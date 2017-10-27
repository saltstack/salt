# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf
from tests.unit import ModuleTestCase, hasDependency
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath
from salt.states import libcloud_dns

ensure_in_syspath('../../')

SERVICE_NAME = 'libcloud_dns'
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


test_records = {
    "zone1": [TestRecord(0, "www", "A", "127.0.0.1")]
}


def list_zones(profile):
    return [TestZone("zone1", "test.com")]


def list_records(zone_id, profile):
    return test_records[zone_id]


def create_record(*args):
    return True


def delete_record(*args):
    return True


def create_zone(*args):
    return True


def delete_zone(*args):
    return True


libcloud_dns.__salt__ = {
    'libcloud_dns.list_zones': list_zones,
    'libcloud_dns.list_records': list_records,
    'libcloud_dns.create_record': create_record,
    'libcloud_dns.delete_record': delete_record,
    'libcloud_dns.create_zone': create_zone,
    'libcloud_dns.delete_zone': delete_zone
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
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

    def test_present_record_exists(self):
        """
        Try and create a record that already exists
        """
        result = libcloud_dns.record_present("www", "test.com", "A", "127.0.0.1", "test")
        self.assertTrue(result)

    def test_present_record_does_not_exist(self):
        """
        Try and create a record that already exists
        """
        result = libcloud_dns.record_present("mail", "test.com", "A", "127.0.0.1", "test")
        self.assertTrue(result)

    def test_absent_record_exists(self):
        """
        Try and deny a record that already exists
        """
        result = libcloud_dns.record_absent("www", "test.com", "A", "127.0.0.1", "test")
        self.assertTrue(result)

    def test_absent_record_does_not_exist(self):
        """
        Try and deny a record that already exists
        """
        result = libcloud_dns.record_absent("mail", "test.com", "A", "127.0.0.1", "test")
        self.assertTrue(result)

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
        result = libcloud_dns.zone_present('testing.com', 'master', 'test1')
        self.assertTrue(result)

    def test_zone_already_present(self):
        """
        Assert that a zone is present (that did exist)
        """
        result = libcloud_dns.zone_present('test.com', 'master', 'test1')
        self.assertTrue(result)

    def test_zone_absent(self):
        """
        Assert that a zone that did exist is absent
        """
        result = libcloud_dns.zone_absent('test.com', 'test1')
        self.assertTrue(result)

    def test_zone_already_absent(self):
        """
        Assert that a zone that did not exist is absent
        """
        result = libcloud_dns.zone_absent('testing.com', 'test1')
        self.assertTrue(result)

if __name__ == '__main__':
    from unit import run_tests
    run_tests(LibcloudDnsModuleTestCase)
