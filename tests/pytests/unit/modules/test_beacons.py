"""
    :codeauthor: :email:`Gareth J. Greenaway <ggreenaway@vmware.com>`
"""

import logging
import os

import pytest

import salt.modules.beacons as beacons
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, call, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {beacons: {"__opts__": minion_opts}}


@pytest.mark.slow_test
def test_delete():
    """
    Test deleting a beacon.
    """
    comm1 = "Deleted beacon: ps."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_delete_complete",
            "beacons": {},
        },
    ]

    with patch.dict(
        beacons.__opts__,
        {
            "beacons": {
                "ps": [{"processes": {"salt-master": "stopped", "apache2": "stopped"}}]
            },
        },
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(beacons.__salt__, {"event.fire": mock}):
            with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                assert beacons.delete("ps") == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_add():
    """
    Test adding a beacon
    """
    comm1 = "Added beacon: ps."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["ps"],
        },
        {
            "complete": True,
            "valid": True,
            "vcomment": "",
            "tag": "/salt/minion/minion_beacons_list_complete",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "ps": [{"processes": {"salt-master": "stopped", "apache2": "stopped"}}]
            },
        },
    ]

    mock = MagicMock(return_value=True)
    with patch.dict(beacons.__salt__, {"event.fire": mock}):
        with patch.object(SaltEvent, "get_event", side_effect=event_returns):
            assert beacons.add(
                "ps",
                [
                    {
                        "processes": {
                            "salt-master": "stopped",
                            "apache2": "stopped",
                        }
                    }
                ],
            ) == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_save():
    """
    Test saving beacons.
    """
    _beacon_conf_file = os.path.join(
        os.path.dirname(beacons.__opts__["conf_file"]),
        os.path.dirname(beacons.__opts__["default_include"]),
        "beacons.conf",
    )
    _beacons_data = {
        "ps": [{"processes": {"salt-master": "stopped", "apache2": "stopped"}}]
    }

    # Test that beacons contents are written to config file.
    _expected = {
        "comment": "Beacons saved to {}.".format(_beacon_conf_file),
        "result": True,
    }
    with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
        with patch.object(beacons, "list_", MagicMock(return_value=_beacons_data)):
            ret = beacons.save()
            assert ret == _expected

            _call = call(
                "beacons:\n  ps:\n  - processes:\n      apache2: stopped\n      salt-master: stopped\n"
            )
            write_calls = fopen_mock.filehandles[_beacon_conf_file][
                0
            ].write._mock_mock_calls
            assert _call in write_calls

    _beacons_data = {}

    # Test that when beacons is empty then an empty config file is written.
    _expected = {
        "comment": "Beacons saved to {}.".format(_beacon_conf_file),
        "result": True,
    }
    with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
        with patch.object(beacons, "list_", MagicMock(return_value=_beacons_data)):
            ret = beacons.save()
            assert ret == _expected

            _call = call("")
            write_calls = fopen_mock.filehandles[_beacon_conf_file][
                0
            ].write._mock_mock_calls
            assert _call in write_calls


@pytest.mark.slow_test
def test_disable():
    """
    Test disabling beacons
    """
    comm1 = "Disabled beacons on minion."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_disabled_complete",
            "beacons": {
                "enabled": False,
                "ps": [{"processes": {"salt-master": "stopped", "apache2": "stopped"}}],
            },
        }
    ]

    mock = MagicMock(return_value=True)
    with patch.dict(beacons.__salt__, {"event.fire": mock}):
        with patch.object(SaltEvent, "get_event", side_effect=event_returns):
            assert beacons.disable() == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_enable():
    """
    Test enabling beacons
    """
    comm1 = "Enabled beacons on minion."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_enabled_complete",
            "beacons": {
                "enabled": True,
                "ps": [{"processes": {"salt-master": "stopped", "apache2": "stopped"}}],
            },
        }
    ]

    mock = MagicMock(return_value=True)
    with patch.dict(beacons.__salt__, {"event.fire": mock}):
        with patch.object(SaltEvent, "get_event", side_effect=event_returns):
            assert beacons.enable() == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_add_beacon_module():
    """
    Test adding a beacon
    """
    comm1 = "Added beacon: watch_salt_master."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["ps"],
        },
        {
            "complete": True,
            "valid": True,
            "vcomment": "",
            "tag": "/salt/minion/minion_beacons_list_complete",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "watch_salt_master": [
                    {"processes": {"salt-master": "stopped"}},
                    {"beacon_module": "ps"},
                ]
            },
        },
    ]

    mock = MagicMock(return_value=True)
    with patch.dict(beacons.__salt__, {"event.fire": mock}):
        with patch.object(SaltEvent, "get_event", side_effect=event_returns):
            assert beacons.add(
                "watch_salt_master",
                [
                    {"processes": {"salt-master": "stopped"}},
                    {"beacon_module": "ps"},
                ],
            ) == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_enable_beacon_module():
    """
    Test enabling beacons
    """
    comm1 = "Enabled beacons on minion."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_enabled_complete",
            "beacons": {
                "enabled": True,
                "watch_salt_master": [
                    {"processes": {"salt-master": "stopped"}},
                    {"beacon_module": "ps"},
                ],
            },
        }
    ]

    mock = MagicMock(return_value=True)
    with patch.dict(beacons.__salt__, {"event.fire": mock}):
        with patch.object(SaltEvent, "get_event", side_effect=event_returns):
            assert beacons.enable() == {"comment": comm1, "result": True}


@pytest.mark.slow_test
def test_delete_beacon_module():
    """
    Test deleting a beacon.
    """
    comm1 = "Deleted beacon: watch_salt_master."
    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_delete_complete",
            "beacons": {},
        },
    ]

    with patch.dict(
        beacons.__opts__,
        {
            "beacons": {
                "watch_salt_master": [
                    {"processes": {"salt-master": "stopped"}},
                    {"beacon_module": "ps"},
                ]
            },
        },
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(beacons.__salt__, {"event.fire": mock}):
            with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                assert beacons.delete("watch_salt_master") == {
                    "comment": comm1,
                    "result": True,
                }
