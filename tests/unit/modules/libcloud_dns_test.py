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
from salt.modules import libcloud_dns

ensure_in_syspath('../../')

SERVICE_NAME = 'libcloud_dns'
libcloud_dns.__salt__ = {}
libcloud_dns.__utils__ = {}


class MockDNSDriver(object):
    def __init__(self):
        pass


def get_mock_driver():
    return MockDNSDriver()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.libcloud_dns._get_driver',
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

    def test_module_creation(self, *args):
        client = libcloud_dns._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_dns.__init__(None)
            dunder.assert_called_with('salt.modules.libcloud_dns')

if __name__ == '__main__':
    from unit import run_tests
    run_tests(LibcloudDnsModuleTestCase)
