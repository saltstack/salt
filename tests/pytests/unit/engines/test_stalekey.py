"""
unit tests for the stalekey engine
"""

import logging

import pytest

import salt.engines.stalekey as stalekey
from tests.support.mock import MagicMock, mock_open, patch

log = logging.getLogger(__name__)


class MockWheel:
    def __init__(self, *args, **kwargs):
        pass

    def cmd(self, *args, **kwargs):
        return True


@pytest.fixture
def configure_loader_modules():
    return {stalekey: {}}


def test__delete_keys():
    """
    Test to ensure the _delete_keys function deletes multiple keys
    """
    with patch("salt.wheel.WheelClient", MockWheel):
        stale_keys = ["minion1", "minion2"]
        minions = {
            "minion1": 1601430462.5281658,
            "minion2": 1601430462.5281658,
        }

        ret = stalekey._delete_keys(stale_keys, minions)
        assert ret == {}

        stale_keys = ["minion1"]
        minions = {
            "minion1": 1601430462.5281658,
            "minion2": 1601430462.5281658,
        }

        ret = stalekey._delete_keys(stale_keys, minions)
        assert ret == {"minion2": 1601430462.5281658}


def test__read_presence():
    """
    Test for _read_presence returning False for no error and minions presence data
    """
    presence_data = {b"minion": 1601477127.532849}
    expected = (False, {"minion": 1601477127.532849})
    with patch("os.path.exists", return_value=True):
        with patch("salt.utils.files.fopen", mock_open()):
            with patch(
                "salt.utils.msgpack.load", MagicMock(return_value=presence_data)
            ):
                ret = stalekey._read_presence("presence_file")
                assert ret == expected


def test__write_presence():
    """
    Test for _write_presence returning False, meaning no error has occured
    """
    expected = False
    minions = {
        "minion1": 1601430462.5281658,
        "minion2": 1601430462.5281658,
    }
    with patch("salt.utils.files.fopen", mock_open()):
        ret = stalekey._write_presence("presence_file", minions)
        assert ret == expected
