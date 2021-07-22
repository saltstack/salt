"""
unit tests for the beacon_module parameter
"""

import logging

import salt.beacons as beacons
import salt.config
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class BeaconsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt beacon_module parameter
    """

    def setup_loader_modules(self):
        return {beacons: {}}

    def test_beacon_module(self):
        """
        Test that beacon_module parameter for beacon configuration
        """
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["id"] = "minion"
        mock_opts["__role"] = "minion"
        mock_opts["beacons"] = {
            "watch_apache": [
                {"processes": {"apache2": "stopped"}},
                {"beacon_module": "ps"},
            ]
        }
        with patch.dict(beacons.__opts__, mock_opts):
            beacon = salt.beacons.Beacon(mock_opts, [])
            ret = beacon.process(mock_opts["beacons"], mock_opts["grains"])

            _expected = [
                {
                    "tag": "salt/beacon/minion/watch_apache/",
                    "data": {"id": "minion", "apache2": "Stopped"},
                    "beacon_name": "ps",
                }
            ]
            self.assertEqual(ret, _expected)

            # Ensure that "beacon_name" is available in the call to the beacon function
            name = "ps.beacon"
            mocked = {name: MagicMock(return_value=_expected)}
            mocked[name].__globals__ = {}
            calls = [
                call(
                    [
                        {"processes": {"apache2": "stopped"}},
                        {"beacon_module": "ps"},
                        {"_beacon_name": "watch_apache"},
                    ]
                )
            ]
            with patch.object(beacon, "beacons", mocked) as patched:
                beacon.process(mock_opts["beacons"], mock_opts["grains"])
                patched[name].assert_has_calls(calls)
