# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.load as load
import salt.utils.platform

import logging
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LoadBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.load
    '''

    def setup_loader_modules(self):
        return {
            load: {
                '__context__': {},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = load.validate(config)

        self.assertEqual(ret, (False, 'Configuration for load beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = load.validate(config)

        self.assertEqual(ret, (False, 'Averages configuration is required'
                                      ' for load beacon.'))

    @skipIf(salt.utils.platform.is_windows(),
            'os.getloadavg not available on Windows')
    def test_load_match(self):
        with patch('os.getloadavg',
                   MagicMock(return_value=(1.82, 1.84, 1.56))):
            config = [{'averages': {'1m': [0.0, 2.0],
                                    '5m': [0.0, 1.5],
                                    '15m': [0.0, 1.0]}}]

            ret = load.validate(config)

            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            _expected_return = [{'15m': 1.56, '1m': 1.82, '5m': 1.84}]
            ret = load.beacon(config)
            self.assertEqual(ret, _expected_return)
