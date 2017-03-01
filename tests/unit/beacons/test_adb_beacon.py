# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, Mock

# Salt libs
from salt.beacons import adb

# Globals
adb.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ADBBeaconTestCase(TestCase):
    '''
    Test case for salt.beacons.adb
    '''
    def setUp(self):
        adb.last_state = {}
        adb.last_state_extra = {'no_devices': False}

    def test_no_adb_command(self):
        with patch('salt.utils.which') as mock:
            mock.return_value = None

            ret = adb.__virtual__()

            mock.assert_called_once_with('adb')
            self.assertFalse(ret)

    def test_with_adb_command(self):
        with patch('salt.utils.which') as mock:
            mock.return_value = '/usr/bin/adb'

            ret = adb.__virtual__()

            mock.assert_called_once_with('adb')
            self.assertEqual(ret, 'adb')

    def test_non_dict_config(self):
        config = []

        log_mock = Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        self.assertEqual(ret, [])
        log_mock.info.assert_called_once_with('Configuration for adb beacon must be a dict.')

    def test_empty_config(self):
        config = {}

        log_mock = Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        self.assertEqual(ret, [])
        log_mock.info.assert_called_once_with('Configuration for adb beacon must include a states array.')

    def test_invalid_states(self):
        config = {'states': ['Random', 'Failings']}

        log_mock = Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        self.assertEqual(ret, [])
        log_mock.info.assert_called_once_with('Need a one of the following adb states:'
                                              ' offline, bootloader, device, host, recovery, '
                                              'no permissions, sideload, unauthorized, unknown, missing')

    def test_device_state(self):
        config = {'states': ['device']}

        mock = Mock(return_value='List of devices attached\nHTC\tdevice',)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_device_state_change(self):
        config = {'states': ['offline']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\toffline'
        ]

        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'offline', 'tag': 'offline'}])

    def test_multiple_devices(self):
        config = {'states': ['offline', 'device']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\toffline\nNexus\tdevice'
        ]

        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [
                {'device': 'HTC', 'state': 'offline', 'tag': 'offline'},
                {'device': 'Nexus', 'state': 'device', 'tag': 'device'}
            ])

    def test_no_devices_with_different_states(self):
        config = {'states': ['offline'], 'no_devices_event': True}

        mock = Mock(return_value='List of devices attached\nHTC\tdevice')
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_no_devices_no_repeat(self):
        config = {'states': ['offline', 'device'], 'no_devices_event': True}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached',
            'List of devices attached'
        ]

        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'tag': 'no_devices'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_no_devices(self):
        config = {'states': ['offline', 'device'], 'no_devices_event': True}

        out = [
            'List of devices attached',
            'List of devices attached'
        ]

        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'tag': 'no_devices'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_device_missing(self):
        config = {'states': ['device', 'missing']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached',
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\tdevice'
        ]

        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'missing', 'tag': 'missing'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_with_startup(self):
        config = {'states': ['device']}

        mock = Mock(return_value='* daemon started successfully *\nList of devices attached\nHTC\tdevice',)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_with_user(self):
        config = {'states': ['device'], 'user': 'fred'}

        mock = Mock(return_value='* daemon started successfully *\nList of devices attached\nHTC\tdevice',)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            mock.assert_called_once_with('adb devices', runas='fred')
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_device_low_battery(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

    def test_device_no_repeat(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '25'
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_device_no_repeat_capacity_increase(self):
        config = {'states': ['device'], 'battery_low': 75}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '30'
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_device_no_repeat_with_not_found_state(self):
        config = {'states': ['offline'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '25'
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_device_battery_charged(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '100',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_device_low_battery_equal(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

    def test_device_battery_not_found(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '/system/bin/sh: cat: /sys/class/power_supply/*/capacity: No such file or directory',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_device_repeat_multi(self):
        config = {'states': ['offline'], 'battery_low': 35}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '40',
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '80'
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

            ret = adb.beacon(config)
            self.assertEqual(ret, [])

    def test_weird_batteries(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '-9000',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'}])

    def test_multiple_batteries(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25\n40',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])

    def test_multiple_low_batteries(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25\n14',
        ]
        mock = Mock(side_effect=out)
        with patch.dict(adb.__salt__, {'cmd.run': mock}):
            ret = adb.beacon(config)
            self.assertEqual(ret, [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                                   {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}])
