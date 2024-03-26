import logging
import os
import shutil
import textwrap

import pytest

import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

if salt.utils.platform.is_windows():
    import salt.modules.win_file as win_file
    import salt.utils.win_dacl as win_dacl

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    if salt.utils.platform.is_windows():
        grains = {"kernel": "Windows"}
    else:
        grains = {"kernel": "Linux"}
    opts = {
        "test": False,
        "file_roots": {"base": "tmp"},
        "pillar_roots": {"base": "tmp"},
        "cachedir": "tmp",
        "grains": grains,
    }

    ret = {
        filemod: {
            "__salt__": {
                "config.manage_mode": MagicMock(),
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": opts,
            "__grains__": grains,
            "__utils__": {
                "files.is_binary": MagicMock(return_value=False),
                "files.get_encoding": MagicMock(return_value="utf-8"),
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }
    if salt.utils.platform.is_windows():
        ret.update(
            {
                win_dacl: {"__opts__": opts},
                win_file: {
                    "__utils__": {"dacl.check_perms": win_dacl.check_perms},
                    "__opts__": opts,
                },
            }
        )

    return ret


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

        first part of start line // START BLOCK : part of start line not removed
        to be removed
        first part of end line // END BLOCK : part of end line not removed

        #-- START BLOCK UNFINISHED

        #-- START BLOCK 1
        old content part 1
        old content part 2
        #-- END BLOCK 1

        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec
        venenatis tellus eget massa facilisis, in auctor ante aliquet. Sed nec
        cursus metus. Curabitur massa urna, vehicula id porttitor sed, lobortis
        quis leo.
        """
    )

    multiline_string = os.linesep.join(multiline_string.splitlines())

    return multiline_string


@pytest.fixture
def multiline_file(tmp_path, multiline_string):
    multiline_file = str(tmp_path / "multiline-file.txt")

    with salt.utils.files.fopen(multiline_file, "w+b") as file_handle:
        file_handle.write(salt.utils.stringutils.to_bytes(multiline_string))

    yield multiline_file
    shutil.rmtree(str(tmp_path))


# Make a unique subdir to avoid any tempfile conflicts
@pytest.fixture
def subdir(tmp_path):
    subdir = tmp_path / "test-file-block-replace-subdir"
    subdir.mkdir()
    yield subdir
    shutil.rmtree(str(subdir))


def test_replace_multiline(multiline_file):
    new_multiline_content = os.linesep.join(
        [
            "Who's that then?",
            "Well, how'd you become king, then?",
            "We found them. I'm not a witch.",
            "We shall say 'Ni' again to you, if you do not appease us.",
        ]
    )
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 1",
            marker_end="#-- END BLOCK 1",
            content=new_multiline_content,
            backup=False,
            append_newline=None,
        )

    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        filecontent = fp.read()

    assert (
        salt.utils.stringutils.to_bytes(
            os.linesep.join(
                ["#-- START BLOCK 1", new_multiline_content, "#-- END BLOCK 1"]
            )
        )
        in filecontent
    )
    assert b"old content part 1" not in filecontent
    assert b"old content part 2" not in filecontent


def test_replace_append(multiline_file):
    new_content = "Well, I didn't vote for you."

    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            append_if_not_found=False,
            backup=False,
        )

    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            append_if_not_found=False,
            backup=False,
        )
    with salt.utils.files.fopen(multiline_file, "r") as fp:
        assert (
            "#-- START BLOCK 2" + "\n" + new_content + "#-- END BLOCK 2"
            not in salt.utils.stringutils.to_unicode(fp.read())
        )

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            backup=False,
            append_if_not_found=True,
        )

    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        assert (
            salt.utils.stringutils.to_bytes(
                os.linesep.join(["#-- START BLOCK 2", f"{new_content}#-- END BLOCK 2"])
            )
            in fp.read()
        )


def test_replace_insert_after(multiline_file):
    new_content = "Well, I didn't vote for you."

    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            insert_after_match="not in the text",
            backup=False,
        )
    with salt.utils.files.fopen(multiline_file, "r") as fp:
        assert (
            "#-- START BLOCK 2" + "\n" + new_content + "#-- END BLOCK 2"
            not in salt.utils.stringutils.to_unicode(fp.read())
        )

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            backup=False,
            insert_after_match="malesuada",
        )

    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        assert (
            salt.utils.stringutils.to_bytes(
                os.linesep.join(["#-- START BLOCK 2", f"{new_content}#-- END BLOCK 2"])
            )
            in fp.read()
        )


def test_replace_append_newline_at_eof(subdir):
    """
    Check that file.blockreplace works consistently on files with and
    without newlines at end of file.
    """
    base = "bar"
    args = {
        "marker_start": "#start",
        "marker_end": "#stop",
        "content": "baz",
        "append_if_not_found": True,
    }
    block = os.linesep.join(["#start", "baz#stop"]) + os.linesep
    # File ending with a newline
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes(base + os.linesep))
        tfile.flush()
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(tfile.name, **args)
    expected = os.linesep.join([base, block])
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # File not ending with a newline
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes(base))
        tfile.flush()
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(tfile.name, **args)
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected
    os.remove(tfile.name)

    # A newline should not be added in empty files
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        pass
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(tfile.name, **args)
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == block
    os.remove(tfile.name)


def test_replace_prepend(multiline_file):
    new_content = "Well, I didn't vote for you."

    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            prepend_if_not_found=False,
            backup=False,
        )
    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        assert (
            salt.utils.stringutils.to_bytes(
                os.linesep.join(["#-- START BLOCK 2", f"{new_content}#-- END BLOCK 2"])
            )
            not in fp.read()
        )

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            backup=False,
            prepend_if_not_found=True,
        )

    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        assert fp.read().startswith(
            salt.utils.stringutils.to_bytes(
                os.linesep.join(
                    [
                        "#-- START BLOCK 2",
                        f"{new_content}#-- END BLOCK 2",
                    ]
                )
            )
        )


def test_replace_insert_before(multiline_file):
    new_content = "Well, I didn't vote for you."

    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            insert_before_match="not in the text",
            backup=False,
        )
    with salt.utils.files.fopen(multiline_file, "r") as fp:
        assert (
            "#-- START BLOCK 2" + "\n" + new_content + "#-- END BLOCK 2"
            not in salt.utils.stringutils.to_unicode(fp.read())
        )

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 2",
            marker_end="#-- END BLOCK 2",
            content=new_content,
            backup=False,
            insert_before_match="malesuada",
        )

    with salt.utils.files.fopen(multiline_file, "rb") as fp:
        assert (
            salt.utils.stringutils.to_bytes(
                os.linesep.join(["#-- START BLOCK 2", f"{new_content}#-- END BLOCK 2"])
            )
            in fp.read()
        )


def test_replace_partial_marked_lines(multiline_file):
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="// START BLOCK",
            marker_end="// END BLOCK",
            content="new content 1",
            backup=False,
        )

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = salt.utils.stringutils.to_unicode(fp.read())
    assert "new content 1" in filecontent
    assert "to be removed" not in filecontent
    assert "first part of start line" in filecontent
    assert "first part of end line" not in filecontent
    assert "part of start line not removed" in filecontent
    assert "part of end line not removed" in filecontent


def test_backup(multiline_file):
    fext = ".bak"
    bak_file = f"{multiline_file}{fext}"

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="// START BLOCK",
            marker_end="// END BLOCK",
            content="new content 2",
            backup=fext,
        )

    assert os.path.exists(bak_file)
    os.unlink(bak_file)
    assert not os.path.exists(bak_file)

    fext = ".bak"
    bak_file = f"{multiline_file}{fext}"

    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="// START BLOCK",
            marker_end="// END BLOCK",
            content="new content 3",
            backup=False,
        )

    assert not os.path.exists(bak_file)


def test_no_modifications(multiline_file):
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 1",
            marker_end="#-- END BLOCK 1",
            content="new content 4",
            backup=False,
            append_newline=None,
        )
    before_ctime = os.stat(multiline_file).st_mtime
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK 1",
            marker_end="#-- END BLOCK 1",
            content="new content 4",
            backup=False,
            append_newline=None,
        )
    after_ctime = os.stat(multiline_file).st_mtime

    assert before_ctime == after_ctime


def test_dry_run(multiline_file):
    before_ctime = os.stat(multiline_file).st_mtime
    filemod.blockreplace(
        multiline_file,
        marker_start="// START BLOCK",
        marker_end="// END BLOCK",
        content="new content 5",
        dry_run=True,
    )
    after_ctime = os.stat(multiline_file).st_mtime

    assert before_ctime == after_ctime


def test_show_changes(multiline_file):
    if salt.utils.platform.is_windows():
        check_perms_patch = win_file.check_perms
    else:
        check_perms_patch = filemod.check_perms
    with patch.object(filemod, "check_perms", check_perms_patch):
        ret = filemod.blockreplace(
            multiline_file,
            marker_start="// START BLOCK",
            marker_end="// END BLOCK",
            content="new content 6",
            backup=False,
            show_changes=True,
        )

        assert ret.startswith("---")  # looks like a diff

        ret = filemod.blockreplace(
            multiline_file,
            marker_start="// START BLOCK",
            marker_end="// END BLOCK",
            content="new content 7",
            backup=False,
            show_changes=False,
        )

        assert isinstance(ret, bool)


def test_unfinished_block_exception(multiline_file):
    with pytest.raises(CommandExecutionError):
        filemod.blockreplace(
            multiline_file,
            marker_start="#-- START BLOCK UNFINISHED",
            marker_end="#-- END BLOCK UNFINISHED",
            content="foobar",
            backup=False,
        )
