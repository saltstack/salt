"""
integration tests for mac_xattr
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.skip_if_binaries_missing("xattr"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def xattr(modules):
    return modules.xattr


@pytest.fixture
def existing_file(tmp_path):
    fpath = tmp_path / "xattr_test_file.txt"
    fpath.touch()
    return fpath


@pytest.fixture
def non_existing_file(tmp_path):
    return tmp_path / "xattr_no_file"


def test_list_no_xattr(xattr, existing_file, non_existing_file):
    """
    Make sure there are no attributes
    """
    # Clear existing attributes
    ret = xattr.clear(existing_file)
    assert ret

    # Test no attributes
    ret = xattr.list(existing_file)
    assert ret == {}

    # Test file not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.list(non_existing_file)
        assert f"File not found: {non_existing_file}" in str(exc.value)


def test_write(xattr, existing_file, non_existing_file):
    """
    Write an attribute
    """
    # Clear existing attributes
    ret = xattr.clear(existing_file)
    assert ret

    # Write some attributes
    ret = xattr.write(existing_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(existing_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(existing_file, "crabby", "patty")
    assert ret

    # Test that they were actually added
    ret = xattr.list(existing_file)
    assert ret == {
        "spongebob": "squarepants",
        "squidward": "plankton",
        "crabby": "patty",
    }

    # Test file not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.write(non_existing_file, "patrick", "jellyfish")
        assert f"File not found: {non_existing_file}" in str(exc.value)


def test_read(xattr, existing_file, non_existing_file):
    """
    Test xattr.read
    """
    # Clear existing attributes
    ret = xattr.clear(existing_file)
    assert ret

    # Write an attribute
    ret = xattr.write(existing_file, "spongebob", "squarepants")
    assert ret

    # Read the attribute
    ret = xattr.read(existing_file, "spongebob")
    assert ret == "squarepants"

    # Test file not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.read(non_existing_file, "spongebob")
        assert f"File not found: {non_existing_file}" in str(exc.value)

    # Test attribute not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.read(existing_file, "patrick")
        assert "Attribute not found: patrick" in str(exc.value)


def test_delete(xattr, existing_file, non_existing_file):
    """
    Test xattr.delete
    """
    # Clear existing attributes
    ret = xattr.clear(existing_file)
    assert ret

    # Write some attributes
    ret = xattr.write(existing_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(existing_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(existing_file, "crabby", "patty")
    assert ret

    # Delete an attribute
    ret = xattr.delete(existing_file, "squidward")
    assert ret

    # Make sure it was actually deleted
    ret = xattr.list(existing_file)
    assert ret == {
        "spongebob": "squarepants",
        "crabby": "patty",
    }

    # Test file not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.delete(non_existing_file, "spongebob")
        assert f"File not found: {non_existing_file}" in str(exc.value)

    # Test attribute not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.delete(existing_file, "patrick")
        assert "Attribute not found: patrick" in str(exc.value)


def test_clear(xattr, existing_file, non_existing_file):
    """
    Test xattr.clear
    """
    # Clear existing attributes
    ret = xattr.clear(existing_file)
    assert ret

    # Write some attributes
    ret = xattr.write(existing_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(existing_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(existing_file, "crabby", "patty")
    assert ret

    # Test Clear
    ret = xattr.clear(existing_file)
    assert ret

    # Test file not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = xattr.clear(non_existing_file)
        assert f"File not found: {non_existing_file}" in str(exc.value)
