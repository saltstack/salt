import os

import pytest

import salt.utils.verify
from tests.support.mock import patch


@pytest.mark.skip_on_windows(reason="Not applicable for Windows.")
def test_verify_env_race_condition():
    def _stat(path):
        """
        Helper function for mock_stat, we want to raise errors for specific paths, but not until we get into the proper path.
        Until then, just return plain os.stat_result
        """
        if path in ("/tmp/salt-dir/.file3", "/tmp/salt-dir/.dir3"):
            raise AssertionError("The .file3 and .dir3 paths should never be called!")

        if path in ("/tmp/salt-dir/file1", "/tmp/salt-dir/dir1"):
            raise FileNotFoundError(
                "[Errno 2] No such file or directory: this exception should not be visible"
            )

        # we need to return at least different st_uid in order to trigger chown for these paths
        if path in ("/tmp/salt-dir/file4", "/tmp/salt-dir/dir4"):
            return os.stat_result([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

        return os.stat_result([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def _chown(path, uid, gid):
        if path in ("/tmp/salt-dir/file4", "/tmp/salt-dir/dir4"):
            raise FileNotFoundError(
                "[Errno 2] No such file or directory: this exception should not be visible"
            )

        return

    with patch("os.chown", side_effect=_chown) as mock_chown, patch(
        "os.stat", side_effect=_stat
    ) as mock_stat, patch(
        "salt.utils.verify._get_pwnam", return_value=(None, None, 0, 0)
    ), patch(
        "os.getuid", return_value=0
    ), patch(
        "os.listdir", return_value=["subdir"]
    ), patch(
        "os.path.isdir", return_value=True
    ), patch(
        "salt.utils.path.os_walk",
        return_value=[
            (
                "/tmp/salt-dir",
                ["dir1", "dir2", ".dir3", "dir4"],
                ["file1", "file2", ".file3", "file4"],
            )
        ],
    ):

        # verify this runs without issues, even though FNFE is raised
        salt.utils.verify.verify_env(["/tmp/salt-dir"], "root", skip_extra=True)

        # and verify it got actually called with the valid paths
        mock_stat.assert_any_call("/tmp/salt-dir/file1")
        mock_stat.assert_any_call("/tmp/salt-dir/dir1")

        mock_stat.assert_any_call("/tmp/salt-dir/file4")
        mock_stat.assert_any_call("/tmp/salt-dir/dir4")

        mock_chown.assert_any_call("/tmp/salt-dir/file4", 0, 0)
        mock_chown.assert_any_call("/tmp/salt-dir/dir4", 0, 0)
