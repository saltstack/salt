import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_issue_48557(file, tmp_path):
    tempfile = tmp_path / "temp_file_issue_48557"
    contents = "test1\ntest2\ntest3\n"
    expected = "test1\ntest2\ntest4\ntest3\n"
    tempfile.write_text(contents)
    ret = file.line(name=str(tempfile), after="test2", mode="insert", content="test4")
    assert ret.result is True
    assert tempfile.read_text() == expected
