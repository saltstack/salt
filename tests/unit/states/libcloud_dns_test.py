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
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath
from salt.states import libcloud_dns

ensure_in_syspath('../../')

SERVICE_NAME = 'libcloud_dns'
libcloud_dns.__salt__ = {}
libcloud_dns.__utils__ = {}


class TestZone(object):
    def __init__(self, id, name):
        self.id = id
        self.name = name


class TestRecord(object):
    def __init__(self, id, type, data):
        self.id = id
        self.type = type
        self.data = data


class MockDNSDriver(object):
    def __init__(self):
        pass


def get_mock_driver():
    return MockDNSDriver()


class MockDnsModule(object):
    test_records = {
        0: [TestRecord(0, "AAAA", "www")]
    }

    def list_zones(self, profile):
        return [Zone(0, "test.com")]

    def list_records(self, zone_id, profile):
        return MockDnsModule.test_records[zone_id]


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.states.libcloud_dns._get_driver',
       MagicMock(return_value=MockDNSDriver()))
class LibcloudDnsModuleTestCase(ModuleTestCase):
    def setUp(self):
        hasDependency('libcloud')

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

    def test_present_record(self):
        result = libcloud_dns.record_present("www", "test.com", "A", "127.0.0.1", "test")
        self.assertTrue(result)

if __name__ == '__main__':
    from unit import run_tests
    run_tests(LibcloudDnsModuleTestCase)
