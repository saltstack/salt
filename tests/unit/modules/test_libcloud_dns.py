# -*- coding: utf-8 -*-
'''
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.libcloud_dns as libcloud_dns


class MockDNSDriver(object):
    def __init__(self):
        pass

    def list_record_types(self, *args, **kwargs):
        raise NotImplementedError()

    def list_zones(self, *args, **kwargs):
        raise NotImplementedError()

    def list_records(self, zone):
        raise NotImplementedError()

    def get_zone(self, zone_id):
        raise NotImplementedError()

    def get_record(self, zone_id, record_id):
        raise NotImplementedError()

    def create_zone(self, domain, type='master', ttl=None, extra=None):
        raise NotImplementedError()

    def update_zone(self, zone, domain, type='master', ttl=None, extra=None):
        raise NotImplementedError()

    def create_record(self, name, zone, type, data, extra=None):
        raise NotImplementedError()

    def update_record(self, record, name, type, data, extra=None):
        raise NotImplementedError()

    def delete_zone(self, zone):
        raise NotImplementedError()

    def delete_record(self, record):
        raise NotImplementedError()


class TestZone(object):
    '''
    Reflects an instance of libcloud.dns.base.Zone
    '''
    id = '12345'
    domain = 'test.com'
    type = 'master'
    ttl = 3600
    driver = MockDNSDriver()
    extra = {'k': 'v'}


'''
Dictionary version of the test zone
'''
_DICT_TEST_ZONE = {
    'id': '12345',
    'domain': 'test.com',
    'type': 'master',
    'ttl': 3600,
    'extra': {'k': 'v'}
}


class TestRecord(object):
    '''
    Reflects an instance of libcloud.dns.base.Record
    '''
    id = '45678'
    name = 'www'
    type = 'A'
    data = '1.2.3.4'
    zone = TestZone()
    driver = MockDNSDriver()
    ttl = 600
    extra = {'y': 'x'}


'''
Dictionary version of the test zone
'''
_DICT_TEST_RECORD = {
    'id': '45678',
    'name': 'www',
    'type': 'A',
    'data': '1.2.3.4',
    'ttl': 600,
    'extra': {'y': 'x'},
    'zone': _DICT_TEST_ZONE
}


def get_mock_driver():
    return MockDNSDriver()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LibcloudDnsModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '_get_driver': MagicMock(return_value=MockDNSDriver()),
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                })
            }
        }
        if libcloud_dns.HAS_LIBCLOUD is False:
            module_globals['sys.modules'] = {'libcloud': MagicMock()}

        return {libcloud_dns: module_globals}

    def test_module_creation(self):
        client = libcloud_dns._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_dns.__init__(None)
            dunder.assert_called_with('salt.modules.libcloud_dns')

    def test_list_record_types(self):
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.list_record_types', return_value=[]) as method:
            types = libcloud_dns.list_record_types('test')
            self.assertEqual(types, [])
            method.assert_called_once()
            method.assert_called_with()

    def test_list_zones(self):
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.list_zones', return_value=[TestZone()]) as method:
            types = libcloud_dns.list_zones('test')
            self.assertEqual(types, [_DICT_TEST_ZONE])
            method.assert_called_once()
            method.assert_called_with()

    def test_list_records(self):
        zone = TestZone()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.get_zone', return_value=zone) as get_zone:
            with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.list_records', return_value=[TestRecord()]) as method:
                types = libcloud_dns.list_records('12345', 'test')
                self.assertEqual(types, [_DICT_TEST_RECORD])
                method.assert_called_once()
                method.assert_called_with(zone)
                get_zone.assert_called_once()
                get_zone.assert_called_with('12345')

    def test_list_records_by_type(self):
        zone = TestZone()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.get_zone', return_value=zone) as get_zone:
            with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.list_records', return_value=[TestRecord()]) as method:
                types = libcloud_dns.list_records('12345', 'test', 'NS')
                self.assertEqual(types, [])
                method.assert_called_once()
                method.assert_called_with(zone)
                get_zone.assert_called_once()
                get_zone.assert_called_with('12345')

    def test_get_zone(self):
        zone = TestZone()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.get_zone', return_value=zone) as get_zone:
            zone = libcloud_dns.get_zone('12345', 'test')
            self.assertEqual(zone, _DICT_TEST_ZONE)
            get_zone.assert_called_once()
            get_zone.assert_called_with('12345')

    def test_get_record(self):
        record = TestRecord()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.get_record', return_value=record) as get_record:
            record = libcloud_dns.get_record('12345', '45678', 'test')
            self.assertEqual(record, _DICT_TEST_RECORD)
            get_record.assert_called_once()
            get_record.assert_called_with('12345', '45678')

    def test_create_zone(self):
        zone = TestZone()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.create_zone', return_value=zone) as create_zone:
            zone = libcloud_dns.create_zone('test.com', 'test', type='slave', ttl=400, extra={'extra': 'data'})
            self.assertEqual(zone, _DICT_TEST_ZONE)
            create_zone.assert_called_once()
            create_zone.assert_called_with('test.com', type='slave', ttl=400, extra={'extra': 'data'})

    def test_update_zone(self):
        test_zone = TestZone()
        with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.get_zone', return_value=test_zone) as get_zone:
            with patch('tests.unit.modules.test_libcloud_dns.MockDNSDriver.update_zone', return_value=test_zone) as update_zone:
                zone = libcloud_dns.update_zone('12345', 'test.com', 'test', type='slave', ttl=400, extra={'extra': 'data'})
                self.assertEqual(zone, _DICT_TEST_ZONE)
                update_zone.assert_called_once()
                update_zone.assert_called_with(zone=test_zone, domain='test.com', type='slave', ttl=400, extra={'extra': 'data'})
                get_zone.assert_called_once()
                get_zone.assert_called_with('12345')