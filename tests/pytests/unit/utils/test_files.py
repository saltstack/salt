"""
Unit Tests for functions located in salt/utils/files.py
"""


import copy
import io
import os

import pytest

import salt.utils.files
from tests.support.mock import MagicMock, patch


def test_safe_rm():
    with patch("os.remove") as os_remove_mock:
        salt.utils.files.safe_rm("dummy_tgt")
        assert os_remove_mock.called is True


def test_safe_rm_exceptions(tmp_path):
    assert (
        salt.utils.files.safe_rm(str(tmp_path / "no_way_this_is_a_file_nope.sh"))
        is None
    )


def test_safe_walk_symlink_recursion(tmp_path):
    if tmp_path.stat().st_ino == 0:
        pytest.xfail(reason="inodes not supported in {}".format(tmp_path))
    tmp_path = str(tmp_path)

    os.mkdir(os.path.join(tmp_path, "fax"))
    os.makedirs(os.path.join(tmp_path, "foo", "bar"))
    os.symlink(os.path.join("..", ".."), os.path.join(tmp_path, "foo", "bar", "baz"))
    os.symlink("foo", os.path.join(tmp_path, "root"))
    expected = [
        (os.path.join(tmp_path, "root"), ["bar"], []),
        (os.path.join(tmp_path, "root", "bar"), ["baz"], []),
        (os.path.join(tmp_path, "root", "bar", "baz"), ["fax", "foo", "root"], []),
        (os.path.join(tmp_path, "root", "bar", "baz", "fax"), [], []),
    ]
    paths = []
    for root, dirs, names in salt.utils.files.safe_walk(os.path.join(tmp_path, "root")):
        paths.append((root, sorted(dirs), names))
    assert paths == expected


def test_fopen_with_disallowed_fds():
    """
    This is safe to have as a unit test since we aren't going to actually
    try to read or write. We want to ensure that we are raising a
    TypeError. Python 3's open() builtin will treat the booleans as file
    descriptor numbers and try to open stdin/stdout. We also want to test
    fd 2 which is stderr.
    """
    for invalid_fn in (False, True, 0, 1, 2):
        try:
            with salt.utils.files.fopen(invalid_fn):
                pass
        except TypeError:
            # This is expected. We aren't using an assertRaises here
            # because we want to ensure that if we did somehow open the
            # filehandle, that it doesn't remain open.
            pass
        else:
            # We probably won't even get this far if we actually opened
            # stdin/stdout as a file descriptor. It is likely to cause the
            # integration suite to die since, news flash, closing
            # stdin/stdout/stderr is usually not a wise thing to do in the
            # middle of a program's execution.
            pytest.fail(
                "fopen() should have been prevented from opening a file "
                "using {} as the filename".format(invalid_fn)
            )


def test_fopen_binary_line_buffering(tmp_path):
    tmp_file = os.path.join(tmp_path, "foobar")
    with patch("builtins.open") as open_mock, patch(
        "salt.utils.files.is_fcntl_available", MagicMock(return_value=False)
    ):
        salt.utils.files.fopen(os.path.join(tmp_path, "foobar"), mode="b", buffering=1)
        assert open_mock.called
        assert open_mock.call_args[1]["buffering"] == io.DEFAULT_BUFFER_SIZE


def _create_temp_structure(temp_directory, structure):
    for folder, files in structure.items():
        current_directory = os.path.join(temp_directory, folder)
        os.makedirs(current_directory)
        for name, content in files.items():
            path = os.path.join(temp_directory, folder, name)
            with salt.utils.files.fopen(path, "w+") as fh:
                fh.write(content)


def _validate_folder_structure_and_contents(target_directory, desired_structure):
    for folder, files in desired_structure.items():
        for name, content in files.items():
            path = os.path.join(target_directory, folder, name)
            with salt.utils.files.fopen(path) as fh:
                assert fh.read().strip() == content


def test_recursive_copy(tmp_path):
    src = str(tmp_path / "src")
    dest = str(tmp_path / "dest")
    src_structure = {
        "foo": {"foofile.txt": "fooSTRUCTURE"},
        "bar": {"barfile.txt": "barSTRUCTURE"},
    }
    dest_structure = {
        "foo": {"foo.txt": "fooTARGET_STRUCTURE"},
        "baz": {"baz.txt": "bazTARGET_STRUCTURE"},
    }

    # Create the file structures in both src and dest dirs
    _create_temp_structure(src, src_structure)
    _create_temp_structure(dest, dest_structure)

    # Perform the recursive copy
    salt.utils.files.recursive_copy(src, dest)

    # Confirm results match expected results
    desired_structure = copy.copy(dest_structure)
    desired_structure.update(src_structure)
    _validate_folder_structure_and_contents(dest, desired_structure)


@pytest.mark.skip_unless_on_windows
def test_case_sensitive_filesystem_win():
    """
    Test case insensitivity on Windows.
    """
    result = salt.utils.files.case_insensitive_filesystem()
    assert result is True


@pytest.mark.skip_unless_on_linux
def test_case_sensitive_filesystem_lin():
    """
    Test case insensitivity on Linux.
    """
    result = salt.utils.files.case_insensitive_filesystem()
    assert result is False


@pytest.mark.skip_unless_on_darwin
def test_case_sensitive_filesystem_dar():
    """
    Test case insensitivity on Darwin.
    """
    result = salt.utils.files.case_insensitive_filesystem()
    assert result is True
