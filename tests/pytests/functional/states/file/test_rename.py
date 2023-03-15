"""
Tests for file.rename state function
"""
# nox -e pytest-zeromq-3.8(coverage=False) -- -vvv --run-slow --run-destructive tests\pytests\functional\states\file\test_rename.py

import pytest

import salt.utils.path

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(states):
    return states.file


@pytest.fixture(scope="function")
def source():
    with pytest.helpers.temp_file(
        name="old_name.txt", contents="Source content"
    ) as source:
        yield source


def test_defaults(file, source):
    """
    Test file.rename with defaults
    """
    new_name = source.parent / "new_name.txt"
    try:
        file.rename(name=str(new_name), source=str(source))
        assert new_name.exists()
        assert not source.exists()
    finally:
        new_name.unlink()


def test_relative_name(file):
    """
    Test file.rename when name is a relative path
    """
    result = file.rename(name="..\\rel\\path\\test", source=str(source))
    assert "is not an absolute path" in result.filtered["comment"]
    assert result.filtered["result"] is False


def test_missing_source(file, source):
    """
    Test file.rename with the source file is missing
    """
    new_name = source.parent / "new_name.txt"
    missing_name = source.parent / "missing.txt"
    result = file.rename(name=str(new_name), source=str(missing_name))
    assert "has already been moved out of place" in result.filtered["comment"]
    assert result.filtered["result"] is True


def test_target_exists(file, source):
    """
    Test file.rename when there is an existing file with the new name
    """
    new_name = source.parent / "new_name.txt"
    new_name.write_text("existing file")
    try:
        result = file.rename(name=str(new_name), source=str(source))
        assert "exists and will not be overwritten" in result.filtered["comment"]
        assert result.filtered["result"] is True
    finally:
        new_name.unlink()


def test_target_exists_force(file, source):
    """
    Test file.rename when there is an existing file with the new name and
    force=True
    """
    new_name = source.parent / "new_name.txt"
    new_name.write_text("existing file")
    try:
        file.rename(name=str(new_name), source=str(source), force=True)
        assert new_name.exists()
        assert not source.exists()
        assert new_name.read_text() == "Source content"
    finally:
        new_name.unlink()


def test_test_is_true(file, source):
    new_name = source.parent / "new_name.txt"
    result = file.rename(name=str(new_name), source=str(source), test=True)
    assert "is set to be moved to" in result.filtered["comment"]
    assert result.filtered["result"] is None


def test_missing_dirs(file, source):
    new_name = source.parent / "missing_subdir" / "new_name.txt"
    result = file.rename(name=str(new_name), source=str(source))
    assert "is not present" in result.filtered["comment"]
    assert result.filtered["result"] is False


def test_missing_dirs_makedirs(file, source):
    new_name = source.parent / "missing_subdir" / "new_name.txt"
    try:
        file.rename(name=str(new_name), source=str(source), makedirs=True)
        assert new_name.exists()
        assert not source.exists()
    finally:
        new_name.unlink()
        new_name.parent.rmdir()


def test_source_is_link(file, source):
    link_source = source.parent / "link_source.lnk"
    link_source.symlink_to(source)
    new_name = source.parent / "new_name.lnk"
    try:
        file.rename(name=str(new_name), source=str(link_source))
        assert new_name.exists()
        assert new_name.is_symlink()
        assert salt.utils.path.readlink(str(new_name)) == str(source)
        assert new_name.read_text() == "Source content"
        assert not link_source.exists()
    finally:
        new_name.unlink()
