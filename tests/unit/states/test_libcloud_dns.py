# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.unit import ModuleTestCase, hasDependency
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
from salt.states import libcloud_dns

SERVICE_NAME = 'libcloud_dns'
libcloud_dns.__salt__ = {}
libcloud_dns.__utils__ = {}


class TestZone(object):
    def __init__(self, id, domain):
        self.id = id
        self.domain = domain


class TestRecord(object):
    def __init__(self, id, name, type, data):
        self.id = id
        self.name = name
        self.type = type
        self.data = data


class MockDNSDriver(object):
    def __init__(self):
        pass


def get_mock_driver():
    return MockDNSDriver()


class MockDnsModule(object):
    test_records = {
        "zone1": [TestRecord(0, "www", "A", "127.0.0.1")]
    }

    def list_zones(self, profile):
        return [TestZone("zone1", "test.com")]

    def list_records(self, zone_id, profile):
        return MockDnsModule.test_records[zone_id]

    def create_record(self, *args):
        return True

    def delete_record(self, *args):
        return True

    def create_zone(self, *args):
        return True

    def delete_zone(self, *args):
        return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.states.libcloud_dns._get_driver',
       MagicMock(return_value=MockDNSDriver()))
class LibcloudDnsModuleTestCase(ModuleTestCase):
    def setUp(self):
        hasDependency('libcloud', fake_module=False)

        def get_config(service):
            if service == SERVICE_NAME:
                return {
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                }
            else:
                raise KeyError("service name invalid")

        self.setup_loader()
        self.loader.set_result(libcloud_dns, 'config.option', get_config)
        libcloud_dns.libcloud_dns_module = MockDnsModule()

    def test_module_creation(self, *args):
        client = libcloud_dns._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_dns.__init__(None)
            dunder.assert_called_with('salt.states.libcloud_dns')

    def test_present_record_exists(self):
        """
        Try and create a record that already exists
        """
        with patch.object(MockDnsModule, 'create_record', MagicMock(return_value=True)) as create_patch:
            result = libcloud_dns.record_present("www", "test.com", "A", "127.0.0.1", "test")
            self.assertTrue(result)
        self.assertFalse(create_patch.called)

    def test_present_record_does_not_exist(self):
        """
        Try and create a record that already exists
        """
        with patch.object(MockDnsModule, 'create_record') as create_patch:
            result = libcloud_dns.record_present("mail", "test.com", "A", "127.0.0.1", "test")
            self.assertTrue(result)
        create_patch.assert_called_with('mail', "zone1", "A", "127.0.0.1", "test")

    def test_absent_record_exists(self):
        """
        Try and deny a record that already exists
        """
        with patch.object(MockDnsModule, 'delete_record', MagicMock(return_value=True)) as create_patch:
            result = libcloud_dns.record_absent("www", "test.com", "A", "127.0.0.1", "test")
            self.assertTrue(result)
        create_patch.assert_called_with('zone1', 0, 'test')

    def test_absent_record_does_not_exist(self):
        """
        Try and deny a record that already exists
        """
        with patch.object(MockDnsModule, 'delete_record') as create_patch:
            result = libcloud_dns.record_absent("mail", "test.com", "A", "127.0.0.1", "test")
            self.assertTrue(result)
        self.assertFalse(create_patch.called)

    def test_present_zone_not_found(self):
        """
        Assert that when you try and ensure present state for a record to a zone that doesn't exist
        it fails gracefully
        """
        result = libcloud_dns.record_present("mail", "notatest.com", "A", "127.0.0.1", "test")
        self.assertFalse(result['result'])

    def test_absent_zone_not_found(self):
        """
        Assert that when you try and ensure absent state for a record to a zone that doesn't exist
        it fails gracefully
        """
        result = libcloud_dns.record_absent("mail", "notatest.com", "A", "127.0.0.1", "test")
        self.assertFalse(result['result'])

    def test_zone_present(self):
        """
        Assert that a zone is present (that did not exist)
        """
        with patch.object(MockDnsModule, 'create_zone') as create_patch:
            result = libcloud_dns.zone_present('testing.com', 'master', 'test1')
            self.assertTrue(result)
        self.assertTrue(create_patch.called)
        create_patch.assert_called_with('testing.com', 'test1', 'master')

    def test_zone_already_present(self):
        """
        Assert that a zone is present (that did exist)
        """
        with patch.object(MockDnsModule, 'create_zone') as create_patch:
            result = libcloud_dns.zone_present('test.com', 'master', 'test1')
            self.assertTrue(result)
        self.assertFalse(create_patch.called)

    def test_zone_absent(self):
        """
        Assert that a zone that did exist is absent
        """
        with patch.object(MockDnsModule, 'delete_zone') as create_patch:
            result = libcloud_dns.zone_absent('test.com', 'test1')
            self.assertTrue(result)
        self.assertTrue(create_patch.called)
        create_patch.assert_called_with('zone1', 'test1')

    def test_zone_already_absent(self):
        """
        Assert that a zone that did not exist is absent
        """
        with patch.object(MockDnsModule, 'delete_zone') as create_patch:
            result = libcloud_dns.zone_absent('testing.com', 'test1')
            self.assertTrue(result)
        self.assertFalse(create_patch.called)
