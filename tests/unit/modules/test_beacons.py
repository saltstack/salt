"""
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
"""

import os

import pytest
import salt.modules.beacons as beacons
from salt.utils.event import SaltEvent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class BeaconsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.beacons
    """

    @classmethod
    def setUpClass(cls):
        cls.sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")

    def setup_loader_modules(self):
        return {beacons: {}}

    @pytest.mark.slow_test
    def test_delete(self):
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
                    "ps": [
                        {"processes": {"salt-master": "stopped", "apache2": "stopped"}}
                    ]
                },
                "sock_dir": self.sock_dir,
            },
        ):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.delete("ps"), {"comment": comm1, "result": True}
                    )

    @pytest.mark.slow_test
    def test_add(self):
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
                    "ps": [
                        {"processes": {"salt-master": "stopped", "apache2": "stopped"}}
                    ]
                },
            },
        ]

        with patch.dict(beacons.__opts__, {"beacons": {}, "sock_dir": self.sock_dir}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.add(
                            "ps",
                            [
                                {
                                    "processes": {
                                        "salt-master": "stopped",
                                        "apache2": "stopped",
                                    }
                                }
                            ],
                        ),
                        {"comment": comm1, "result": True},
                    )

    @pytest.mark.slow_test
    def test_save(self):
        """
        Test saving beacons.
        """
        comm1 = "Beacons saved to {}beacons.conf.".format(RUNTIME_VARS.TMP + os.sep)
        with patch.dict(
            beacons.__opts__,
            {
                "conf_file": os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "foo"),
                "beacons": {},
                "default_include": RUNTIME_VARS.TMP + os.sep,
                "sock_dir": self.sock_dir,
            },
        ):

            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                _ret_value = {"complete": True, "beacons": {}}
                with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                    self.assertDictEqual(
                        beacons.save(), {"comment": comm1, "result": True}
                    )

    @pytest.mark.slow_test
    def test_disable(self):
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
                    "ps": [
                        {"processes": {"salt-master": "stopped", "apache2": "stopped"}}
                    ],
                },
            }
        ]

        with patch.dict(beacons.__opts__, {"beacons": {}, "sock_dir": self.sock_dir}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.disable(), {"comment": comm1, "result": True}
                    )

    @pytest.mark.slow_test
    def test_enable(self):
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
                    "ps": [
                        {"processes": {"salt-master": "stopped", "apache2": "stopped"}}
                    ],
                },
            }
        ]

        with patch.dict(beacons.__opts__, {"beacons": {}, "sock_dir": self.sock_dir}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.enable(), {"comment": comm1, "result": True}
                    )

    @pytest.mark.slow_test
    def test_add_beacon_module(self):
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

        with patch.dict(beacons.__opts__, {"beacons": {}, "sock_dir": self.sock_dir}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.add(
                            "watch_salt_master",
                            [
                                {"processes": {"salt-master": "stopped"}},
                                {"beacon_module": "ps"},
                            ],
                        ),
                        {"comment": comm1, "result": True},
                    )

    @pytest.mark.slow_test
    def test_enable_beacon_module(self):
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

        with patch.dict(beacons.__opts__, {"beacons": {}, "sock_dir": self.sock_dir}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.enable(), {"comment": comm1, "result": True}
                    )

    @pytest.mark.slow_test
    def test_delete_beacon_module(self):
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
                "sock_dir": self.sock_dir,
            },
        ):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {"event.fire": mock}):
                with patch.object(SaltEvent, "get_event", side_effect=event_returns):
                    self.assertDictEqual(
                        beacons.delete("watch_salt_master"),
                        {"comment": comm1, "result": True},
                    )
