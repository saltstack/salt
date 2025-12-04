"""
Unit Tests for functions located in salt/utils/files.py
"""

import copy
import io
import os

import pytest

import salt.utils.files
from tests.support.mock import MagicMock, mock_open, patch


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
        pytest.xfail(reason=f"inodes not supported in {tmp_path}")
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


def test_if_is_text_returns_true_to_text_files():
    """
    Test if text files are recognized as texts
    """
    mock_fp_ = MagicMock(spec=io.BufferedIOBase)

    # Text file with single byte characters
    file_content = b"This is a text file with all characters with one byte aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True

    # Text file with utf-8 multibyte characters (from Saltstack page in russian Wikipedia)
    file_content = b"\xd0\x94\xd0\xb2\xd1\x83\xd0\xbc\xd1\x8f \xd0\xb3\xd0\xbb\xd0\xb0\xd0\xb2\xd0\xbd\xd1\x8b\xd0\xbc\xd0\xb8 \xd0\xba\xd0\xbe\xd0\xbc\xd0\xbf\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd1\x82\xd0\xb0\xd0\xbc\xd0\xb8 SaltStack \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd1\x8e\xd1\x82\xd1\x81\xd1\x8f Salt Master (\xc2\xab\xd0\xbc\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80\xc2\xbb) \xd0\xb8 Salt Minion (\xc2\xab\xd1\x81\xd1\x82\xd0\xb0\xd0\xb2\xd0\xbb\xd0\xb5\xd0\xbd\xd0\xbd\xd0\xb8\xd0\xba\xc2\xbb, \xc2\xab\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb1\xd0\xbb\xd0\xb8\xd0\xb6\xd1\x91\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9\xc2\xbb, \xc2\xab\xd0\xbc\xd0\xb8\xd0\xbd\xd1\x8c\xd0\xbe\xd0\xbd\xc2\xbb). \xd0\x9c\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80 \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd0\xb5\xd1\x82\xd1\x81\xd1\x8f \xd1\x86\xd0\xb5\xd0\xbd\xd1\x82\xd1\x80\xd0\xb0\xd0\xbb\xd1\x8c\xd0\xbd\xd0\xbe\xd0\xb9 "
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True

    # Text file with truncated utf-8 multibyte character (from Saltstack page in russian Wikipedia)
    file_content = b"\xd0\x94\xd0\xb2\xd1\x83\xd0\xbc\xd1\x8f \xd0\xb3\xd0\xbb\xd0\xb0\xd0\xb2\xd0\xbd\xd1\x8b\xd0\xbc\xd0\xb8 \xd0\xba\xd0\xbe\xd0\xbc\xd0\xbf\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd1\x82\xd0\xb0\xd0\xbc\xd0\xb8 SaltStack \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd1\x8e\xd1\x82\xd1\x81\xd1\x8f Salt Master (\xc2\xab\xd0\xbc\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80\xc2\xbb) \xd0\xb8 Salt Minion (\xc2\xab\xd1\x81\xd1\x82\xd0\xb0\xd0\xb2\xd0\xbb\xd0\xb5\xd0\xbd\xd0\xbd\xd0\xb8\xd0\xba\xc2\xbb, \xc2\xab\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb1\xd0\xbb\xd0\xb8\xd0\xb6\xd1\x91\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9\xc2\xbb, \xc2\xab\xd0\xbc\xd0\xb8\xd0\xbd\xd1\x8c\xd0\xbe\xd0\xbd\xc2\xbb). \xd0\x9c\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80 \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd0\xb5\xd1\x82\xd1\x81\xd1\x8f \xd1\x86\xd0\xb5\xd0\xbd\xd1\x82\xd1\x80\xd0\xb0\xd0\xbb\xd1\x8c\xd0\xbd\xd0\xbe  \xd0"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True

    # Text file with invalid utf-8 multibyte character
    file_content = b"This is a text file with a invalid multibyte character at middle \xc3aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True

    # Empty file
    file_content = b""
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True

    # File with less than 30% of binary data, should be detected as text
    file_content = b"This is a file with less than 30% of binary data. Should be detected as text aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is True


def test_if_is_text_returns_false_for_binary_files():
    """
    Test if binary files are not recognized as texts
    """
    mock_fp_ = MagicMock(spec=io.BufferedIOBase)

    # First bytes from /bin/ls
    file_content = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00>\x00\x01\x00\x00\x00pR@\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\xd8\x16\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x008\x00\r\x00@\x00\x1e\x00\x1d\x00\x06\x00\x00\x00\x04\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00@\x00@\x00\x00\x00\x00\x00@\x00@\x00\x00\x00\x00\x00\xd8\x02\x00\x00\x00\x00\x00\x00\xd8\x02\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00\x18\x03\x00\x00\x00\x00\x00\x00\x18\x03@\x00\x00\x00\x00\x00\x18\x03@\x00\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00$\x00\x00\x00\x00\x00\x00\x00$\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x05\x00\x00\x00\x000\x00\x00\x00\x00\x00\x00\x000@\x00\x00\x00\x00"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is False

    # First bytes from MariaDB ib_logfile
    file_content = b"Phys\x00\x00\x00\x00\x00\x00\x00\x00\x00\x000\x00MariaDB 11.4.5\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is False

    # First bytes from PNG file
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\\r\xa8f\x00\x00\x01|iCCPicc\x00\x00(\x91}\x91=H\xc3@\x1c\xc5_SKE*\x0evPq\xc8P\x9d,\x8a\x8a:j\x15\x8aP!\xd4\n\xad:\x98\\\xfa\x05M\x1a\x92\x14\x17G\xc1\xb5\xe0\xe0\xc7b\xd5\xc1\xc5YW\x07WA\x10\xfc\x00qrtRt\x91\x12\xff\x97\x14Z\xc4zp\xdc\x8fw\xf7\x1ew\xef\x00\xa1Vb\x9a\xd51\x06h\xbam&\xe311\x9dY\x15\x83\xaf\xf0\xa3\x1f\x01LcTf\x961'I\t\xb4\x1d_\xf7\xf0\xf1\xf5.\xca\xb3\xda\x9f\xfbst\xabY\x8b\x01>\x91x\x96\x19\xa6M\xbcA<\xb5i\x1b\x9c\xf7\x89\xc3\xac \xab\xc4\xe7\xc4#&]\x90\xf8\x91\xeb\x8a\xc7o\x9c\xf3.\x0b<3l\xa6\x92\xf3\xc4ab1\xdf\xc2J\x0b\xb3\x82\xa9\x11O\x12GTM\xa7|!\xed\xb1\xcay\x8b\xb3V\xaa\xb0\xc6=\xf9"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is False

    # File with \x00 , should be detected as not text
    file_content = b"This is a file with \x00 inside. Should be detected as not text by is_text aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is False

    # File with more than 30% of binary data, should be detected as not text
    file_content = b"This is a file with more than 30% of binary data. Should be detected as not text aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    mock_fp_.read.return_value = file_content
    result = salt.utils.files.is_text(mock_fp_)
    assert result is False


def test_if_is_binary_returns_true_for_binary_files():
    """
    Test if binary files are detected as binary
    """
    # First bytes from PNG file
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\\r\xa8f\x00\x00\x01|iCCPicc\x00\x00(\x91}\x91=H\xc3@\x1c\xc5_SKE*\x0evPq\xc8P\x9d,\x8a\x8a:j\x15\x8aP!\xd4\n\xad:\x98\\\xfa\x05M\x1a\x92\x14\x17G\xc1\xb5\xe0\xe0\xc7b\xd5\xc1\xc5YW\x07WA\x10\xfc\x00qrtRt\x91\x12\xff\x97\x14Z\xc4zp\xdc\x8fw\xf7\x1ew\xef\x00\xa1Vb\x9a\xd51\x06h\xbam&\xe311\x9dY\x15\x83\xaf\xf0\xa3\x1f\x01LcTf\x961'I\t\xb4\x1d_\xf7\xf0\xf1\xf5.\xca\xb3\xda\x9f\xfbst\xabY\x8b\x01>\x91x\x96\x19\xa6M\xbcA<\xb5i\x1b\x9c\xf7\x89\xc3\xac \xab\xc4\xe7\xc4#&]\x90\xf8\x91\xeb\x8a\xc7o\x9c\xf3.\x0b<3l\xa6\x92\xf3\xc4ab1\xdf\xc2J\x0b\xb3\x82\xa9\x11O\x12GTM\xa7|!\xed\xb1\xcay\x8b\xb3V\xaa\xb0\xc6=\xf9"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is True

    # First bytes from MariaDB ib_logfile
    file_content = b"Phys\x00\x00\x00\x00\x00\x00\x00\x00\x00\x000\x00MariaDB 11.4.5\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is True

    # First bytes from /bin/ls
    file_content = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00>\x00\x01\x00\x00\x00pR@\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\xd8\x16\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x008\x00\r\x00@\x00\x1e\x00\x1d\x00\x06\x00\x00\x00\x04\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00@\x00@\x00\x00\x00\x00\x00@\x00@\x00\x00\x00\x00\x00\xd8\x02\x00\x00\x00\x00\x00\x00\xd8\x02\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x04\x00\x00\x00\x18\x03\x00\x00\x00\x00\x00\x00\x18\x03@\x00\x00\x00\x00\x00\x18\x03@\x00\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00$\x00\x00\x00\x00\x00\x00\x00$\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x05\x00\x00\x00\x000\x00\x00\x00\x00\x00\x00\x000@\x00\x00\x00\x00"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is True

    # File with too much binary data. Should be detected as binary
    file_content = b"This is a file with more than 30% of binary data. Should be detected as not text aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is True


def test_is_binary_returns_false_for_text_files():
    """
    Test if text files are not detected as binary
    """
    # Text file with single byte characters
    file_content = b"This is a text file with all characters with one byte aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is False

    # Text file with truncated multibyte utf-8 character at end
    file_content = b"This is a text file with a truncated multibyte utf-8 character at end aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xd0"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is False

    # Text file with valid multibyte utf-8 character at end
    file_content = b"This is a text file with a valid multibyte utf-8 character aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xc3\x87"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is False

    # Text file with utf-8 multibyte characters (from Saltstack page in russian Wikipedia)
    file_content = b"\xd0\x94\xd0\xb2\xd1\x83\xd0\xbc\xd1\x8f \xd0\xb3\xd0\xbb\xd0\xb0\xd0\xb2\xd0\xbd\xd1\x8b\xd0\xbc\xd0\xb8 \xd0\xba\xd0\xbe\xd0\xbc\xd0\xbf\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd1\x82\xd0\xb0\xd0\xbc\xd0\xb8 SaltStack \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd1\x8e\xd1\x82\xd1\x81\xd1\x8f Salt Master (\xc2\xab\xd0\xbc\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80\xc2\xbb) \xd0\xb8 Salt Minion (\xc2\xab\xd1\x81\xd1\x82\xd0\xb0\xd0\xb2\xd0\xbb\xd0\xb5\xd0\xbd\xd0\xbd\xd0\xb8\xd0\xba\xc2\xbb, \xc2\xab\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb1\xd0\xbb\xd0\xb8\xd0\xb6\xd1\x91\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9\xc2\xbb, \xc2\xab\xd0\xbc\xd0\xb8\xd0\xbd\xd1\x8c\xd0\xbe\xd0\xbd\xc2\xbb). \xd0\x9c\xd0\xb0\xd1\x81\xd1\x82\xd0\xb5\xd1\x80 \xd1\x8f\xd0\xb2\xd0\xbb\xd1\x8f\xd0\xb5\xd1\x82\xd1\x81\xd1\x8f \xd1\x86\xd0\xb5\xd0\xbd\xd1\x82\xd1\x80\xd0\xb0\xd0\xbb\xd1\x8c\xd0\xbd\xd0\xbe\xd0\xb9 "
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is False

    # File with less than 30% of binary data, should be detected as text
    file_content = b"This is a file with less than 30% of binary data. Should be detected as text aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    readfile = mock_open(read_data=file_content)
    with patch("os.path.isfile", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", readfile
    ):
        result = salt.utils.files.is_binary("/fake/file")
        assert result is False
