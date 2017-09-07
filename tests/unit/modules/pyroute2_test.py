# -*- coding: UTF-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
from salt.beacons.network_settings import ATTRS

# Import Third Party libs
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(Pyroute2TestCase, needs_daemon=False)
