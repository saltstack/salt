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
    assert salt_call_cli.run("xattr.clear", test_file)

    # Test no attributes
    assert salt_call_cli.run("xattr.list", test_file) == {}

    # Test file not found
    assert (
        salt_call_cli.run("xattr.list", no_file) == f"ERROR: File not found: {no_file}"
    )


def test_write(salt_call_cli, setup_teardown_vars):
    """
    Write an attribute
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    assert salt_call_cli.run("xattr.clear", test_file)

    # Write some attributes
    assert salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert salt_call_cli.run("xattr.write", test_file, "crabby", "patty")

    # Test that they were actually added
    assert salt_call_cli.run("xattr.list", test_file) == {
        "spongebob": "squarepants",
        "squidward": "plankton",
        "crabby": "patty",
    }

    # Test file not found
    assert (
        salt_call_cli.run("xattr.write", no_file, "patrick", "jellyfish")
        == f"ERROR: File not found: {no_file}"
    )


def test_read(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.read
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    assert salt_call_cli.run("xattr.clear", test_file)

    # Write an attribute
    assert salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")

    # Read the attribute
    assert salt_call_cli.run("xattr.read", test_file, "spongebob") == "squarepants"

    # Test file not found
    assert (
        salt_call_cli.run("xattr.read", no_file, "spongebob")
        == f"ERROR: File not found: {no_file}"
    )

    # Test attribute not found
    assert (
        salt_call_cli.run("xattr.read", test_file, "patrick")
        == "ERROR: Attribute not found: patrick"
    )


def test_delete(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.delete
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    assert salt_call_cli.run("xattr.clear", test_file)

    # Write some attributes
    assert salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert salt_call_cli.run("xattr.write", test_file, "crabby", "patty")

    # Delete an attribute
    assert salt_call_cli.run("xattr.delete", test_file, "squidward")

    # Make sure it was actually deleted
    assert salt_call_cli.run("xattr.list", test_file) == {
        "spongebob": "squarepants",
        "crabby": "patty",
    }

    # Test file not found
    assert (
        salt_call_cli.run("xattr.delete", no_file, "spongebob")
        == f"ERROR: File not found: {no_file}"
    )

    # Test attribute not found
    assert (
        salt_call_cli.run("xattr.delete", test_file, "patrick")
        == "ERROR: Attribute not found: patrick"
    )


def test_clear(salt_call_cli, setup_teardown_vars):
    """
    Test xattr.clear
    """
    test_file = setup_teardown_vars[0]
    no_file = setup_teardown_vars[1]

    # Clear existing attributes
    assert salt_call_cli.run("xattr.clear", test_file)

    # Write some attributes
    assert salt_call_cli.run("xattr.write", test_file, "spongebob", "squarepants")
    assert salt_call_cli.run("xattr.write", test_file, "squidward", "plankton")
    assert salt_call_cli.run("xattr.write", test_file, "crabby", "patty")

    # Test Clear
    assert salt_call_cli.run("xattr.clear", test_file)

    # Test file not found
    assert (
        salt_call_cli.run("xattr.clear", no_file) == f"ERROR: File not found: {no_file}"
    )
