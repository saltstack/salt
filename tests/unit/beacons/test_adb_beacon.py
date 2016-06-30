# coding: utf-8

# Python libs
from __future__ import absolute_import

# 3rd-party libs
import pytest
mock = pytest.importorskip('mock', minversion='2.0.0')

# Salt libs
from salt.beacons import adb


@pytest.fixture(autouse=True)
def reset_adb():
    adb.__salt__ = {}
    adb.last_state = {}
    adb.last_state_extra = {'no_devices': False}


class TestADBBeacon(object):
    '''
    Test case for salt.beacons.adb
    '''
    def test_no_adb_command(self):
        with mock.patch('salt.utils.which') as mocked:
            mocked.return_value = None

            ret = adb.__virtual__()

            mocked.assert_called_once_with('adb')
            assert ret is False

    def test_with_adb_command(self):
        with mock.patch('salt.utils.which') as mocked:
            mocked.return_value = '/usr/bin/adb'

            ret = adb.__virtual__()

            mocked.assert_called_once_with('adb')
            assert ret == 'adb'

    def test_non_dict_config(self):
        config = []

        log_mock = mock.Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        assert ret == []
        log_mock.info.assert_called_once_with('Configuration for adb beacon must be a dict.')

    def test_empty_config(self):
        config = {}

        log_mock = mock.Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        assert ret == []
        log_mock.info.assert_called_once_with('Configuration for adb beacon must include a states array.')

    def test_invalid_states(self):
        config = {'states': ['Random', 'Failings']}

        log_mock = mock.Mock()
        adb.log = log_mock

        ret = adb.beacon(config)

        assert ret == []
        log_mock.info.assert_called_once_with('Need a one of the following adb states:'
                                              ' offline, bootloader, device, host, recovery, '
                                              'no permissions, sideload, unauthorized, unknown, missing')

    def test_device_state(self):
        config = {'states': ['device']}

        mocked = mock.Mock(return_value='List of devices attached\nHTC\tdevice',)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

    def test_device_state_change(self):
        config = {'states': ['offline']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\toffline'
        ]

        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):

            ret = adb.beacon(config)
            assert ret == []

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'offline', 'tag': 'offline'}]

    def test_multiple_devices(self):
        config = {'states': ['offline', 'device']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\toffline\nNexus\tdevice'
        ]

        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'offline', 'tag': 'offline'},
                           {'device': 'Nexus', 'state': 'device', 'tag': 'device'}]

    def test_no_devices_with_different_states(self):
        config = {'states': ['offline'], 'no_devices_event': True}

        mocked = mock.Mock(return_value='List of devices attached\nHTC\tdevice')
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):

            ret = adb.beacon(config)
            assert ret == []

    def test_no_devices_no_repeat(self):
        config = {'states': ['offline', 'device'], 'no_devices_event': True}

        out = [
            'List of devices attached',
            'List of devices attached'
        ]

        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):

            ret = adb.beacon(config)
            assert ret == [{'tag': 'no_devices'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_device_missing(self):
        config = {'states': ['device', 'missing']}

        out = [
            'List of devices attached\nHTC\tdevice',
            'List of devices attached',
            'List of devices attached\nHTC\tdevice',
            'List of devices attached\nHTC\tdevice'
        ]

        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'missing', 'tag': 'missing'}]

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_with_startup(self):
        config = {'states': ['device']}

        mocked = mock.Mock(return_value='* daemon started successfully *\nList of devices attached\nHTC\tdevice',)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

    def test_with_user(self):
        config = {'states': ['device'], 'user': 'fred'}

        mocked = mock.Mock(return_value='* daemon started successfully *\nList of devices attached\nHTC\tdevice',)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            mocked.assert_called_once_with('adb devices', runas='fred')
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

    def test_device_low_battery(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

    def test_device_no_repeat(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '25'
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_device_no_repeat_capacity_increase(self):
        config = {'states': ['device'], 'battery_low': 75}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '30'
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_device_no_repeat_with_not_found_state(self):
        config = {'states': ['offline'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
            'List of devices attached\nHTC\tdevice',
            '25'
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_device_battery_charged(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '100',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

    def test_device_low_battery_equal(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

    def test_device_battery_not_found(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '/system/bin/sh: cat: /sys/class/power_supply/*/capacity: No such file or directory',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

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
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

            ret = adb.beacon(config)
            assert ret == []

            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

            ret = adb.beacon(config)
            assert ret == []

    def test_weird_batteries(self):
        config = {'states': ['device'], 'battery_low': 25}

        out = [
            'List of devices attached\nHTC\tdevice',
            '-9000',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'}]

    def test_multiple_batteries(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25\n40',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]

    def test_multiple_low_batteries(self):
        config = {'states': ['device'], 'battery_low': 30}

        out = [
            'List of devices attached\nHTC\tdevice',
            '25\n14',
        ]
        mocked = mock.Mock(side_effect=out)
        with mock.patch.dict(adb.__salt__, {'cmd.run': mocked}):
            ret = adb.beacon(config)
            assert ret == [{'device': 'HTC', 'state': 'device', 'tag': 'device'},
                           {'device': 'HTC', 'battery_level': 25, 'tag': 'battery_low'}]
