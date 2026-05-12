"""
Tests for file.touch function
"""

import pytest

from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


def test_touch(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target))
    assert target.exists()


def test_touch_error_atime(file, tmp_path):
    """
    Test touch with non int input
    """
    target = tmp_path / "test.file"
    with pytest.raises(SaltInvocationError) as exc:
        file.touch(str(target), atime="string")
    assert "atime and mtime must be integers" in exc.value.message


def test_touch_error_mtime(file, tmp_path):
    """
    Test touch with non int input
    """
    target = tmp_path / "test.file"
    with pytest.raises(SaltInvocationError) as exc:
        file.touch(str(target), mtime="string")
    assert "atime and mtime must be integers" in exc.value.message


def test_touch_atime(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target), atime=123)
    assert target.stat().st_atime == 123


def test_touch_atime_zero(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target), atime=0)
    assert target.stat().st_atime == 0


def test_touch_mtime(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target), mtime=234)
    assert target.stat().st_mtime == 234


def test_touch_mtime_zero(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target), mtime=0)
    assert target.stat().st_mtime == 0


def test_touch_atime_mtime(file, tmp_path):
    """
    Test touch with defaults
    """
    target = tmp_path / "test.file"
    file.touch(str(target), atime=456, mtime=789)
    assert target.stat().st_atime == 456
    assert target.stat().st_mtime == 789
