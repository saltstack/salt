# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON
from tests.support.mixins import LoaderModuleMockMixin

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
