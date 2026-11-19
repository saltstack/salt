import errno
import os

import pytest

import salt.modules.zypperpkg as zypper
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {zypper: {"__salt__": {}}}


@pytest.mark.parametrize("err", [errno.EROFS, errno.EACCES, errno.EPERM])
def test_is_rpm_lock_unwritable_lock_file(err, tmp_path):
    """
    _is_rpm_lock must not raise when the rpm lock file cannot be opened for
    writing (e.g. read-only root filesystem on transactional systems).
    """
    lock = tmp_path / ".rpm.lock"
    lock.touch()
    caller = zypper._Zypper()
    caller.exit_code = 1
    with patch.object(caller, "RPM_LOCK", str(lock)), patch(
        "salt.utils.files.fopen", side_effect=OSError(err, os.strerror(err))
    ):
        assert caller._is_rpm_lock() is False


def test_is_rpm_lock_other_oserror_raised(tmp_path):
    lock = tmp_path / ".rpm.lock"
    lock.touch()
    caller = zypper._Zypper()
    caller.exit_code = 1
    with patch.object(caller, "RPM_LOCK", str(lock)), patch(
        "salt.utils.files.fopen", side_effect=OSError(errno.EIO, "io")
    ):
        with pytest.raises(OSError):
            caller._is_rpm_lock()
