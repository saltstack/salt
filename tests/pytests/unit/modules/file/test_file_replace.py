import logging
import os
import shutil
import textwrap

import pytest
import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": configmod.manage_mode,
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {"kernel": "Linux"},
            "__utils__": {
                "files.is_text": MagicMock(return_value=True),
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture
def multiline_string():
    multiline_string = textwrap.dedent(
        """\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam rhoncus
        enim ac bibendum vulputate. Etiam nibh velit, placerat ac auctor in,
        lacinia a turpis. Nulla elit elit, ornare in sodales eu, aliquam sit
        amet nisl.

        Fusce ac vehicula lectus. Vivamus justo nunc, pulvinar in ornare nec,
        sollicitudin id sem. Pellentesque sed ipsum dapibus, dapibus elit id,
        malesuada nisi.

        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec
        venenatis tellus eget massa facilisis, in auctor ante aliquet. Sed nec
        cursus metus. Curabitur massa urna, vehicula id porttitor sed, lobortis
        quis leo.
        """
    )

    return multiline_string


@pytest.fixture
def multiline_file(tmp_path, multiline_string):
    multiline_file = str(tmp_path / "multiline-file.txt")

    with salt.utils.files.fopen(multiline_file, "w+") as file_handle:
        file_handle.write(multiline_string)

    yield multiline_file
    shutil.rmtree(str(tmp_path))


# Make a unique subdir to avoid any tempfile conflicts
@pytest.fixture
def subdir(tmp_path):
    subdir = tmp_path / "test-file-replace-subdir"
    subdir.mkdir()
    yield subdir
    shutil.rmtree(str(subdir))


def test_replace(multiline_file):
    filemod.replace(multiline_file, r"Etiam", "Salticus", backup=False)

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        assert "Salticus" in salt.utils.stringutils.to_unicode(fp.read())


def test_replace_append_if_not_found(subdir):
    """
    Check that file.replace append_if_not_found works
    """
    args = {
        "pattern": "#*baz=(?P<value>.*)",
        "repl": "baz=\\g<value>",
        "append_if_not_found": True,
    }
    base = os.linesep.join(["foo=1", "bar=2"])

    # File ending with a newline, no match
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes(base + os.linesep))
        tfile.flush()
    filemod.replace(tfile.name, **args)
    expected = os.linesep.join([base, "baz=\\g<value>"]) + os.linesep
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # File not ending with a newline, no match
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes(base))
        tfile.flush()
    filemod.replace(tfile.name, **args)
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # A newline should not be added in empty files
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        pass
    filemod.replace(tfile.name, **args)
    expected = args["repl"] + os.linesep
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # Using not_found_content, rather than repl
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes(base))
        tfile.flush()
    args["not_found_content"] = "baz=3"
    expected = os.linesep.join([base, "baz=3"]) + os.linesep
    filemod.replace(tfile.name, **args)
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # not appending if matches
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        base = os.linesep.join(["foo=1", "baz=42", "bar=2"])
        tfile.write(salt.utils.stringutils.to_bytes(base))
        tfile.flush()
    expected = base
    filemod.replace(tfile.name, **args)
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected


def test_backup(multiline_file):
    fext = ".bak"
    bak_file = "{}{}".format(multiline_file, fext)

    filemod.replace(multiline_file, r"Etiam", "Salticus", backup=fext)

    assert os.path.exists(bak_file)
    os.unlink(bak_file)


def test_nobackup(multiline_file):
    fext = ".bak"
    bak_file = "{}{}".format(multiline_file, fext)

    filemod.replace(multiline_file, r"Etiam", "Salticus", backup=False)

    assert not os.path.exists(bak_file)


def test_dry_run(multiline_file):
    before_ctime = os.stat(multiline_file).st_mtime
    filemod.replace(multiline_file, r"Etiam", "Salticus", dry_run=True)
    after_ctime = os.stat(multiline_file).st_mtime

    assert before_ctime == after_ctime


def test_show_changes(multiline_file):
    ret = filemod.replace(multiline_file, r"Etiam", "Salticus", show_changes=True)

    assert ret.startswith("---")  # looks like a diff


def test_noshow_changes(multiline_file):
    ret = filemod.replace(multiline_file, r"Etiam", "Salticus", show_changes=False)

    assert isinstance(ret, bool)


def test_re_str_flags(multiline_file):
    # upper- & lower-case
    filemod.replace(
        multiline_file, r"Etiam", "Salticus", flags=["MULTILINE", "ignorecase"]
    )


def test_re_int_flags(multiline_file):
    filemod.replace(multiline_file, r"Etiam", "Salticus", flags=10)


def test_empty_flags_list(multiline_file):
    filemod.replace(multiline_file, r"Etiam", "Salticus", flags=[])


def test_numeric_repl(multiline_file):
    """
    This test covers cases where the replacement string is numeric, and the
    CLI parser yamlifies it into a numeric type. If not converted back to a
    string type in file.replace, a TypeError occurs when the replacemen is
    attempted. See https://github.com/saltstack/salt/issues/9097 for more
    information.
    """
    filemod.replace(multiline_file, r"Etiam", 123)


def test_search_only_return_true(multiline_file):
    ret = filemod.replace(multiline_file, r"Etiam", "Salticus", search_only=True)

    assert isinstance(ret, bool)
    assert ret is True


def test_search_only_return_false(multiline_file):
    ret = filemod.replace(multiline_file, r"Etian", "Salticus", search_only=True)

    assert isinstance(ret, bool)
    assert ret is False
