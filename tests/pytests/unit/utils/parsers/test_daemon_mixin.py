"""
Tests the PIDfile deletion in the DaemonMixIn.
"""

import logging

import pytest

import salt.utils.parsers
from tests.support.mock import ANY, MagicMock, patch


@pytest.fixture
def daemon_mixin():
    mixin = salt.utils.parsers.DaemonMixIn()
    mixin.config = {"pidfile": "/some/fake.pid"}
    return mixin


def test_pid_file_deletion(daemon_mixin):
    """
    PIDfile deletion without exception.
    """
    with patch("os.unlink", MagicMock()) as unlink_mock:
        with patch("os.path.isfile", MagicMock(return_value=True)):
            with patch("salt.utils.parsers.log", MagicMock()) as log_mock:
                daemon_mixin._mixin_before_exit()
                unlink_mock.assert_called_once()
                log_mock.info.assert_not_called()
                log_mock.debug.assert_not_called()


def test_pid_deleted_oserror_as_root(daemon_mixin):
    """
    PIDfile deletion with exception, running as root.
    """
    with patch("os.unlink", MagicMock(side_effect=OSError())) as unlink_mock:
        with patch("os.path.isfile", MagicMock(return_value=True)):
            with patch("salt.utils.parsers.log", MagicMock()) as log_mock:
                if salt.utils.platform.is_windows():
                    patch_args = (
                        "salt.utils.win_functions.is_admin",
                        MagicMock(return_value=True),
                    )
                else:
                    patch_args = ("os.getuid", MagicMock(return_value=0))

                with patch(*patch_args):
                    daemon_mixin._mixin_before_exit()
                    assert unlink_mock.call_count == 1
                    log_mock.info.assert_called_with(
                        "PIDfile(%s) could not be deleted: %s",
                        format(daemon_mixin.config["pidfile"], ""),
                        ANY,
                        exc_info_on_loglevel=logging.DEBUG,
                    )


def test_pid_deleted_oserror_as_non_root(daemon_mixin):
    """
    PIDfile deletion with exception, running as non-root.
    """
    with patch("os.unlink", MagicMock(side_effect=OSError())) as unlink_mock:
        with patch("os.path.isfile", MagicMock(return_value=True)):
            with patch("salt.utils.parsers.log", MagicMock()) as log_mock:
                if salt.utils.platform.is_windows():
                    patch_args = (
                        "salt.utils.win_functions.is_admin",
                        MagicMock(return_value=False),
                    )
                else:
                    patch_args = ("os.getuid", MagicMock(return_value=1000))

                with patch(*patch_args):
                    daemon_mixin._mixin_before_exit()
                    assert unlink_mock.call_count == 1
                    log_mock.info.assert_not_called()
                    log_mock.debug.assert_not_called()
