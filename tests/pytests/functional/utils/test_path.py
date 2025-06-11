"""
Test the salt.utils.path Salt Util
"""

import subprocess

import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def symlink_file(tmp_path):
    target = tmp_path / "tgt_symlink"
    target.write_text("this is the symlink target")
    symlink = tmp_path / "symlink"
    symlink.symlink_to(target)
    assert symlink.is_symlink()
    assert symlink.read_text() == "this is the symlink target"
    yield symlink


@pytest.fixture
def symlink_dir(tmp_path):
    target = tmp_path / "tgt_symlink"
    target.mkdir()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(target)
    assert symlink.is_symlink()
    yield symlink


@pytest.fixture
def junction(tmp_path):
    """
    Create a directory and a junction to that directory.
    """
    target = tmp_path / "tgt_junction"
    target.mkdir()
    junction = tmp_path / "junction"
    cmd = ["cmd", "/c", "mklink", "/j", str(junction), str(target)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert junction.is_symlink() is False
    yield junction


def test_islink_symlink_file(symlink_file):
    assert salt.utils.path.islink(str(symlink_file))


def test_islink_symlink_dir(symlink_dir):
    assert salt.utils.path.islink(str(symlink_dir))


@pytest.mark.skip_unless_on_windows
def test_islink_junction(junction):
    """
    Junctions are only a thing on Windows, but they are the equivalent of a
    symlink. They just apply to directories
    """
    assert salt.utils.path.islink(str(junction))
