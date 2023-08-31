import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
]

IS_WINDOWS = salt.utils.platform.is_windows()


def test_absent_file(file, tmp_path):
    """
    file.absent
    """
    name = tmp_path / "file_to_kill"
    name.write_text("killme")
    ret = file.absent(name=str(name))
    assert ret.result is True
    assert not name.is_file()


def test_absent_dir(file, tmp_path):
    """
    file.absent
    """
    name = tmp_path / "dir_to_kill"
    name.mkdir(exist_ok=True)
    ret = file.absent(name=str(name))
    assert ret.result is True
    assert not name.is_dir()


def test_absent_link(file, tmp_path):
    """
    file.absent
    """
    name = tmp_path / "link_to_kill"
    tgt = tmp_path / "link_to_kill.tgt"

    tgt.symlink_to(name, target_is_directory=IS_WINDOWS)

    ret = file.absent(name=str(name))

    assert ret.result is True
    assert not name.exists()
    assert not name.is_symlink()


def test_test_absent(file, tmp_path):
    """
    file.absent test interface
    """
    name = tmp_path / "testfile"
    name.write_text("killme")
    ret = file.absent(test=True, name=str(name))
    assert ret.result is None
    assert name.is_file()
