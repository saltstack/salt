import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.parametrize("test", (True, False))
def test_touch(file, tmp_path, test):
    """
    file.touch
    """
    name = tmp_path / "testfile"
    ret = file.touch(name=str(name), test=test)
    if test is True:
        assert ret.result is None
        assert name.is_file() is False
    else:
        assert ret.result is True
        assert name.is_file()


def test_touch_directory(file, tmp_path):
    """
    file.touch a directory
    """
    name = tmp_path / "touch_test_dir"
    name.mkdir()
    ret = file.touch(name=str(name))
    assert ret.result is True
    assert name.is_dir()
