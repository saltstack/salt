"""
Unit tests for file.line
"""

import logging
import os
import shutil

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
from salt.exceptions import CommandExecutionError
from tests.support.mock import DEFAULT, MagicMock, mock_open, patch

log = logging.getLogger(__name__)


class DummyStat:
    st_mode = 33188
    st_ino = 115331251
    st_dev = 44
    st_nlink = 1
    st_uid = 99200001
    st_gid = 99200001
    st_size = 41743
    st_atime = 1552661253
    st_mtime = 1552661253
    st_ctime = 1552661253


@pytest.fixture
def anyattr():
    class AnyAttr:
        def __getattr__(self, item):
            return 0

        def __call__(self, *args, **kwargs):
            return self

    return AnyAttr()


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
            "__utils__": {"stringutils.get_diff": salt.utils.stringutils.get_diff},
        }
    }


@pytest.fixture
def get_body():
    def _get_body(content):
        """
        The body is written as bytestrings or strings depending on platform.
        This func accepts a string of content and returns the appropriate list
        of strings back.
        """
        ret = content.splitlines(True)
        return salt.utils.data.decode_list(ret, to_str=True)

    return _get_body


@pytest.fixture
def tempfile_name(tmp_path):
    subdir = tmp_path / "file-line-temp-dir"
    subdir.mkdir()
    filename = str(subdir / "file-line-temp-file")

    # File needs to be created
    with salt.utils.files.fopen(filename, "w"):
        pass

    yield filename

    # We need to make sure to remove the tree we just created to avoid clashes with other tests
    shutil.rmtree(str(subdir))


def test_set_line_should_raise_command_execution_error_with_no_mode():
    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(lines=[], mode=None)
    assert str(err.value) == "Mode was not defined. How to process the file?"


def test_set_line_should_raise_command_execution_error_with_unknown_mode():
    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(lines=[], mode="fnord")
    assert str(err.value) == "Unknown mode: fnord"


@pytest.mark.parametrize("mode", ("insert", "ensure", "replace"))
def test_if_content_is_none_and_mode_is_valid_but_not_delete_it_should_raise_command_execution_error(
    mode,
):
    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(lines=[], mode=mode)
    assert str(err.value) == "Content can only be empty if mode is delete"


@pytest.mark.parametrize("mode", ("delete", "replace"))
def test_if_delete_or_replace_is_called_with_empty_lines_it_should_warn_and_return_empty_body(
    mode,
):
    with patch("salt.modules.file.log.warning", MagicMock()) as fake_warn:
        actual_lines = filemod._set_line(mode=mode, lines=[], content="roscivs")
        assert actual_lines == []
        fake_warn.assert_called_with("Cannot find text to %s. File is empty.", mode)


def test_if_mode_is_delete_and_not_before_after_or_match_then_content_should_be_used_to_delete_line():
    lines = ["foo", "roscivs", "bar"]
    to_remove = "roscivs"
    expected_lines = ["foo", "bar"]

    actual_lines = filemod._set_line(mode="delete", lines=lines, content=to_remove)

    assert actual_lines == expected_lines


def test_if_mode_is_replace_and_not_before_after_or_match_and_content_exists_then_lines_should_not_change():
    original_lines = ["foo", "roscivs", "bar"]
    content = "roscivs"

    actual_lines = filemod._set_line(
        mode="replace", lines=original_lines, content=content
    )

    assert actual_lines == original_lines


def test_if_mode_is_replace_and_match_is_set_then_it_should_replace_the_first_match():
    to_replace = "quuxy"
    replacement = "roscivs"
    original_lines = ["foo", to_replace, "bar"]
    expected_lines = ["foo", replacement, "bar"]

    actual_lines = filemod._set_line(
        mode="replace",
        lines=original_lines,
        content=replacement,
        match=to_replace,
    )

    assert actual_lines == expected_lines


def test_if_mode_is_replace_and_indent_is_true_then_it_should_match_indention_of_existing_line():
    indents = "\t\t      \t \t"
    to_replace = indents + "quuxy"
    replacement = "roscivs"
    original_lines = ["foo", to_replace, "bar"]
    expected_lines = ["foo", indents + replacement, "bar"]

    actual_lines = filemod._set_line(
        mode="replace",
        lines=original_lines,
        content=replacement,
        match=to_replace,
        indent=True,
    )

    assert actual_lines == expected_lines


def test_if_mode_is_replace_and_indent_is_false_then_it_should_just_use_content():
    indents = "\t\t      \t \t"
    to_replace = indents + "quuxy"
    replacement = "\t        \t\troscivs"
    original_lines = ["foo", to_replace, "bar"]
    expected_lines = ["foo", replacement, "bar"]

    actual_lines = filemod._set_line(
        mode="replace",
        lines=original_lines,
        content=replacement,
        match=to_replace,
        indent=False,
    )

    assert actual_lines == expected_lines


def test_if_mode_is_insert_and_no_location_before_or_after_then_it_should_raise_command_execution_error():
    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=[],
            content="fnord",
            mode="insert",
            location=None,
            before=None,
            after=None,
        )

    assert (
        str(err.value)
        == 'On insert either "location" or "before/after" conditions are required.'
    )


def test_if_mode_is_insert_and_location_is_start_it_should_insert_content_at_start():
    lines = ["foo", "bar", "bang"]
    content = "roscivs"
    expected_lines = [content] + lines

    with patch("os.linesep", ""):
        actual_lines = filemod._set_line(
            lines=lines,
            content=content,
            mode="insert",
            location="start",
        )

    assert actual_lines == expected_lines


def test_if_mode_is_insert_and_lines_have_eol_then_inserted_line_should_have_matching_eol():
    linesep = "\r\n"
    lines = ["foo" + linesep]
    content = "roscivs"
    expected_lines = [content + linesep] + lines

    actual_lines = filemod._set_line(
        lines=lines,
        content=content,
        mode="insert",
        location="start",
    )

    assert actual_lines == expected_lines


def test_if_mode_is_insert_and_no_lines_then_the_content_should_have_os_linesep_added():
    content = "roscivs"
    fake_linesep = "\U0001f40d"
    expected_lines = [content + fake_linesep]

    with patch("os.linesep", fake_linesep):
        actual_lines = filemod._set_line(
            lines=[],
            content=content,
            mode="insert",
            location="start",
        )

    assert actual_lines == expected_lines


def test_if_location_is_end_of_empty_file_then_it_should_just_be_content():
    content = "roscivs"
    expected_lines = [content]

    actual_lines = filemod._set_line(
        lines=[],
        content=content,
        mode="insert",
        location="end",
    )

    assert actual_lines == expected_lines


def test_if_location_is_end_of_file_and_indent_is_True_then_line_should_match_previous_indent():
    content = "roscivs"
    indent = "   \t\t\t   "
    original_lines = [indent + "fnord"]
    expected_lines = original_lines + [indent + content]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location="end",
        indent=True,
    )

    assert actual_lines == expected_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_if_location_is_not_set_but_before_and_after_are_then_line_should_appear_as_the_line_before_before(
    indent,
):
    content = "roscivs"
    after = "after"
    before = "before"
    original_lines = ["foo", "bar", indent + after, "belowme", indent + before]
    expected_lines = [
        "foo",
        "bar",
        indent + after,
        "belowme",
        indent + content,
        indent + before,
    ]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=None,
        before=before,
        after=after,
    )

    assert actual_lines == expected_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_insert_with_after_and_before_with_no_location_should_indent_to_match_before_indent(
    indent,
):
    content = "roscivs"
    after = "after"
    before = "before"
    original_lines = [
        "foo",
        "bar",
        indent + after,
        "belowme",
        (indent * 2) + before,
    ]
    expected_lines = [
        "foo",
        "bar",
        indent + after,
        "belowme",
        (indent * 2) + content,
        (indent * 2) + before,
    ]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=None,
        before=before,
        after=after,
    )

    assert actual_lines == expected_lines


def test_if_not_location_but_before_and_after_and_more_than_one_after_it_should_CommandExecutionError():
    after = "one"
    before = "two"
    original_lines = [after, after, after, after, before]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=None,
            before=before,
            after=after,
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "after" expression'
    )


def test_if_not_location_but_before_and_after_and_more_than_one_before_it_should_CommandExecutionError():
    after = "one"
    before = "two"
    original_lines = [after, before, before, before]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=None,
            before=before,
            after=after,
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "before" expression'
    )


def test_if_not_location_or_before_but_after_and_after_has_more_than_one_it_should_CommandExecutionError():
    location = None
    before = None
    after = "after"
    original_lines = [after, after, after]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=location,
            before=before,
            after=after,
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "after" expression'
    )


def test_if_not_location_or_after_but_before_and_before_has_more_than_one_it_should_CommandExecutionError():
    location = None
    before = "before"
    after = None
    original_lines = [before, before, before]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=location,
            before=before,
            after=after,
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "before" expression'
    )


def test_if_not_location_or_after_and_no_before_in_lines_it_should_CommandExecutionError():
    location = None
    before = "before"
    after = None
    original_lines = ["fnord", "fnord"]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=location,
            before=before,
            after=after,
        )
    assert str(err.value) == "Neither before or after was found in file"


def test_if_not_location_or_before_and_no_after_in_lines_it_should_CommandExecutionError():
    location = None
    before = None
    after = "after"
    original_lines = ["fnord", "fnord"]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content="fnord",
            mode="insert",
            location=location,
            before=before,
            after=after,
        )
    assert str(err.value) == "Neither before or after was found in file"


def test_if_not_location_or_before_but_after_then_line_should_be_inserted_after_after():
    location = before = None
    after = "indessed"
    content = "roscivs"
    indent = "\t\t\t   "
    original_lines = ["foo", indent + after, "bar"]
    expected_lines = ["foo", indent + after, indent + content, "bar"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
    )

    assert actual_lines == expected_lines


def test_insert_with_after_should_ignore_line_endings_on_comparison():
    after = "after"
    content = "roscivs"
    line_endings = "\r\n\r\n"
    original_lines = [after, content + line_endings]

    actual_lines = filemod._set_line(
        lines=original_lines[:],
        content=content,
        mode="insert",
        after=after,
    )

    assert actual_lines == original_lines


def test_insert_with_before_should_ignore_line_endings_on_comparison():
    before = "before"
    content = "bottia"
    line_endings = "\r\n\r\n"
    original_lines = [content + line_endings, before]

    actual_lines = filemod._set_line(
        lines=original_lines[:],
        content=content,
        mode="insert",
        before=before,
    )

    assert actual_lines == original_lines


def test_if_not_location_or_before_but_after_and_indent_False_then_line_should_be_inserted_after_after_without_indent():
    location = before = None
    after = "indessed"
    content = "roscivs"
    indent = "\t\t\t   "
    original_lines = ["foo", indent + after, "bar"]
    expected_lines = ["foo", indent + after, content, "bar"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
        indent=False,
    )

    assert actual_lines == expected_lines


def test_if_not_location_or_after_but_before_then_line_should_be_inserted_before_before():
    location = after = None
    before = "indessed"
    content = "roscivs"
    indent = "\t\t\t   "
    original_lines = [indent + "foo", indent + before, "bar"]
    expected_lines = [indent + "foo", indent + content, indent + before, "bar"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
    )

    assert actual_lines == expected_lines


def test_if_not_location_or_after_but_before_and_indent_False_then_line_should_be_inserted_before_before_without_indent():
    location = after = None
    before = "indessed"
    content = "roscivs"
    indent = "\t\t\t   "
    original_lines = [indent + "foo", before, "bar"]
    expected_lines = [indent + "foo", content, before, "bar"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
        indent=False,
    )

    assert actual_lines == expected_lines


def test_insert_after_the_last_line_should_work():
    location = before = None
    after = "indessed"
    content = "roscivs"
    original_lines = [after]
    expected_lines = [after, content]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
        indent=True,
    )

    assert actual_lines == expected_lines


def test_insert_should_work_just_like_ensure_on_before():
    # I'm pretty sure that this is or should be a bug, but that
    # is how things currently work, so I'm calling it out here.
    #
    # If that should change, then this test should change.
    before = "indessed"
    content = "roscivs"
    original_lines = [content, before]

    actual_lines = filemod._set_line(
        lines=original_lines[:],
        content=content,
        mode="insert",
        before=before,
    )

    assert actual_lines == original_lines


def test_insert_should_work_just_like_ensure_on_after():
    # I'm pretty sure that this is or should be a bug, but that
    # is how things currently work, so I'm calling it out here.
    #
    # If that should change, then this test should change.
    after = "indessed"
    content = "roscivs"
    original_lines = [after, content]

    actual_lines = filemod._set_line(
        # If we don't pass in a copy of the lines then it modifies
        # them, and our test fails. Oops.
        lines=original_lines[:],
        content=content,
        mode="insert",
        after=after,
    )

    assert actual_lines == original_lines


def test_insert_before_the_first_line_should_work():
    location = after = None
    before = "indessed"
    content = "roscivs"
    original_lines = [before]
    expected_lines = [content, before]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="insert",
        location=location,
        before=before,
        after=after,
        indent=True,
    )

    assert actual_lines == expected_lines


def test_ensure_with_before_and_too_many_after_should_CommandExecutionError():
    location = None
    before = "before"
    after = "after"
    lines = [after, after, before]
    content = "fnord"

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=lines,
            content=content,
            mode="ensure",
            location=location,
            before=before,
            after=after,
        )

    assert (
        str(err.value) == 'Found more than expected occurrences in "after" expression'
    )


def test_ensure_with_too_many_after_should_CommandExecutionError():
    after = "fnord"
    bad_lines = [after, after]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=bad_lines,
            content="asdf",
            after=after,
            mode="ensure",
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "after" expression'
    )


def test_ensure_with_after_and_too_many_before_should_CommandExecutionError():
    location = None
    before = "before"
    after = "after"
    lines = [after, before, before]
    content = "fnord"

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=lines,
            content=content,
            mode="ensure",
            location=location,
            before=before,
            after=after,
        )

    assert (
        str(err.value) == 'Found more than expected occurrences in "before" expression'
    )


def test_ensure_with_too_many_before_should_CommandExecutionError():
    before = "fnord"
    bad_lines = [before, before]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=bad_lines,
            content="asdf",
            before=before,
            mode="ensure",
        )
    assert (
        str(err.value) == 'Found more than expected occurrences in "before" expression'
    )


def test_ensure_with_before_and_after_that_already_contains_the_line_should_return_original_info():
    before = "before"
    after = "after"
    content = "roscivs"
    original_lines = [after, content, before]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        mode="ensure",
        after=after,
        before=before,
    )

    assert actual_lines == original_lines


def test_ensure_with_too_many_lines_between_before_and_after_should_CommandExecutionError():
    before = "before"
    after = "after"
    content = "roscivs"
    original_lines = [after, "fnord", "fnord", before]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=original_lines,
            content=content,
            mode="ensure",
            after=after,
            before=before,
        )

    assert (
        str(err.value)
        == 'Found more than one line between boundaries "before" and "after".'
    )


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_no_lines_between_before_and_after_should_insert_a_line(indent):
    before = "before"
    after = "after"
    content = "roscivs"
    original_lines = [indent + after, before]
    expected_lines = [indent + after, indent + content, before]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == expected_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_existing_but_different_line_should_set_the_line(indent):
    before = "before"
    after = "after"
    content = "roscivs"
    original_lines = [indent + after, "fnord", before]
    expected_lines = [indent + after, indent + content, before]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == expected_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_after_and_existing_content_should_return_same_lines(indent):
    before = None
    after = "after"
    content = "roscivs"
    original_lines = [indent + after, indent + content, "fnord"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == original_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_after_and_missing_content_should_add_it(indent):
    before = None
    after = "after"
    content = "roscivs"
    original_lines = [indent + after, "more fnord", "fnord"]
    expected_lines = [indent + after, indent + content, "more fnord", "fnord"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == expected_lines


def test_ensure_with_after_and_content_at_the_end_should_not_add_duplicate():
    after = "after"
    content = "roscivs"
    original_lines = [after, content + "\n"]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        after=after,
        mode="ensure",
    )

    assert actual_lines == original_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_before_and_missing_content_should_add_it(indent):
    before = "before"
    after = None
    content = "roscivs"
    original_lines = [indent + "fnord", indent + "fnord", before]
    expected_lines = [
        indent + "fnord",
        indent + "fnord",
        indent + content,
        before,
    ]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == expected_lines


@pytest.mark.parametrize("indent", ("", " \t \t\t\t      "))
def test_ensure_with_before_and_existing_content_should_return_same_lines(indent):
    before = "before"
    after = None
    content = "roscivs"
    original_lines = [indent + "fnord", indent + content, before]

    actual_lines = filemod._set_line(
        lines=original_lines,
        content=content,
        before=before,
        after=after,
        mode="ensure",
        indent=True,
    )

    assert actual_lines == original_lines


def test_ensure_without_before_and_after_should_CommandExecutionError():
    before = "before"
    after = "after"
    bad_lines = ["fnord", "fnord1", "fnord2"]

    with pytest.raises(CommandExecutionError) as err:
        filemod._set_line(
            lines=bad_lines,
            before=before,
            after=after,
            content="aardvark",
            mode="ensure",
        )
    assert (
        str(err.value)
        == "Wrong conditions? Unable to ensure line without knowing where"
        " to put it before and/or after."
    )


@pytest.mark.parametrize("mode", ["delete", "replace"])
def test_delete_line_in_empty_file(anyattr, mode):
    """
    Tests that when calling file.line with ``mode=delete``,
    the function doesn't stack trace if the file is empty.
    Should return ``False``.

    See Issue #38438.
    """
    with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ):
        _log = MagicMock()
        with patch("salt.utils.files.fopen", mock_open(read_data="")), patch(
            "os.stat", anyattr
        ), patch("salt.modules.file.log", _log):
            assert not filemod.line(
                "/dummy/path", content="foo", match="bar", mode=mode
            )
        warning_call = _log.warning.call_args_list[0][0]
        warning_log_msg = warning_call[0] % warning_call[1:]
        assert "Cannot find text to {}".format(mode) in warning_log_msg


@pytest.mark.parametrize("mode", ["delete", "replace"])
def test_line_delete_no_match(mode):
    """
    Tests that when calling file.line with ``mode=delete``,
    with not matching pattern to delete returns False
    :return:
    """
    file_content = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/custom"]
    )
    match = "not matching"
    with patch("os.path.realpath", MagicMock()), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ), patch("os.stat", MagicMock()):
        files_fopen = mock_open(read_data=file_content)
        with patch("salt.utils.files.fopen", files_fopen):
            atomic_opener = mock_open()
            with patch("salt.utils.atomicfile.atomic_open", atomic_opener):
                assert not filemod.line("foo", content="foo", match=match, mode=mode)


@pytest.mark.parametrize(
    "mode,err_msg",
    [
        (None, "How to process the file"),
        ("nonsense", "Unknown mode"),
    ],
)
def test_line_modecheck_failure(mode, err_msg):
    """
    Test for file.line for empty or wrong mode.
    Calls unknown or empty mode and expects failure.
    :return:
    """
    with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ):
        with pytest.raises(CommandExecutionError) as exc_info:
            filemod.line("foo", mode=mode)
        assert err_msg in str(exc_info.value)


@pytest.mark.parametrize("mode", ["insert", "ensure", "replace"])
def test_line_no_content(mode):
    """
    Test for file.line for an empty content when not deleting anything.
    :return:
    """
    with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ):
        with pytest.raises(CommandExecutionError) as exc_info:
            filemod.line("foo", mode=mode)
        assert 'Content can only be empty if mode is "delete"' in str(exc_info.value)


def test_line_insert_no_location_no_before_no_after():
    """
    Test for file.line for insertion but define no location/before/after.
    :return:
    """
    with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ), patch("os.stat", MagicMock()), patch(
        "salt.utils.files.fopen", mock_open(read_data="test data")
    ):
        with pytest.raises(CommandExecutionError) as exc_info:
            filemod.line("foo", content="test content", mode="insert")
        assert '"location" or "before/after"' in str(exc_info.value)


def test_line_insert_after_no_pattern(tempfile_name, get_body):
    """
    Test for file.line for insertion after specific line, using no pattern.

    See issue #38670
    :return:
    """
    file_content = os.linesep.join(["file_roots:", "  base:", "    - /srv/salt"])
    file_modified = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/custom"]
    )
    cfg_content = "- /srv/custom"

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name, content=cfg_content, after="- /srv/salt", mode="insert"
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


@pytest.mark.parametrize("after_line", ["file_r.*", ".*roots"])
def test_line_insert_after_pattern(tempfile_name, get_body, after_line):
    """
    Test for file.line for insertion after specific line, using pattern.

    See issue #38670
    :return:
    """
    file_content = os.linesep.join(
        [
            "file_boots:",
            "  - /rusty",
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/sugar",
        ]
    )
    file_modified = os.linesep.join(
        [
            "file_boots:",
            "  - /rusty",
            "file_roots:",
            "  custom:",
            "    - /srv/custom",
            "  base:",
            "    - /srv/salt",
            "    - /srv/sugar",
        ]
    )
    cfg_content = os.linesep.join(["  custom:", "    - /srv/custom"])
    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            after=after_line,
            mode="insert",
            indent=False,
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        # We passed cfg_content with a newline in the middle, so it
        # will be written as two lines in the same element of the list
        # passed to .writelines()
        expected[3] = expected[3] + expected.pop(4)
        assert writelines_content[0] == expected, (
            writelines_content[0],
            expected,
        )


def test_line_insert_multi_line_content_after_unicode(tempfile_name, get_body):
    """
    Test for file.line for insertion after specific line with Unicode

    See issue #48113
    :return:
    """
    file_content = "This is a line{}This is another line".format(os.linesep)
    file_modified = salt.utils.stringutils.to_str(
        "This is a line{}"
        "This is another line{}"
        "This is a line with unicode Ŷ".format(os.linesep, os.linesep)
    )
    cfg_content = "This is a line with unicode Ŷ"
    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    after_line = "This is another line"
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            after=after_line,
            mode="insert",
            indent=False,
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (
            writelines_content[0],
            expected,
        )


@pytest.mark.parametrize("before_line", ["/srv/salt", "/srv/sa.*t"])
def test_line_insert_before(tempfile_name, get_body, before_line):
    """
    Test for file.line for insertion before specific line, using pattern and no patterns.

    See issue #38670
    :return:
    """
    file_content = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/sugar"]
    )
    file_modified = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/custom",
            "    - /srv/salt",
            "    - /srv/sugar",
        ]
    )
    cfg_content = "- /srv/custom"

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name, content=cfg_content, before=before_line, mode="insert"
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        # assert writelines_content[0] == expected, (writelines_content[0], expected)
        assert writelines_content[0] == expected


def test_line_assert_exception_pattern():
    """
    Test for file.line for exception on insert with too general pattern.

    :return:
    """
    file_content = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/sugar"]
    )
    cfg_content = "- /srv/custom"
    before_line = "/sr.*"
    with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ), patch("os.stat", MagicMock()), patch(
        "salt.utils.files.fopen", mock_open(read_data=file_content)
    ), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ):
        with pytest.raises(CommandExecutionError) as cm:
            filemod.line(
                "foo",
                content=cfg_content,
                before=before_line,
                mode="insert",
            )
        assert (
            str(cm.value)
            == 'Found more than expected occurrences in "before" expression'
        )


def test_line_insert_before_after(tempfile_name, get_body):
    """
    Test for file.line for insertion before specific line, using pattern and no patterns.

    See issue #38670
    :return:
    """
    file_content = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/pepper",
            "    - /srv/sugar",
        ]
    )
    file_modified = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/pepper",
            "    - /srv/coriander",
            "    - /srv/sugar",
        ]
    )
    cfg_content = "- /srv/coriander"

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    b_line = "/srv/sugar"
    a_line = "/srv/salt"
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            before=b_line,
            after=a_line,
            mode="insert",
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected


def test_line_insert_start(tempfile_name, get_body):
    """
    Test for file.line for insertion at the beginning of the file
    :return:
    """
    cfg_content = "everything: fantastic"
    file_content = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/sugar"]
    )
    file_modified = os.linesep.join(
        [
            cfg_content,
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/sugar",
        ]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name, content=cfg_content, location="start", mode="insert"
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


def test_line_insert_end(tempfile_name, get_body):
    """
    Test for file.line for insertion at the end of the file (append)
    :return:
    """
    cfg_content = "everything: fantastic"
    file_content = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/sugar"]
    )
    file_modified = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/sugar",
            "    " + cfg_content,
        ]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(tempfile_name, content=cfg_content, location="end", mode="insert")
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


def test_line_insert_ensure_before(tempfile_name, get_body):
    """
    Test for file.line for insertion ensuring the line is before
    :return:
    """
    cfg_content = "/etc/init.d/someservice restart"
    file_content = os.linesep.join(["#!/bin/bash", "", "exit 0"])
    file_modified = os.linesep.join(["#!/bin/bash", "", cfg_content, "exit 0"])

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(tempfile_name, content=cfg_content, before="exit 0", mode="ensure")
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


def test_line_insert_duplicate_ensure_before(tempfile_name):
    """
    Test for file.line for insertion ensuring the line is before
    :return:
    """
    cfg_content = "/etc/init.d/someservice restart"
    file_content = os.linesep.join(["#!/bin/bash", "", cfg_content, "exit 0"])
    file_modified = os.linesep.join(["#!/bin/bash", "", cfg_content, "exit 0"])

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(tempfile_name, content=cfg_content, before="exit 0", mode="ensure")
        # If file not modified no handlers in dict
        assert atomic_open_mock.filehandles.get(tempfile_name) is None


def test_line_insert_ensure_before_first_line(tempfile_name, get_body):
    """
    Test for file.line for insertion ensuring the line is before first line
    :return:
    """
    cfg_content = "#!/bin/bash"
    file_content = os.linesep.join(["/etc/init.d/someservice restart", "exit 0"])
    file_modified = os.linesep.join(
        [cfg_content, "/etc/init.d/someservice restart", "exit 0"]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            before="/etc/init.d/someservice restart",
            mode="ensure",
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


def test_line_insert_ensure_after(tempfile_name, get_body):
    """
    Test for file.line for insertion ensuring the line is after
    :return:
    """
    cfg_content = "exit 0"
    file_content = os.linesep.join(["#!/bin/bash", "/etc/init.d/someservice restart"])
    file_modified = os.linesep.join(
        ["#!/bin/bash", "/etc/init.d/someservice restart", cfg_content]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            after="/etc/init.d/someservice restart",
            mode="ensure",
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (writelines_content[0], expected)


def test_line_insert_duplicate_ensure_after(tempfile_name):
    """
    Test for file.line for insertion ensuring the line is after
    :return:
    """
    cfg_content = "exit 0"
    file_content = os.linesep.join(
        ["#!/bin/bash", "/etc/init.d/someservice restart", cfg_content]
    )
    file_modified = os.linesep.join(
        ["#!/bin/bash", "/etc/init.d/someservice restart", cfg_content]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content=cfg_content,
            after="/etc/init.d/someservice restart",
            mode="ensure",
        )
        # If file not modified no handlers in dict
        assert atomic_open_mock.filehandles.get(tempfile_name) is None


def test_line_insert_ensure_beforeafter_twolines(tempfile_name, get_body):
    """
    Test for file.line for insertion ensuring the line is between two lines
    :return:
    """
    cfg_content = 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev users"'
    # pylint: disable=W1401
    file_content = os.linesep.join(
        [
            r'NAME_REGEX="^[a-z][-a-z0-9_]*\$"',
            'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"',
        ]
    )
    # pylint: enable=W1401
    after, before = file_content.split(os.linesep)
    file_modified = os.linesep.join([after, cfg_content, before])

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    for (_after, _before) in [(after, before), ("NAME_.*", "SKEL_.*")]:
        with patch("os.path.isfile", isfile_mock), patch(
            "os.stat", MagicMock(return_value=DummyStat())
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
            "salt.utils.atomicfile.atomic_open", mock_open()
        ) as atomic_open_mock:
            filemod.line(
                tempfile_name,
                content=cfg_content,
                after=_after,
                before=_before,
                mode="ensure",
            )
            handles = atomic_open_mock.filehandles[tempfile_name]
            # We should only have opened the file once
            open_count = len(handles)
            assert open_count == 1, open_count
            # We should only have invoked .writelines() once...
            writelines_content = handles[0].writelines_calls
            writelines_count = len(writelines_content)
            assert writelines_count == 1, writelines_count
            # ... with the updated content
            expected = get_body(file_modified)
            assert writelines_content[0] == expected, (
                writelines_content[0],
                expected,
            )


def test_line_insert_ensure_beforeafter_twolines_exists(tempfile_name):
    """
    Test for file.line for insertion ensuring the line is between two lines
    where content already exists
    """
    cfg_content = 'EXTRA_GROUPS="dialout"'
    # pylint: disable=W1401
    file_content = os.linesep.join(
        [
            r'NAME_REGEX="^[a-z][-a-z0-9_]*\$"',
            'EXTRA_GROUPS="dialout"',
            'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"',
        ]
    )
    # pylint: enable=W1401
    after, before = (
        file_content.split(os.linesep)[0],
        file_content.split(os.linesep)[2],
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    for (_after, _before) in [(after, before), ("NAME_.*", "SKEL_.*")]:
        with patch("os.path.isfile", isfile_mock), patch(
            "os.stat", MagicMock(return_value=DummyStat())
        ), patch("salt.utils.files.fopen", mock_open(read_data=file_content)), patch(
            "salt.utils.atomicfile.atomic_open", mock_open()
        ) as atomic_open_mock:
            result = filemod.line(
                "foo",
                content=cfg_content,
                after=_after,
                before=_before,
                mode="ensure",
            )
            # We should not have opened the file
            assert not atomic_open_mock.filehandles
            # No changes should have been made
            assert result is False


def test_line_insert_ensure_beforeafter_rangelines():
    """
    Test for file.line for insertion ensuring the line is between two lines
    within the range.  This expected to bring no changes.
    """
    cfg_content = 'EXTRA_GROUPS="dialout cdrom floppy audio video plugdev users"'
    # pylint: disable=W1401
    file_content = (
        r'NAME_REGEX="^[a-z][-a-z0-9_]*\$"{}SETGID_HOME=no{}ADD_EXTRA_GROUPS=1{}'
        'SKEL_IGNORE_REGEX="dpkg-(old|new|dist|save)"'.format(
            os.linesep, os.linesep, os.linesep
        )
    )
    # pylint: enable=W1401
    after, before = (
        file_content.split(os.linesep)[0],
        file_content.split(os.linesep)[-1],
    )
    for (_after, _before) in [(after, before), ("NAME_.*", "SKEL_.*")]:
        with patch("os.path.realpath", MagicMock(wraps=lambda x: x)), patch(
            "os.path.isfile", MagicMock(return_value=True)
        ), patch("os.stat", MagicMock()), patch(
            "salt.utils.files.fopen", mock_open(read_data=file_content)
        ), patch(
            "salt.utils.atomicfile.atomic_open", mock_open()
        ):
            with pytest.raises(CommandExecutionError) as exc_info:
                filemod.line(
                    "foo",
                    content=cfg_content,
                    after=_after,
                    before=_before,
                    mode="ensure",
                )
            assert (
                'Found more than one line between boundaries "before" and "after"'
                in str(exc_info.value)
            )


@pytest.mark.parametrize(
    "content", ["/srv/pepper", "/srv/pepp*", "/srv/p.*", "/sr.*pe.*"]
)
def test_line_delete(tempfile_name, get_body, content):
    """
    Test for file.line for deletion of specific line
    :return:
    """
    file_content = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/pepper",
            "    - /srv/sugar",
        ]
    )
    file_modified = os.linesep.join(
        ["file_roots:", "  base:", "    - /srv/salt", "    - /srv/sugar"]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    files_fopen = mock_open(read_data=file_content)
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", files_fopen), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(tempfile_name, content=content, mode="delete")
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (
            writelines_content[0],
            expected,
        )


@pytest.mark.parametrize(
    "match", ["/srv/pepper", "/srv/pepp*", "/srv/p.*", "/sr.*pe.*"]
)
def test_line_replace(tempfile_name, get_body, match):
    """
    Test for file.line for replacement of specific line
    :return:
    """
    file_content = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/pepper",
            "    - /srv/sugar",
        ]
    )
    file_modified = os.linesep.join(
        [
            "file_roots:",
            "  base:",
            "    - /srv/salt",
            "    - /srv/natrium-chloride",
            "    - /srv/sugar",
        ]
    )

    isfile_mock = MagicMock(
        side_effect=lambda x: True if x == tempfile_name else DEFAULT
    )
    files_fopen = mock_open(read_data=file_content)
    with patch("os.path.isfile", isfile_mock), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ), patch("salt.utils.files.fopen", files_fopen), patch(
        "salt.utils.atomicfile.atomic_open", mock_open()
    ) as atomic_open_mock:
        filemod.line(
            tempfile_name,
            content="- /srv/natrium-chloride",
            match=match,
            mode="replace",
        )
        handles = atomic_open_mock.filehandles[tempfile_name]
        # We should only have opened the file once
        open_count = len(handles)
        assert open_count == 1, open_count
        # We should only have invoked .writelines() once...
        writelines_content = handles[0].writelines_calls
        writelines_count = len(writelines_content)
        assert writelines_count == 1, writelines_count
        # ... with the updated content
        expected = get_body(file_modified)
        assert writelines_content[0] == expected, (
            writelines_content[0],
            expected,
        )
