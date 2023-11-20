"""
integration tests for mac_xattr
"""

import pytest

pytestmark = [
    pytest.mark.skip_if_binaries_missing("xattr"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def xttr(modules):
    return modules.xttr


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, tmp_path):
    test_file = tmp_path / "xattr_test_file.txt"
    no_file = str(tmp_path / "xattr_no_file.txt")

    test_file.touch()

    try:
        yield str(test_file), no_file
    finally:
        if test_file.exists():
            test_file.unlink()


def test_list_no_xattr(xattr, setup_teardown_vars):
    """
    Make sure there are no attributes
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = xattr.clear(test_file)
    assert ret

    # Test no attributes
    ret = xattr.list(test_file)
    assert ret == {}

    # Test file not found
    ret = xattr.list(no_file)
    assert f"File not found: {no_file}" in ret


def test_write(xattr, setup_teardown_vars):
    """
    Write an attribute
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = xattr.clear(test_file)
    assert ret

    # Write some attributes
    ret = xattr.write(test_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(test_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(test_file, "crabby", "patty")
    assert ret

    # Test that they were actually added
    ret = xattr.list(test_file)
    assert ret == {
        "spongebob": "squarepants",
        "squidward": "plankton",
        "crabby": "patty",
    }

    # Test file not found
    ret = xattr.write(no_file, "patrick", "jellyfish")
    assert f"File not found: {no_file}" in ret


def test_read(xattr, setup_teardown_vars):
    """
    Test xattr.read
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = xattr.clear(test_file)
    assert ret

    # Write an attribute
    ret = xattr.write(test_file, "spongebob", "squarepants")
    assert ret

    # Read the attribute
    ret = xattr.read(test_file, "spongebob")
    assert ret == "squarepants"

    # Test file not found
    ret = xattr.read(no_file, "spongebob")
    assert f"File not found: {no_file}" in ret

    # Test attribute not found
    ret = xattr.read(test_file, "patrick")
    assert "Attribute not found: patrick" in ret


def test_delete(xattr, setup_teardown_vars):
    """
    Test xattr.delete
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = xattr.clear(test_file)
    assert ret

    # Write some attributes
    ret = xattr.write(test_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(test_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(test_file, "crabby", "patty")
    assert ret

    # Delete an attribute
    ret = xattr.delete(test_file, "squidward")
    assert ret

    # Make sure it was actually deleted
    ret = xattr.list(test_file)
    assert ret == {
        "spongebob": "squarepants",
        "crabby": "patty",
    }

    # Test file not found
    ret = xattr.delete(no_file, "spongebob")
    assert f"File not found: {no_file}" in ret

    # Test attribute not found
    ret = xattr.delete(test_file, "patrick")
    assert "Attribute not found: patrick" in ret


def test_clear(xattr, setup_teardown_vars):
    """
    Test xattr.clear
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = xattr.clear(test_file)
    assert ret

    # Write some attributes
    ret = xattr.write(test_file, "spongebob", "squarepants")
    assert ret

    ret = xattr.write(test_file, "squidward", "plankton")
    assert ret

    ret = xattr.write(test_file, "crabby", "patty")
    assert ret

    # Test Clear
    ret = xattr.clear(test_file)
    assert ret

    # Test file not found
    ret = xattr.clear(no_file)
    assert f"File not found: {no_file}" in ret
