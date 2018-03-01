# -*- coding: UTF-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import TestCase
from tests.support.unit import skipIf
from salt.beacons.network_settings import ATTRS
try:
    from pyroute2 import IPDB
    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False


@skipIf(not HAS_PYROUTE2, 'no pyroute2 installed, skipping')
class Pyroute2TestCase(TestCase):

    def test_interface_dict_fields(self):
        with IPDB() as ipdb:
            for attr in ATTRS:
                # ipdb.interfaces is a dict-like object, that
                # contains interface definitions. Interfaces can
                # be referenced both with indices and names.
                #
                # ipdb.interfaces[1] is an interface with index 1,
                # that is the loopback interface.
                self.assertIn(attr, ipdb.interfaces[1])
