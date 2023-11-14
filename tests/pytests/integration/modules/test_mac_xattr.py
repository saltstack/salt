"""
integration tests for mac_xattr
"""

import os

import pytest

pytestmark = [
    pytest.mark.skip_if_binaries_missing("xattr"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli, tmp_path):
    test_file = tmp_path / "xattr_test_file.txt"
    no_file = tmp_path / "xattr_no_file.txt"

    salt_call_cli.run("file.touch", test_file)

    try:
        yield test_file, no_file
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


def test_list_no_xattr(salt_call_cli, setup_teardown_vars):
    """
    Make sure there are no attributes
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Test no attributes
    ret = salt_call_cli.run("xattr.list", test_file)
    assert ret.data == {}

    # Test file not found
    ret = salt_call_cli.run("xattr.list", no_file)
    assert ret.stderr == f"ERROR: File not found: {no_file}"


def test_write(salt_call_cli, setup_teardown_vars):
    """
    Write an attribute
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Write some attributes
    ret = salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "crabby", "patty")
    assert ret.data

    # Test that they were actually added
    ret = salt_call_cli.run("xattr.list", test_file)
    assert ret.data == {
        "spongebob": "squarepants",
        "squidward": "plankton",
        "crabby": "patty",
    }

    # Test file not found
    ret = salt_call_cli.run("xattr.write", no_file, "patrick", "jellyfish")
    assert ret.stderr == f"ERROR: File not found: {no_file}"


def test_read(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.read
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Write an attribute
    ret = salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert ret.data

    # Read the attribute
    ret = salt_call_cli.run("xattr.read", test_file, "spongebob")
    assert ret.data == "squarepants"

    # Test file not found
    ret = salt_call_cli.run("xattr.read", no_file, "spongebob")
    assert ret.stderr == f"ERROR: File not found: {no_file}"

    # Test attribute not found
    ret = salt_call_cli.run("xattr.read", test_file, "patrick")
    assert ret.stderr == "ERROR: Attribute not found: patrick"


def test_delete(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.delete
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Write some attributes
    ret = salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "crabby", "patty")
    assert ret.data

    # Delete an attribute
    ret = salt_call_cli.run("xattr.delete", test_file, "squidward")
    assert ret.data

    # Make sure it was actually deleted
    ret = salt_call_cli.run("xattr.list", test_file)
    assert ret.data == {
        "spongebob": "squarepants",
        "crabby": "patty",
    }

    # Test file not found
    ret = salt_call_cli.run("xattr.delete", no_file, "spongebob")
    assert ret.stderr == f"ERROR: File not found: {no_file}"

    # Test attribute not found
    ret = salt_call_cli.run("xattr.delete", test_file, "patrick")
    assert ret.stderr == "ERROR: Attribute not found: patrick"


def test_clear(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.clear
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Write some attributes
    ret = salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert ret.data

    ret = salt_call_cli.run("xattr.write", test_file, "crabby", "patty")
    assert ret.data

    # Test Clear
    ret = salt_call_cli.run("xattr.clear", test_file)
    assert ret.data

    # Test file not found
    ret = salt_call_cli.run("xattr.clear", no_file)
    assert ret.stderr == f"ERROR: File not found: {no_file}"
