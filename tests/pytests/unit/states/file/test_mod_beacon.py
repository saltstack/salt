"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import pytest

import salt.modules.beacons as beaconmod
import salt.states.beacon as beaconstate
import salt.states.file as filestate
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.usefixtures("mocked_tcp_pub_client"),
]


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        },
        beaconstate: {"__salt__": {}, "__opts__": {}},
        beaconmod: {"__salt__": {}, "__opts__": {}},
    }


def test_mod_beacon_unsupported():
    """
    Test to create a beacon based on a file
    """
    name = "/tmp/tempfile"

    with patch.dict(filestate.__salt__, {"beacons.list": MagicMock(return_value={})}):
        with patch.dict(filestate.__states__, {"beacon.present": beaconstate.present}):
            ret = filestate.mod_beacon(name, sfun="copy")
            expected = {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "file.copy does not work with the beacon state function",
            }

            assert ret == expected


def test_mod_beacon_beacon_false():
    """
    Test to create a beacon based on a file
    """
    name = "/tmp/tempfile"

    with patch.dict(filestate.__salt__, {"beacons.list": MagicMock(return_value={})}):
        with patch.dict(filestate.__states__, {"beacon.present": beaconstate.present}):
            ret = filestate.mod_beacon(name, sfun="managed")
            expected = {
                "name": name,
                "changes": {},
                "result": True,
                "comment": "Not adding beacon.",
            }

            assert ret == expected

            ret = filestate.mod_beacon(name, sfun="managed", beacon=False)
            expected = {
                "name": name,
                "changes": {},
                "result": True,
                "comment": "Not adding beacon.",
            }

            assert ret == expected


def test_mod_beacon_file(tmp_path):
    """
    Test to create a beacon based on a file
    """

    name = "/tmp/tempfile"

    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["inotify"],
        },
        {
            "valid": True,
            "tag": "/salt/minion/minion_beacon_validation_complete",
            "vcomment": "Valid beacon configuration",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "beacon_inotify_/tmp/tempfile": [
                    {
                        "files": {
                            "/tmp/tempfile": {"mask": ["create", "delete", "modify"]},
                        }
                    },
                    {"interval": 60},
                    {"coalesce": False},
                    {"beacon_module": "inotify"},
                ]
            },
        },
    ]
    mock = MagicMock(return_value=True)
    beacon_state_mocks = {
        "beacons.list": beaconmod.list_,
        "beacons.add": beaconmod.add,
        "beacons.list_available": beaconmod.list_available,
        "event.fire": mock,
    }

    beacon_mod_mocks = {"event.fire": mock}

    sock_dir = str(tmp_path / "test-socks")
    with patch.dict(filestate.__states__, {"beacon.present": beaconstate.present}):
        with patch.dict(beaconstate.__salt__, beacon_state_mocks):
            with patch.dict(beaconmod.__salt__, beacon_mod_mocks):
                with patch.dict(
                    beaconmod.__opts__, {"beacons": {}, "sock_dir": sock_dir}
                ):
                    with patch.object(
                        SaltEvent, "get_event", side_effect=event_returns
                    ):
                        ret = filestate.mod_beacon(name, sfun="managed", beacon="True")
                        expected = {
                            "name": "beacon_inotify_/tmp/tempfile",
                            "changes": {},
                            "result": True,
                            "comment": "Adding beacon_inotify_/tmp/tempfile to beacons",
                        }

                        assert ret == expected


def test_mod_beacon_directory(tmp_path):
    """
    Test to create a beacon based on a file
    """

    name = "/tmp/tempdir"

    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["inotify"],
        },
        {
            "valid": True,
            "tag": "/salt/minion/minion_beacon_validation_complete",
            "vcomment": "Valid beacon configuration",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "beacon_inotify_/tmp/tempdir": [
                    {
                        "files": {
                            "/tmp/tempdir": {
                                "mask": ["create", "delete", "modify"],
                                "auto_add": True,
                                "recurse": True,
                                "exclude": [],
                            }
                        }
                    },
                    {"interval": 60},
                    {"coalesce": False},
                    {"beacon_module": "inotify"},
                ]
            },
        },
    ]
    mock = MagicMock(return_value=True)
    beacon_state_mocks = {
        "beacons.list": beaconmod.list_,
        "beacons.add": beaconmod.add,
        "beacons.list_available": beaconmod.list_available,
        "event.fire": mock,
    }

    beacon_mod_mocks = {"event.fire": mock}

    sock_dir = str(tmp_path / "test-socks")
    with patch.dict(filestate.__states__, {"beacon.present": beaconstate.present}):
        with patch.dict(beaconstate.__salt__, beacon_state_mocks):
            with patch.dict(beaconmod.__salt__, beacon_mod_mocks):
                with patch.dict(
                    beaconmod.__opts__, {"beacons": {}, "sock_dir": sock_dir}
                ):
                    with patch.object(
                        SaltEvent, "get_event", side_effect=event_returns
                    ):
                        ret = filestate.mod_beacon(
                            name, sfun="directory", beacon="True"
                        )
                        expected = {
                            "name": "beacon_inotify_/tmp/tempdir",
                            "changes": {},
                            "result": True,
                            "comment": "Adding beacon_inotify_/tmp/tempdir to beacons",
                        }

                        assert ret == expected
