"""
    :codeauthor: Alexander Schwartz <alexander.schwartz@gmx.net>
"""

import os

import pytest

#from unittest.mock import MagicMock, patch

import salt.states.archive as archive
import salt.utils.platform
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        archive: {
            "__grains__": {"os": "FooOS!"},
            "__opts__": {"cachedir": "/tmp", "test": False, "hash_type": "sha256"},
            "__env__": "test",
        }
    }


def _isfile_side_effect(path):
    """
    MagicMock side_effect for os.path.isfile(). We don't want to use dict.get
    here because we want the test to fail if there's a path we haven't
    accounted for, so that we can add it.

    NOTE: This may fall over on some platforms if /usr/bin/tar does not exist.
    If so, just add an entry in the dictionary for the path being used for tar.
    """
    if salt.utils.platform.is_windows():
        path = path.lower()
    d = {
        "/tmp/foo.tar.gz": True,
        "c:\\tmp\\foo.tar.gz": True,
        "/private/tmp/foo.tar.gz": True,
        "/tmp/out": False,
        "\\tmp\\out": False,
        "/usr/bin/tar": True,
        "/bin/tar": True,
        "/tmp/test_extracted_tar": False,
        "c:\\tmp\\test_extracted_tar": False,
        "/private/tmp/test_extracted_tar": False,
    }
    return d[path]


def test_extracted_tar():
    """
    archive.extracted tar options
    """

    if salt.utils.platform.is_windows():
        source = "C:\\tmp\\foo.tar.gz"
        tmp_dir = "C:\\tmp\\test_extracted_tar"
    elif salt.utils.platform.is_darwin():
        source = "/private/tmp/foo.tar.gz"
        tmp_dir = "/private/tmp/test_extracted_tar"
    else:
        source = "/tmp/foo.tar.gz"
        tmp_dir = "/tmp/test_extracted_tar"
    test_tar_opts = [
        "--no-anchored foo",
        "v -p --opt",
        "-v -p",
        "--long-opt -z",
        "z -v -weird-long-opt arg",
    ]
    ret_tar_opts = [
        ["tar", "xv", "--no-anchored", "foo", "-f"],
        ["tar", "xv", "-p", "--opt", "-f"],
        ["tar", "xv", "-p", "-f"],
        ["tar", "xv", "--long-opt", "-z", "-f"],
        ["tar", "xvz", "-weird-long-opt", "arg", "-f"],
    ]

    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    ret = {
        "stdout": ["cheese", "ham", "saltines"],
        "stderr": "biscuits",
        "retcode": "31337",
        "pid": "1337",
    }
    mock_run = MagicMock(return_value=ret)
    mock_source_list = MagicMock(return_value=(source, None))
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["cheese", "saltines"],
            "links": ["ham"],
            "top_level_dirs": [],
            "top_level_files": ["cheese", "saltines"],
            "top_level_links": ["ham"],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__opts__,
        {"test": False, "cachedir": tmp_dir, "hash_type": "sha256"},
    ), patch.dict(
        archive.__salt__,
        {
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": mock_run,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(
        archive.__states__, {"file.directory": mock_true}
    ), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):

        for test_opts, ret_opts in zip(test_tar_opts, ret_tar_opts):
            archive.extracted(
                tmp_dir, source, options=test_opts, enforce_toplevel=False
            )
            ret_opts.append(source)
            mock_run.assert_called_with(
                ret_opts, cwd=tmp_dir + os.sep, python_shell=False
            )


def test_tar_gnutar():
    """
    Tests the call of extraction with gnutar
    """
    gnutar = MagicMock(return_value="tar (GNU tar)")
    source = "/tmp/foo.tar.gz"
    mock_false = MagicMock(return_value=False)
    mock_true = MagicMock(return_value=True)
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    run_all = MagicMock(
        return_value={"retcode": 0, "stdout": "stdout", "stderr": "stderr"}
    )
    mock_source_list = MagicMock(return_value=(source, None))
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["stdout"],
            "links": [],
            "top_level_dirs": [],
            "top_level_files": ["stdout"],
            "top_level_links": [],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__salt__,
        {
            "cmd.run": gnutar,
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": run_all,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(archive.__states__, {"file.directory": mock_true}), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = archive.extracted(
            os.path.join(os.sep + "tmp", "out"),
            source,
            options="xvzf",
            enforce_toplevel=False,
            keep=True,
        )
        assert ret["changes"]["extracted_files"] == ["stdout"]


def test_tar_bsdtar():
    """
    Tests the call of extraction with bsdtar
    """
    bsdtar = MagicMock(return_value="tar (bsdtar)")
    source = "/tmp/foo.tar.gz"
    mock_false = MagicMock(return_value=False)
    mock_true = MagicMock(return_value=True)
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    run_all = MagicMock(
        return_value={"retcode": 0, "stdout": "stdout", "stderr": "stderr"}
    )
    mock_source_list = MagicMock(return_value=(source, None))
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["stderr"],
            "links": [],
            "top_level_dirs": [],
            "top_level_files": ["stderr"],
            "top_level_links": [],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__salt__,
        {
            "cmd.run": bsdtar,
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": run_all,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(archive.__states__, {"file.directory": mock_true}), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = archive.extracted(
            os.path.join(os.sep + "tmp", "out"),
            source,
            options="xvzf",
            enforce_toplevel=False,
            keep=True,
        )
        assert ret["changes"]["extracted_files"] == ["stderr"]


def test_tar_bsdtar_with_trim_output():
    """
    Tests the call of extraction with bsdtar with trim_output
    """
    bsdtar = MagicMock(return_value="tar (bsdtar)")
    source = "/tmp/foo.tar.gz"
    mock_false = MagicMock(return_value=False)
    mock_true = MagicMock(return_value=True)
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    run_all = MagicMock(
        return_value={"retcode": 0, "stdout": "stdout", "stderr": "stderr"}
    )
    mock_source_list = MagicMock(return_value=(source, None))
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["stderr"],
            "links": [],
            "top_level_dirs": [],
            "top_level_files": ["stderr"],
            "top_level_links": [],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__salt__,
        {
            "cmd.run": bsdtar,
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": run_all,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(archive.__states__, {"file.directory": mock_true}), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = archive.extracted(
            os.path.join(os.sep + "tmp", "out"),
            source,
            options="xvzf",
            enforce_toplevel=False,
            keep_source=True,
            trim_output=1,
        )
        assert ret["changes"]["extracted_files"] == ["stderr"]
        assert ret["comment"].endswith("Output was trimmed to 1 number of lines")


def test_extracted_when_if_missing_path_exists():
    """
    When if_missing exists, we should exit without making any changes.

    NOTE: We're not mocking the __salt__ dunder because if we actually run
    any functions from that dunder, we're doing something wrong. So, in
    those cases we'll just let it raise a KeyError and cause the test to
    fail.
    """
    name = if_missing = "/tmp/foo"
    source = "salt://foo.bar.tar"
    with patch.object(os.path, "exists", MagicMock(return_value=True)):
        ret = archive.extracted(name, source=source, if_missing=if_missing)
        assert ret["result"], ret
        assert ret["comment"] == f"Path {if_missing} exists"


def test_clean_parent_conflict():
    """
    Tests the call of extraction with gnutar with both clean_parent plus clean set to True
    """
    gnutar = MagicMock(return_value="tar (GNU tar)")
    source = "/tmp/foo.tar.gz"
    ret_comment = "Only one of 'clean' and 'clean_parent' can be set to True"
    mock_false = MagicMock(return_value=False)
    mock_true = MagicMock(return_value=True)
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    run_all = MagicMock(
        return_value={"retcode": 0, "stdout": "stdout", "stderr": "stderr"}
    )
    mock_source_list = MagicMock(return_value=(source, None))
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["stdout"],
            "links": [],
            "top_level_dirs": [],
            "top_level_files": ["stdout"],
            "top_level_links": [],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__salt__,
        {
            "cmd.run": gnutar,
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": run_all,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(archive.__states__, {"file.directory": mock_true}), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = archive.extracted(
            os.path.join(os.sep + "tmp", "out"),
            source,
            options="xvzf",
            enforce_toplevel=False,
            clean=True,
            clean_parent=True,
            keep=True,
        )
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert ret["comment"] == ret_comment


def test_skip_files_list_verify_conflict():
    """
    Tests the call of extraction with both skip_files_list_verify and skip_verify set to True
    """
    gnutar = MagicMock(return_value="tar (GNU tar)")
    source = "/tmp/foo.tar.gz"
    ret_comment = (
        'Only one of "skip_files_list_verify" and "skip_verify" can be set to True'
    )
    mock_false = MagicMock(return_value=False)
    mock_true = MagicMock(return_value=True)
    state_single_mock = MagicMock(return_value={"local": {"result": True}})
    run_all = MagicMock(
        return_value={"retcode": 0, "stdout": "stdout", "stderr": "stderr"}
    )
    mock_source_list = MagicMock(return_value=(source, None))
    list_mock = MagicMock(
        return_value={
            "dirs": [],
            "files": ["stdout"],
            "links": [],
            "top_level_dirs": [],
            "top_level_files": ["stdout"],
            "top_level_links": [],
        }
    )
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch.dict(
        archive.__salt__,
        {
            "cmd.run": gnutar,
            "file.directory_exists": mock_false,
            "file.file_exists": mock_false,
            "state.single": state_single_mock,
            "file.makedirs": mock_true,
            "cmd.run_all": run_all,
            "archive.list": list_mock,
            "file.source_list": mock_source_list,
        },
    ), patch.dict(archive.__states__, {"file.directory": mock_true}), patch.object(
        os.path, "isfile", isfile_mock
    ), patch(
        "salt.utils.path.which", MagicMock(return_value=True)
    ):
        ret = archive.extracted(
            os.path.join(os.sep + "tmp", "out"),
            source,
            options="xvzf",
            enforce_toplevel=False,
            clean=True,
            skip_files_list_verify=True,
            skip_verify=True,
            keep=True,
        )
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert ret["comment"] == ret_comment


def test_skip_files_list_verify_success():
    """
    Test that if the local and expected source hash are the same we won't do anything.
    """

    if salt.utils.platform.is_windows():
        source = "C:\\tmp\\foo.tar.gz"
        tmp_dir = "C:\\tmp\\test_extracted_tar"
    elif salt.utils.platform.is_darwin():
        source = "/private/tmp/foo.tar.gz"
        tmp_dir = "/private/tmp/test_extracted_tar"
    else:
        source = "/tmp/foo.tar.gz"
        tmp_dir = "/tmp/test_extracted_tar"

    expected_comment = (
        "Archive {} existing source sum is the same as the "
        "expected one and skip_files_list_verify argument "
        "was set to True. Extraction is not needed".format(source)
    )
    expected_ret = {
        "name": tmp_dir,
        "result": True,
        "changes": {},
        "comment": expected_comment,
    }
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    mock_cached = MagicMock(return_value=f"{tmp_dir}/{source}")
    source_sum = {"hsum": "testhash", "hash_type": "sha256"}
    mock_hash = MagicMock(return_value=source_sum)
    mock_source_list = MagicMock(return_value=(source, None))
    isfile_mock = MagicMock(side_effect=_isfile_side_effect)

    with patch("salt.states.archive._read_cached_checksum", mock_hash):
        with patch.dict(
            archive.__opts__,
            {"test": False, "cachedir": tmp_dir, "hash_type": "sha256"},
        ), patch.dict(
            archive.__salt__,
            {
                "file.directory_exists": mock_false,
                "file.get_source_sum": mock_hash,
                "file.check_hash": mock_true,
                "cp.is_cached": mock_cached,
                "file.source_list": mock_source_list,
            },
        ), patch.object(
            os.path, "isfile", isfile_mock
        ):

            ret = archive.extracted(
                tmp_dir,
                source,
                source_hash="testhash",
                skip_files_list_verify=True,
                enforce_toplevel=False,
            )
            assert ret == expected_ret




# Example 1: Test successful ZIP creation
def test_compressed_zip_success():
    """
    Test that archive.compressed creates a ZIP file successfully
    """
    # Mock the archive.zip execution module to return success
    zip_mock = MagicMock(return_value=True)
    
    # Mock os.path.exists to say sources exist, archive doesn't
    def path_exists_side_effect(path):
        if path == "/tmp/test.zip":
            return False  # Archive doesn't exist
        return True  # Sources exist
    
    # Mock os.path.isfile to say archive doesn't exist
    isfile_mock = MagicMock(return_value=False)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", isfile_mock
    ):
        
        # Call the compressed function
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file1.txt", "/tmp/file2.txt"],
            archive_format="zip",
        )
        
        # Verify the execution module was called correctly
        zip_mock.assert_called_once_with(
            "/tmp/test.zip",
            "/tmp/file1.txt",
            "/tmp/file2.txt",
        )
        
        # Verify the return structure
        assert ret["name"] == "/tmp/test.zip"
        assert ret["result"] is True
        assert ret["changes"]["created"] == "/tmp/test.zip"
        assert "Successfully created" in ret["comment"]


# Example 2: Test successful TAR.GZ creation
def test_compressed_tar_gz_success():
    """
    Test that archive.compressed creates a TAR.GZ file successfully
    """
    tar_mock = MagicMock(return_value=True)
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.tar.gz":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.tar.gz",
            sources=["/tmp/dir1", "/tmp/dir2"],
            archive_format="tar.gz",
        )
        
        # Verify tar was called with compression flag
        tar_mock.assert_called_once_with(
            "czf",
            "/tmp/test.tar.gz",
            ["/tmp/dir1", "/tmp/dir2"],
        )
        
        assert ret["result"] is True
        assert ret["changes"]["created"] == "/tmp/test.tar.gz"


# Example 3: Test tar without compression
def test_compressed_tar_no_compression():
    """
    Test that archive.compressed creates a plain TAR file
    """
    tar_mock = MagicMock(return_value=True)
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.tar":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.tar",
            sources=["/tmp/file.txt"],
            archive_format="tar",
        )
        
        # Verify tar was called with 'cf' (no compression flag)
        tar_mock.assert_called_once_with(
            "cf",
            "/tmp/test.tar",
            ["/tmp/file.txt"],
        )
        
        assert ret["result"] is True


# Example 4: Test tar.bz2 compression
def test_compressed_tar_bz2():
    """
    Test that archive.compressed creates a TAR.BZ2 file
    """
    tar_mock = MagicMock(return_value=True)
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.tar.bz2":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.tar.bz2",
            sources=["/tmp/data"],
            archive_format="tar.bz2",
        )
        
        # Verify 'j' flag for bzip2
        tar_mock.assert_called_once_with(
            "cjf",
            "/tmp/test.tar.bz2",
            ["/tmp/data"],
        )
        
        assert ret["result"] is True


# Example 5: Test tar.xz compression
def test_compressed_tar_xz():
    """
    Test that archive.compressed creates a TAR.XZ file
    """
    tar_mock = MagicMock(return_value=True)
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.tar.xz":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.tar.xz",
            sources=["/tmp/data"],
            archive_format="tar.xz",
        )
        
        # Verify 'J' flag for xz
        tar_mock.assert_called_once_with(
            "cJf",
            "/tmp/test.tar.xz",
            ["/tmp/data"],
        )
        
        assert ret["result"] is True


# Example 6: Test test mode (no changes)
def test_compressed_test_mode():
    """
    Test that archive.compressed doesn't create files in test mode
    """
    zip_mock = MagicMock(return_value=True)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
        },
    ), patch.dict(archive.__opts__, {"test": True}), patch.object(
        os.path, "exists", MagicMock(return_value=True)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
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
        assert "would be created" in ret["comment"]


# Example 7: Test archive already exists without overwrite
def test_compressed_file_exists_no_overwrite():
    """
    Test that archive.compressed doesn't overwrite existing archives by default
    """
    zip_mock = MagicMock(return_value=True)
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(return_value=True)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=True)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
            overwrite=False,
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
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(return_value=True)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=True)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
            overwrite=True,
        )
        
        # Should create archive even though file exists
        zip_mock.assert_called_once()
        
        assert ret["result"] is True
        assert ret["changes"]["created"] == "/tmp/test.zip"


# Example 9: Test missing sources
def test_compressed_missing_sources():
    """
    Test that archive.compressed fails when sources don't exist
    """
    with patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/nonexistent.txt"],
            archive_format="zip",
        )
        
        # Should fail with missing sources
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "do not exist" in ret["comment"]


# Example 10: Test invalid archive format
def test_compressed_invalid_format():
    """
    Test that archive.compressed fails with invalid format
    """
    with patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(return_value=True)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.rar",
            sources=["/tmp/file.txt"],
            archive_format="rar",
        )
        
        # Should fail with invalid format error
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "Unsupported" in ret["comment"]


# Example 11: Test with user/group/mode (for tar)
def test_compressed_tar_with_ownership():
    """
    Test that archive.compressed sets ownership after creating tar
    """
    tar_mock = MagicMock(return_value=True)
    file_managed_mock = MagicMock(return_value={"result": True, "changes": {"user": "root"}})
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.tar.gz":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.tar": tar_mock,
        },
    ), patch.dict(
        archive.__states__,
        {
            "file.managed": file_managed_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.tar.gz",
            sources=["/tmp/data"],
            archive_format="tar.gz",
            user="root",
            group="wheel",
            mode="0644",
        )
        
        # Verify tar was called
        tar_mock.assert_called_once()
        
        # Verify file.managed was called to set ownership
        file_managed_mock.assert_called_once()
        
        assert ret["result"] is True


# Example 12: Test execution module failure
def test_compressed_execution_module_fails():
    """
    Test that archive.compressed handles execution module failures
    """
    zip_mock = MagicMock(return_value=False)
    
    def path_exists_side_effect(path):
        if path == "/tmp/test.zip":
            return False
        return True
    
    with patch.dict(
        archive.__salt__,
        {
            "archive.zip": zip_mock,
        },
    ), patch.dict(archive.__opts__, {"test": False}), patch.object(
        os.path, "exists", MagicMock(side_effect=path_exists_side_effect)
    ), patch.object(
        os.path, "isfile", MagicMock(return_value=False)
    ):
        
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
            archive_format="zip",
        )
        
        # Should fail when execution module fails
        assert ret["result"] is False
        assert ret["changes"] == {}
        assert "Failed" in ret["comment"]
