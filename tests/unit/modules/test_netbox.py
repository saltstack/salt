# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Zach Moody <zmoody@do.co>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    import pynetbox  # pylint: disable=unused-import
    HAS_PYNETBOX = True
except ImportError:
    HAS_PYNETBOX = False

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    call,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.netbox as netbox

NETBOX_RESPONSE_STUB = {
    'device_name': 'test1-router1',
    'url': 'http://test/',
    'device_role': {
        'name': 'router',
        'url': 'http://test/'
    }
}


@skipIf(HAS_PYNETBOX is False, 'pynetbox lib not installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.netbox._config', MagicMock())
class NetBoxTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            netbox: {},
        }

    def test_get_by_id(self):
        with patch('pynetbox.api', MagicMock()) as mock:
            netbox.get('dcim', 'devices', id=1)
            self.assertEqual(
                mock.mock_calls[1],
                call().dcim.devices.get(1)
            )

    def test_get_by_name(self):
        with patch('pynetbox.api', MagicMock()) as mock:
            netbox.get('dcim', 'devices', name='test')
            self.assertEqual(
                mock.mock_calls[1],
                call().dcim.devices.get(name='test')
            )

    def test_filter_by_site(self):
        with patch('pynetbox.api', MagicMock()) as mock:
            netbox.filter('dcim', 'devices', site='test')
            self.assertEqual(
                mock.mock_calls[1],
                call().dcim.devices.filter(site='test')
            )

    def test_filter_url(self):
        strip_url = netbox._strip_url_field(NETBOX_RESPONSE_STUB)
        self.assertTrue(
            'url' not in strip_url and 'url' not in strip_url['device_role']
        )

    def test_get_secret(self):
        with patch('pynetbox.api', MagicMock()) as mock:
            netbox.get('secrets', 'secrets', name='test')
            self.assertTrue(
                'token' and 'private_key_file' in mock.call_args[1]
            )
