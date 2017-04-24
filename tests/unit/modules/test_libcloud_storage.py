# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.libcloud_storage as libcloud_storage


class MockStorageDriver(object):
    def __init__(self):
        pass


def get_mock_driver():
    return MockStorageDriver()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.libcloud_storage._get_driver',
       MagicMock(return_value=MockStorageDriver()))
class LibcloudStorageModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                })
            }
        }
        if libcloud_storage.HAS_LIBCLOUD is False:
            module_globals['sys.modules'] = {'libcloud': MagicMock()}

        return {libcloud_storage: module_globals}

    def test_module_creation(self):
        client = libcloud_storage._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_storage.__init__(None)
            dunder.assert_called_with('salt.modules.libcloud_storage')
