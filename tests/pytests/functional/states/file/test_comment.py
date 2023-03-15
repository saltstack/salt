"""
Tests for file.comment state function
"""
import re

import pytest

import salt.utils.files
from tests.support.helpers import dedent

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(states):
    return states.file


@pytest.fixture(scope="function")
def source():
    with pytest.helpers.temp_file(
        name="file.txt",
        contents=dedent(
            """
            things = stuff
            port = 5432                             # (change requires restart)
            # commented = something
            moar = things
            """
        ),
    ) as source:
        yield source


def test_issue_62121(file, source):
    """
    Test file.comment when the comment character is
    later in the line, after the text
    """
    regex = r"^port\s*=.+"
    reg_cmp = re.compile(regex, re.MULTILINE)
    cmt_regex = r"^#port\s*=.+"
    cmt_cmp = re.compile(cmt_regex, re.MULTILINE)

    with salt.utils.files.fopen(str(source)) as _fp:
        assert reg_cmp.findall(_fp.read())

    file.comment(name=str(source), regex=regex)

    with salt.utils.files.fopen(str(source)) as _fp:
        assert not reg_cmp.findall(_fp.read())
        _fp.seek(0)
        assert cmt_cmp.findall(_fp.read())


def test_comment(file, tmp_path):
    """
    file.comment
    """
    name = tmp_path / "testfile"
    # write a line to file
    name.write_text("comment_me")

    # Look for changes with test=True: return should be "None" at the first run
    ret = file.comment(name=str(name), regex="^comment", test=True)
    assert ret.result is None

    # comment once
    ret = file.comment(name=str(name), regex="^comment")
    assert ret.result is True
    # line is commented
    assert name.read_text().startswith("#comment")

    # comment twice
    ret = file.comment(name=str(name), regex="^comment")
    # result is still positive
    assert ret.result is True
    # line is still commented
    assert name.read_text().startswith("#comment")

    # Test previously commented file returns "True" now and not "None" with test=True
    ret = file.comment(name=str(name), regex="^comment", test=True)
    assert ret.result is True


def test_test_comment(file, tmp_path):
    """
    file.comment test interface
    """
    name = tmp_path / "testfile"
    # write a line to file
    name.write_text("comment_me")

    # Look for changes with test=True: return should be "None" at the first run
    ret = file.comment(name=str(name), regex="^comment", test=True)
    assert ret.result is None
    assert "#comment" not in name.read_text()


def test_issue_2401_file_comment(modules, tmp_path):
    # Get a path to the temporary file
    tmp_file = tmp_path / "issue-2041-comment.txt"
    tmp_file.write_text("hello\nworld\n")
    # create the sls template
    template_lines = [
        "{}:".format(tmp_file),
        "  file.comment:",
        "    - regex: ^world",
    ]
    template = "\n".join(template_lines)
    ret = modules.state.template_str(template)
    for state_run in ret:
        assert state_run.result is True
        assert "Pattern already commented" not in state_run.comment
        assert "Commented lines successfully" in state_run.comment

    # This next time, it is already commented.
    ret = modules.state.template_str(template)
    for state_run in ret:
        assert state_run.result is True
        assert "Pattern already commented" in state_run.comment
