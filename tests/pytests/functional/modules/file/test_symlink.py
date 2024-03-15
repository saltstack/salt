"""
Tests for file.symlink function
"""

import os

import pytest

import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(scope="function")
def source():
    with pytest.helpers.temp_file(contents="Source content") as source:
        yield source


def test_symlink(file, source):
    """
    Test symlink with defaults
    """
    target = source.parent / "symlink.lnk"
    try:
        file.symlink(str(source), str(target))
        assert salt.utils.path.islink(str(target))
    finally:
        target.unlink()


def test_symlink_missing_src(file, source):
    """
    Test symlink when src is missing should still create the link
    """
    target = source.parent / "symlink.lnk"
    missing_source = source.parent / "missing.txt"
    try:
        file.symlink(str(missing_source), str(target))
        assert salt.utils.path.islink(str(target))
    finally:
        target.unlink()


def test_symlink_exists_same(file, source):
    """
    Test symlink with an existing symlink to the correct file
    Timestamps should not change
    """
    target = source.parent / "symlink.lnk"
    target.symlink_to(source)
    try:
        before_time = os.stat(str(target)).st_mtime
        ret = file.symlink(str(source), str(target))
        after_time = os.stat(str(target)).st_mtime
        assert before_time == after_time
        assert ret is True
    finally:
        target.unlink()


def test_symlink_exists_different(file, source):
    """
    Test symlink with an existing symlink to a different file
    Should throw a CommandExecutionError
    """
    dif_source = source.parent / "dif_source.txt"
    target = source.parent / "symlink.lnk"
    target.symlink_to(dif_source)
    try:
        with pytest.raises(CommandExecutionError) as exc:
            file.symlink(str(source), str(target))
        assert "Found existing symlink:" in exc.value.message
    finally:
        target.unlink()


def test_symlink_exists_file(file, source):
    """
    Test symlink when the existing file is not a link
    We don't do anything because we do not want to destroy any data
    Should throw a CommandExecutionError
    """
    with pytest.helpers.temp_file("symlink.txt", contents="Source content") as target:
        with pytest.raises(CommandExecutionError) as exc:
            file.symlink(str(source), str(target))
        assert "Existing path is not a symlink:" in exc.value.message


def test_symlink_exists_different_force(file, source):
    """
    Test symlink with an existing symlink to a different file with force=True
    Should destroy the existing symlink and generate a new one to the correct
    location
    """
    dif_source = source.parent / "dif_source.txt"
    target = source.parent / "symlink.lnk"
    target.symlink_to(dif_source)
    try:
        file.symlink(str(source), str(target), force=True)
        assert salt.utils.path.readlink(str(target)) == str(source)
    finally:
        target.unlink()


def test_symlink_target_relative_path(file, source):
    """
    Test symlink when the target file is a relative path
    Should throw a SaltInvocationError
    """
    target = f"..{os.path.sep}symlink.lnk"
    with pytest.raises(SaltInvocationError) as exc:
        file.symlink(str(source), str(target))
    assert "Link path must be absolute" in exc.value.message


def test_symlink_exists_different_atomic(file, source):
    """
    Test symlink with an existing symlink to a different file with atomic=True
    Should replace the existing symlink with a new one to the correct location
    """
    dif_source = source.parent / "dif_source.txt"
    target = source.parent / "symlink.lnk"
    target.symlink_to(dif_source)
    try:
        file.symlink(str(source), str(target), atomic=True)
        assert salt.utils.path.readlink(str(target)) == str(source)
    finally:
        target.unlink()
