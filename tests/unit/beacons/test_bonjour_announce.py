# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.bonjour_announce as bonjour_announce
from tests.support.mixins import LoaderModuleMockMixin

# Salt testing libs
from tests.support.unit import TestCase


class BonjourAnnounceBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.avahi_announce
    """

    def setup_loader_modules(self):
        return {
            bonjour_announce: {
                "last_state": {},
                "last_state_extra": {"no_devices": False},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = bonjour_announce.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for bonjour_announce beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = bonjour_announce.validate(config)

        self.assertEqual(
            ret,
            (
                False,
                "Configuration for bonjour_announce"
                " beacon must contain servicetype, port"
                " and txt items.",
            ),
        )
