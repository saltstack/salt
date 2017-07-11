# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.sensehat as sensehat

HUMIDITY_MOCK = MagicMock(return_value='70%')
TEMPERATURE_MOCK = MagicMock(return_value=30)
TEMPERATURE_PRESSURE_MOCK = MagicMock(return_value=30)
PRESSURE_MOCK = MagicMock(return_value=1500)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SensehatBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.[s]
    '''

    def setup_loader_modules(self):
        return {
            sensehat: {
                '__context__': {},
                '__salt__': {},
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

        with patch.dict(sensehat.__salt__,
                        {'sensehat.get_humidity': HUMIDITY_MOCK}):
            config = [{'sensors': {'humidity': '70%'}}]

            ret = sensehat.validate(config)

            ret = sensehat.beacon(config)
            self.assertEqual(ret, [{'tag': 'sensehat/humidity',
                                    'humidity': '70%'}])

    def test_sensehat_temperature_match(self):

        with patch.dict(sensehat.__salt__,
                        {'sensehat.get_temperature': TEMPERATURE_MOCK}):
            config = [{'sensors': {'temperature': 20}}]

            ret = sensehat.validate(config)

            ret = sensehat.beacon(config)
            self.assertEqual(ret, [{'tag': 'sensehat/temperature',
                                    'temperature': 30}])

    def test_sensehat_temperature_match_range(self):

        with patch.dict(sensehat.__salt__,
                        {'sensehat.get_temperature': TEMPERATURE_MOCK}):
            config = [{'sensors': {'temperature': [20, 29]}}]

            ret = sensehat.validate(config)

            ret = sensehat.beacon(config)
            self.assertEqual(ret, [{'tag': 'sensehat/temperature',
                                    'temperature': 30}])

    def test_sensehat_pressure_match(self):

        with patch.dict(sensehat.__salt__,
                        {'sensehat.get_pressure': PRESSURE_MOCK}):
            config = [{'sensors': {'pressure': '1400'}}]

            ret = sensehat.validate(config)

            ret = sensehat.beacon(config)
            self.assertEqual(ret, [{'tag': 'sensehat/pressure',
                                    'pressure': 1500}])

    def test_sensehat_no_match(self):

        with patch.dict(sensehat.__salt__,
                        {'sensehat.get_pressure': PRESSURE_MOCK}):
            config = [{'sensors': {'pressure': '1600'}}]

            ret = sensehat.validate(config)

            ret = sensehat.beacon(config)
            self.assertEqual(ret, [])
