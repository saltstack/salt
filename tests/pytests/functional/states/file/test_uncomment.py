import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.parametrize("test", (False, True))
def test_uncomment(file, tmp_path, test):
    """
    file.uncomment
    """
    name = tmp_path / "testfile"
    # write a line to file
    name.write_text("#comment_me")

    ret = file.uncomment(name=str(name), regex="^comment", test=test)
    if test is True:
        assert ret.result is None
        assert "#comment" in name.read_text()
    else:
        assert ret.result is True
        assert "#comment" not in name.read_text()
