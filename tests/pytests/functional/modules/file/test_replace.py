"""
Tests for file.rename function
"""
import os
import shutil

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(scope="module")
def multiline_string():
    return """\
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


@pytest.fixture(scope="function")
def multiline_file(tmp_path_factory, multiline_string):
    temp_dir = tmp_path_factory.mktemp("replace-tests")
    test_file = temp_dir / "multiline-file.txt"
    test_file.write_text(multiline_string)
    yield test_file
    shutil.rmtree(str(temp_dir))


def test_no_backup(file, multiline_file):
    # Backup file should NOT be created
    bak_file = "{}.bak".format(multiline_file)
    assert "Salticus" not in multiline_file.read_text()
    file.replace(str(multiline_file), "Etiam", "Salticus", backup=False)
    assert "Salticus" in multiline_file.read_text()
    assert not os.path.exists(bak_file)


def test_backup(file, multiline_file):
    # Should create a backup file. This is basically the default
    bak_file = "{}.bak".format(multiline_file)
    file.replace(str(multiline_file), "Etiam", "Salticus")
    assert "Salticus" in multiline_file.read_text()
    assert os.path.exists(bak_file)


def test_append_if_not_found_no_match_newline(file):
    contents = "foo=1\nbar=2\n"
    expected = "foo=1\nbar=2\nbaz=\\g<value>\n"
    with pytest.helpers.temp_file("test_file.txt", contents) as target:
        file.replace(
            path=str(target),
            pattern="#*baz=(?P<value>.*)",
            repl="baz=\\g<value>",
            append_if_not_found=True,
        )
        assert target.read_text() == expected


def test_append_if_not_found_no_match_no_newline(file):
    contents = "foo=1\nbar=2"
    expected = "foo=1\nbar=2\nbaz=\\g<value>\n"
    with pytest.helpers.temp_file("test_file.txt", contents) as target:
        file.replace(
            path=str(target),
            pattern="#*baz=(?P<value>.*)",
            repl="baz=\\g<value>",
            append_if_not_found=True,
        )
        assert target.read_text() == expected


def test_append_if_not_found_empty_file(file):
    # A newline should NOT be added in empty files
    contents = None
    expected = "baz=\\g<value>\n"
    with pytest.helpers.temp_file("test_file.txt", contents) as target:
        file.replace(
            path=str(target),
            pattern="#*baz=(?P<value>.*)",
            repl="baz=\\g<value>",
            append_if_not_found=True,
        )
        assert target.read_text() == expected


def test_append_if_not_found_content(file):
    # Using not_found_content, rather than repl
    contents = None
    expected = "baz=3\n"
    with pytest.helpers.temp_file("test_file.txt", contents) as target:
        file.replace(
            path=str(target),
            pattern="#*baz=(?P<value>.*)",
            repl="baz=\\g<value>",
            append_if_not_found=True,
            not_found_content="baz=3",
        )
        assert target.read_text() == expected


def test_append_if_not_found_no_append_on_match(file):
    # Not appending if matches
    contents = "foo=1\nbaz=42\nbar=2"
    with pytest.helpers.temp_file("test_file.txt", contents) as target:
        file.replace(
            path=str(target),
            pattern="#*baz=(?P<value>.*)",
            repl="baz=\\g<value>",
            append_if_not_found=True,
            not_found_content="baz=3",
        )
        assert target.read_text() == contents


def test_dry_run(file, multiline_file):
    before_time = os.stat(str(multiline_file)).st_mtime
    file.replace(str(multiline_file), r"Etiam", "Salticus", dry_run=True)
    after_time = os.stat(str(multiline_file)).st_mtime
    assert before_time == after_time


def test_show_changes(file, multiline_file):
    ret = file.replace(str(multiline_file), r"Etiam", "Salticus", show_changes=True)
    assert ret.startswith("---")  # looks like a diff


def test_no_show_changes(file, multiline_file):
    ret = file.replace(str(multiline_file), r"Etiam", "Salticus", show_changes=False)
    assert isinstance(ret, bool)


def test_re_str_flags(file, multiline_file):
    file.replace(
        str(multiline_file), r"etiam", "Salticus", flags=["MULTILINE", "ignorecase"]
    )
    assert "Salticus" in multiline_file.read_text()


def test_re_int_flags(file, multiline_file):
    # flag for multiline and ignore case is 10
    file.replace(str(multiline_file), r"etiam", "Salticus", flags=10)
    assert "Salticus" in multiline_file.read_text()


def test_numeric_repl(file, multiline_file):
    """
    This test covers cases where the replacement string is numeric. The CLI
    parser yaml-fies it into a numeric type. If not converted back to a string
    type in file.replace, a TypeError occurs when the replace is attempted. See
    https://github.com/saltstack/salt/issues/9097 for more information.
    """
    file.replace(str(multiline_file), r"Etiam", 123)
    assert "123" in multiline_file.read_text()


def test_search_only_return_true(file, multiline_file):
    ret = file.replace(str(multiline_file), r"Etiam", "Salticus", search_only=True)
    assert isinstance(ret, bool)
    assert ret is True


def test_search_only_return_false(file, multiline_file):
    ret = file.replace(str(multiline_file), r"Etian", "Salticus", search_only=True)
    assert isinstance(ret, bool)
    assert ret is False


def test_symlink(file, multiline_file):
    # https://github.com/saltstack/salt/pull/61326
    try:
        # Create a symlink to target
        sym_link = multiline_file.parent / "symlink.lnk"
        sym_link.symlink_to(multiline_file)
        # file.replace on the symlink
        file.replace(str(sym_link), r"Etiam", "Salticus")
        # test that the target was changed
        assert "Salticus" in multiline_file.read_text()
    finally:
        if os.path.exists(str(sym_link)):
            sym_link.unlink()


def test_replace_no_modify_time_update_on_no_change(file, multiline_file):
    os.utime(str(multiline_file), (1552661253, 1552661253))
    mtime = os.stat(str(multiline_file)).st_mtime
    file.replace(str(multiline_file), r"Etia.", "Etiam", backup=False)
    nmtime = os.stat(str(multiline_file)).st_mtime

    assert mtime == nmtime


def test_backslash_literal(file, multiline_file):
    file.replace(str(multiline_file), r"Etiam", "Emma", backslash_literal=True)
    assert "Emma" in multiline_file.read_text()
