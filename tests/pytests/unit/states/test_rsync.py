"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import pytest

import salt.states.rsync as rsync
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rsync: {}}


def test_syncronized_failed():
    """
    Test to perform an rsync.synchorized call that fails
    """
    ret = {"pid": 100, "retcode": 23, "stderr": "", "stdout": ""}
    _expected = {
        "changes": {},
        "comment": "Destination directory name was not found.",
        "name": "name",
        "result": False,
    }

    with patch.dict(rsync.__opts__, {"test": True}):
        mock = MagicMock(return_value=ret)
        with patch.dict(rsync.__salt__, {"rsync.rsync": mock}):
            assert rsync.synchronized("name", "source") == _expected

    # Run again mocking os.path.exists as True
    ret = {
        "pid": 100,
        "retcode": 23,
        "stderr": "Something went wrong",
        "stdout": "",
    }
    _expected = {
        "changes": {},
        "comment": "Something went wrong",
        "name": "name",
        "result": False,
    }

    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch.dict(rsync.__opts__, {"test": False}):
            mock = MagicMock(return_value=ret)
            with patch.dict(rsync.__salt__, {"rsync.rsync": mock}):
                assert rsync.synchronized("name", "source") == _expected


def test_syncronized():
    """
    Test to perform an rsync.synchorized call that succeeds
    """
    ret = {
        "pid": 100,
        "retcode": 0,
        "stderr": "",
        "stdout": (
            "sending incremental file list\nsnapshot.jar\n\n"
            "sent 106 bytes  received 35 bytes  282.00 bytes/sec\n"
            "total size is 0  speedup is 0.00"
        ),
    }
    _expected = {
        "changes": {"copied": "snapshot.jar", "deleted": "N/A"},
        "comment": (
            "- sent 106 bytes\n- received 35 bytes\n- "
            "282.00 bytes/sec\n- total size is 0\n- speedup is 0.00"
        ),
        "name": "name",
        "result": True,
    }

    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch.dict(rsync.__opts__, {"test": False}):
            mock = MagicMock(return_value=ret)
            with patch.dict(rsync.__salt__, {"rsync.rsync": mock}):
                assert rsync.synchronized("name", "source") == _expected

    # Second pass simulating the file being in place
    ret = {
        "pid": 100,
        "retcode": 0,
        "stderr": "",
        "stdout": (
            "sending incremental file list\n\n"
            "sent 106 bytes  received 35 bytes  "
            "282.00 bytes/sec\ntotal size is 0  "
            "speedup is 0.00"
        ),
    }
    _expected = {
        "changes": {},
        "comment": (
            "- sent 106 bytes\n- received "
            "35 bytes\n- 282.00 bytes/sec\n- total "
            "size is 0\n- speedup is 0.00"
        ),
        "name": "name",
        "result": True,
    }

    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch.dict(rsync.__opts__, {"test": False}):
            mock = MagicMock(return_value=ret)
            with patch.dict(rsync.__salt__, {"rsync.rsync": mock}):
                assert rsync.synchronized("name", "source") == _expected


def test_syncronized_test_true():
    """
    Test to perform an rsync.synchorized call that fails
    """
    ret = {
        "pid": 100,
        "retcode": 23,
        "stderr": "Something went wrong",
        "stdout": "",
    }
    _expected = {"changes": {}, "comment": "- ", "name": "name", "result": None}

    with patch("os.path.exists", MagicMock(return_value=True)):
        with patch.dict(rsync.__opts__, {"test": True}):
            mock = MagicMock(return_value=ret)
            with patch.dict(rsync.__salt__, {"rsync.rsync": mock}):
                assert rsync.synchronized("name", "source") == _expected
