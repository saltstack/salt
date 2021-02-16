"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import os

import pytest
import salt.modules.beacons as beaconmod
import salt.states.beacon as beaconstate
import salt.states.service as servicestate
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        servicestate: {
            "__env__": "base",
            "__salt__": {},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        },
        beaconstate: {"__salt__": {}, "__opts__": {}},
        beaconmod: {"__salt__": {}, "__opts__": {}},
    }


def test_mod_beacon():
    """
    Test to create a beacon based on a service
    """
    name = "sshd"

    with patch.dict(
        servicestate.__salt__, {"beacons.list": MagicMock(return_value={})}
    ):
        with patch.dict(
            servicestate.__states__, {"beacon.present": beaconstate.present}
        ):
            ret = servicestate.mod_beacon(name, sfun="copy")
            expected = {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "service.copy does not work with the beacon state function",
            }

            assert ret == expected

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
            "beacons": ["service"],
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
                "beacon_service_sshd": [
                    {
                        "services": {
                            "sshd": {
                                "onchangeonly": True,
                                "delay": 0,
                                "uncleanshutdown": None,
                                "emitatstartup": False,
                            },
                        }
                    },
                    {"interval": 60},
                    {"beacon_module": "service"},
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

    with pytest.helpers.temp_directory() as tempdir:
        sock_dir = os.path.join(tempdir, "test-socks")
        with patch.dict(
            servicestate.__states__, {"beacon.present": beaconstate.present}
        ):
            with patch.dict(beaconstate.__salt__, beacon_state_mocks):
                with patch.dict(beaconmod.__salt__, beacon_mod_mocks):
                    with patch.dict(
                        beaconmod.__opts__, {"beacons": {}, "sock_dir": sock_dir}
                    ):
                        with patch.object(
                            SaltEvent, "get_event", side_effect=event_returns
                        ):
                            ret = servicestate.mod_beacon(
                                name, sfun="running", beacon="True"
                            )
                            expected = {
                                "name": "beacon_service_sshd",
                                "changes": {},
                                "result": True,
                                "comment": "Adding beacon_service_sshd to beacons",
                            }

                            assert ret == expected
