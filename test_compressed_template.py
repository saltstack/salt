"""
Test template for archive.compressed function
=============================================

This template shows how to write unit tests for the compressed function.
You should copy these tests into tests/pytests/unit/states/test_archive.py

The tests mock Salt's execution modules (__salt__) and file operations
to verify the compressed function works correctly without actually creating files.
"""

import pytest
from unittest.mock import MagicMock, patch


# Example 1: Test successful ZIP creation
def test_compressed_zip_success():
    """
    Test that archive.compressed creates a ZIP file successfully
    """
    # Mock the archive.zip execution module to return success
    zip_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)  # Archive doesn't exist yet
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        # Call the compressed function
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file1.txt", "/tmp/file2.txt"],
            archive_format="zip",
        )
        
        # Verify the execution module was called correctly
        zip_mock.assert_called_once_with(
            "/tmp/test.zip",
            sources=["/tmp/file1.txt", "/tmp/file2.txt"],
            cwd=None,
        )
        
        # Verify the return structure
        assert ret["name"] == "/tmp/test.zip"
        assert ret["result"] is True
        assert ret["changes"] == {"created": "/tmp/test.zip"}
        assert "Successfully created" in ret["comment"]


# Example 2: Test successful TAR.GZ creation
def test_compressed_tar_gz_success():
    """
    Test that archive.compressed creates a TAR.GZ file successfully
    """
    tar_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.tar.gz",
            sources=["/tmp/dir1", "/tmp/dir2"],
            archive_format="tar",
            compression="gzip",
        )
        
        # Verify tar was called with compression flag
        tar_mock.assert_called_once_with(
            "czf",
            "/tmp/test.tar.gz",
            sources=["/tmp/dir1", "/tmp/dir2"],
            cwd=None,
            template=None,
            user=None,
            group=None,
        )
        
        assert ret["result"] is True
        assert ret["changes"] == {"created": "/tmp/test.tar.gz"}


# Example 3: Test tar without compression
def test_compressed_tar_no_compression():
    """
    Test that archive.compressed creates a plain TAR file
    """
    tar_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.tar",
            sources=["/tmp/file.txt"],
            archive_format="tar",
        )
        
        # Verify tar was called with 'cf' (no compression flag)
        tar_mock.assert_called_once_with(
            "cf",
            "/tmp/test.tar",
            sources=["/tmp/file.txt"],
            cwd=None,
            template=None,
            user=None,
            group=None,
        )
        
        assert ret["result"] is True


# Example 4: Test tar.bz2 compression
def test_compressed_tar_bz2():
    """
    Test that archive.compressed creates a TAR.BZ2 file
    """
    tar_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.tar.bz2",
            sources=["/tmp/data"],
            archive_format="tar",
            compression="bzip2",
        )
        
        # Verify 'j' flag for bzip2
        tar_mock.assert_called_once_with(
            "cjf",
            "/tmp/test.tar.bz2",
            sources=["/tmp/data"],
            cwd=None,
            template=None,
            user=None,
            group=None,
        )
        
        assert ret["result"] is True


# Example 5: Test tar.xz compression
def test_compressed_tar_xz():
    """
    Test that archive.compressed creates a TAR.XZ file
    """
    tar_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.tar.xz",
            sources=["/tmp/data"],
            archive_format="tar",
            compression="xz",
        )
        
        # Verify 'J' flag for xz
        tar_mock.assert_called_once_with(
            "cJf",
            "/tmp/test.tar.xz",
            sources=["/tmp/data"],
            cwd=None,
            template=None,
            user=None,
            group=None,
        )
        
        assert ret["result"] is True


# Example 6: Test test mode (no changes)
def test_compressed_test_mode():
    """
    Test that archive.compressed doesn't create files in test mode
    """
    zip_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": True}):  # TEST MODE
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
        )
        
        # In test mode, execution module should NOT be called
        zip_mock.assert_not_called()
        
        # Result should be None (would make changes)
        assert ret["result"] is None
        assert ret["changes"] == {}
        assert "Would create" in ret["comment"]


# Example 7: Test archive already exists without overwrite
def test_compressed_file_exists_no_overwrite():
    """
    Test that archive.compressed doesn't overwrite existing archives by default
    """
    zip_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=True)  # Archive exists
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
            overwrite=False,  # Don't overwrite
        )
        
        # Should NOT call zip since file exists
        zip_mock.assert_not_called()
        
        assert ret["result"] is True
        assert ret["changes"] == {}
        assert "already exists" in ret["comment"]


# Example 8: Test archive exists with overwrite=True
def test_compressed_file_exists_with_overwrite():
    """
    Test that archive.compressed overwrites when overwrite=True
    """
    zip_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=True)
    file_remove_mock = MagicMock(return_value=True)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
            "file.remove": file_remove_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
            overwrite=True,  # Overwrite existing
        )
        
        # Should remove old file and create new one
        file_remove_mock.assert_called_once_with("/tmp/test.zip")
        zip_mock.assert_called_once()
        
        assert ret["result"] is True
        assert ret["changes"] == {"created": "/tmp/test.zip"}


# Example 9: Test missing sources
def test_compressed_missing_sources():
    """
    Test that archive.compressed fails when sources are missing
    """
    with patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=[],  # Empty sources list
            archive_format="zip",
        )
        
        # Should fail with missing sources
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "No sources" in ret["comment"] or "required" in ret["comment"]


# Example 10: Test invalid archive format
def test_compressed_invalid_format():
    """
    Test that archive.compressed fails with invalid format
    """
    with patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.rar",
            sources=["/tmp/file.txt"],
            archive_format="rar",  # Invalid format
        )
        
        # Should fail with invalid format error
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "Unsupported" in ret["comment"] or "invalid" in ret["comment"].lower()


# Example 11: Test with user/group/mode (for tar)
def test_compressed_tar_with_ownership():
    """
    Test that archive.compressed passes user/group/mode to tar
    """
    tar_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.tar.gz",
            sources=["/tmp/data"],
            archive_format="tar",
            compression="gzip",
            user="root",
            group="wheel",
            mode="0644",
        )
        
        # Verify user/group were passed to tar
        tar_mock.assert_called_once_with(
            "czf",
            "/tmp/test.tar.gz",
            sources=["/tmp/data"],
            cwd=None,
            template=None,
            user="root",
            group="wheel",
        )
        
        assert ret["result"] is True


# Example 12: Test execution module failure
def test_compressed_execution_module_fails():
    """
    Test that archive.compressed handles execution module failures
    """
    zip_mock = MagicMock(return_value=False)  # Zip fails
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
        )
        
        # Should fail when execution module fails
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "Failed" in ret["comment"] or "error" in ret["comment"].lower()


# Example 13: Test with custom options for zip
def test_compressed_zip_with_options():
    """
    Test that archive.compressed passes custom options to zip
    """
    zip_mock = MagicMock(return_value=True)
    file_exists_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
            "file.file_exists": file_exists_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
            options="-9",  # Maximum compression
        )
        
        # Verify options were passed
        call_kwargs = zip_mock.call_args[1]
        assert "options" in call_kwargs or zip_mock.call_args[0][0] == "/tmp/test.zip"
        
        assert ret["result"] is True


"""
HOW TO USE THIS TEMPLATE
========================

1. Copy the test functions above into:
   tests/pytests/unit/states/test_archive.py

2. Add them after the existing tests (after line 486)

3. Make sure the tests reference the correct function:
   - Change 'archive.compressed' to use the imported module

4. Run the tests in WSL:
   cd /mnt/c/Users/ironm/Documents/development/salt-dev/salt
   nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py::test_compressed_zip_success

5. Run all compressed tests:
   nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py -k compressed

6. What to adjust based on your actual implementation:
   - The exact parameters your compressed function accepts
   - The exact structure of the return dictionary
   - The exact error messages in comments
   - How your function handles missing execution modules
   - How your function determines compression from filename vs parameter

7. Minimum tests needed for PR:
   - At least one test for ZIP format
   - At least one test for TAR format with compression
   - At least one test for test mode
   - At least one test for error handling

8. Recommended additional tests:
   - All compression types (gzip, bzip2, xz)
   - Overwrite behavior
   - Invalid inputs
   - User/group/mode for tar archives
"""
