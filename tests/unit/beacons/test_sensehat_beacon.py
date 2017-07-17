# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.sensehat as sensehat


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SensehatBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.[s]
    '''

    def setup_loader_modules(self):

        self.HUMIDITY_MOCK = MagicMock(return_value=80)
        self.TEMPERATURE_MOCK = MagicMock(return_value=30)
        self.PRESSURE_MOCK = MagicMock(return_value=1500)

        self.addCleanup(delattr, self, 'HUMIDITY_MOCK')
        self.addCleanup(delattr, self, 'TEMPERATURE_MOCK')
        self.addCleanup(delattr, self, 'PRESSURE_MOCK')

        return {
            sensehat: {
                '__context__': {},
                '__salt__': {'sensehat.get_humidity': self.HUMIDITY_MOCK,
                             'sensehat.get_temperature': self.TEMPERATURE_MOCK,
                             'sensehat.get_pressure': self.PRESSURE_MOCK
                             },
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = sensehat.validate(config)

        self.assertEqual(ret, (False, 'Configuration for sensehat beacon'
                                      ' must be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = sensehat.validate(config)

        self.assertEqual(ret, (False, 'Configuration for sensehat '
                                      'beacon requires sensors.'))

    def test_sensehat_humidity_match(self):

        config = [{'sensors': {'humidity': '70%'}}]

        ret = sensehat.validate(config)

        ret = sensehat.beacon(config)
        self.assertEqual(ret, [{'tag': 'sensehat/humidity',
                                'humidity': 80}])

    def test_sensehat_temperature_match(self):

        config = [{'sensors': {'temperature': 20}}]

        ret = sensehat.validate(config)

        ret = sensehat.beacon(config)
        self.assertEqual(ret, [{'tag': 'sensehat/temperature',
                                'temperature': 30}])

    def test_sensehat_temperature_match_range(self):

        config = [{'sensors': {'temperature': [20, 29]}}]

        ret = sensehat.validate(config)

        ret = sensehat.beacon(config)
        self.assertEqual(ret, [{'tag': 'sensehat/temperature',
                                'temperature': 30}])

    def test_sensehat_pressure_match(self):

        config = [{'sensors': {'pressure': '1400'}}]

        ret = sensehat.validate(config)

        ret = sensehat.beacon(config)
        self.assertEqual(ret, [{'tag': 'sensehat/pressure',
                                'pressure': 1500}])

    def test_sensehat_no_match(self):

        config = [{'sensors': {'pressure': '1600'}}]

        ret = sensehat.validate(config)

        ret = sensehat.beacon(config)
        self.assertEqual(ret, [])
