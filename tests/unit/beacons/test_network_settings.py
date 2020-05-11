# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON
from tests.support.mixins import LoaderModuleMockMixin
try:
    from pyroute2 import IPDB
    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False

# Salt libs
import salt.beacons.network_settings as network_settings

import logging
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkSettingsBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.network_settings
    '''

    def setup_loader_modules(self):
        return {
            network_settings: {
                '__context__': {},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = network_settings.validate(config)

        self.assertEqual(ret, (False, 'Configuration for network_settings'
                                      ' beacon must be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = network_settings.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))


@skipIf(not HAS_PYROUTE2, 'no pyroute2 installed, skipping')
class Pyroute2TestCase(TestCase):

    def test_interface_dict_fields(self):
        with IPDB() as ipdb:
            for attr in network_settings.ATTRS:
                # ipdb.interfaces is a dict-like object, that
                # contains interface definitions. Interfaces can
                # be referenced both with indices and names.
                #
                # ipdb.interfaces[1] is an interface with index 1,
                # that is the loopback interface.
                self.assertIn(attr, ipdb.interfaces[1])
