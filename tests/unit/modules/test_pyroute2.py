
from __future__ import absolute_import

from pyroute2 import IPDB
from tests.support.unit import TestCase
from salt.beacons.network_settings import ATTRS


class Pyroute2TestCase(TestCase):

    def test_interface_dict_fields(self):
        with IPDB() as ipdb:
            for attr in ATTRS:
                self.assertIn(attr, ipdb.interfaces[1])
