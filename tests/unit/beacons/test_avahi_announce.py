# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.avahi_announce as avahi_announce
from tests.support.mixins import LoaderModuleMockMixin

# Salt testing libs
from tests.support.unit import TestCase


class AvahiAnnounceBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.avahi_announce
    """

    def setup_loader_modules(self):
        return {
            avahi_announce: {
                "last_state": {},
                "last_state_extra": {"no_devices": False},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = avahi_announce.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for avahi_announce beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = avahi_announce.validate(config)

        self.assertEqual(
            ret,
            (
                False,
                "Configuration for avahi_announce"
                " beacon must contain servicetype, port"
                " and txt items.",
            ),
        )
