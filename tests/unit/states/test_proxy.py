# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch,
    call
)

# Import 3rd-party libs
import salt.ext.six as six

# Import Salt Libs
from salt.states import proxy as proxy


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProxyTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the proxy state
    '''
    loader_module = proxy

    def test_set_proxy_macos(self):
        '''
            Test to make sure we can set the proxy settings on macOS
        '''
        with patch.dict(proxy.__grains__, {'os': 'Darwin'}):
            expected = {'changes': {
                'new': [
                    {'port': '3128',
                     'server': '192.168.0.1',
                     'service': 'http',
                     'user': 'frank'},
                    {'port': '3128',
                     'server': '192.168.0.1',
                     'service': 'https',
                     'user': 'frank'},
                    {'port': '3128',
                     'server': '192.168.0.1',
                     'service': 'ftp',
                     'user': 'frank'},
                    {'bypass_domains': ['salt.com', 'test.com']}]
                },
                'comment': 'http proxy settings updated correctly\nhttps proxy settings updated correctly\nftp proxy '
                           'settings updated correctly\nProxy bypass domains updated correctly\n',
                'name': '192.168.0.1',
                'result': True}

            set_proxy_mock = MagicMock(return_value=True)
            patches = {
                'proxy.get_http_proxy': MagicMock(return_value={}),
                'proxy.get_https_proxy': MagicMock(return_value={}),
                'proxy.get_ftp_proxy': MagicMock(return_value={}),
                'proxy.get_proxy_bypass': MagicMock(return_value=[]),
                'proxy.set_http_proxy': set_proxy_mock,
                'proxy.set_https_proxy': set_proxy_mock,
                'proxy.set_ftp_proxy': set_proxy_mock,
                'proxy.set_proxy_bypass': set_proxy_mock,
            }

            with patch.dict(proxy.__salt__, patches):
                out = proxy.managed('192.168.0.1', '3128', user='frank', password='passw0rd',
                                    bypass_domains=['salt.com', 'test.com'])
                if six.PY3:
                    # Sorting is different in Py3
                    out['changes']['new'][-1]['bypass_domains'] = sorted(out['changes']['new'][-1]['bypass_domains'])

                calls = [
                    call('192.168.0.1', '3128', 'frank', 'passw0rd', 'Ethernet'),
                    call('192.168.0.1', '3128', 'frank', 'passw0rd', 'Ethernet'),
                    call('192.168.0.1', '3128', 'frank', 'passw0rd', 'Ethernet'),
                    call(['salt.com', 'test.com'], 'Ethernet')
                ]

                set_proxy_mock.assert_has_calls(calls)
                self.assertEqual(out, expected)

    def test_set_proxy_macos_same(self):
        '''
            Test to make sure we can set the proxy settings on macOS
        '''
        with patch.dict(proxy.__grains__, {'os': 'Darwin'}):
            expected = {'changes': {
                },
                'comment': 'http proxy settings already set.\nhttps proxy settings already set.\nftp proxy settings'
                           ' already set.\nProxy bypass domains are already set correctly.\n',
                'name': '192.168.0.1',
                'result': True}

            proxy_val = {
                'enabled': True,
                'server': '192.168.0.1',
                'port': '3128'
            }

            set_proxy_mock = MagicMock()
            patches = {
                'proxy.get_http_proxy': MagicMock(return_value=proxy_val),
                'proxy.get_https_proxy': MagicMock(return_value=proxy_val),
                'proxy.get_ftp_proxy': MagicMock(return_value=proxy_val),
                'proxy.get_proxy_bypass': MagicMock(return_value=['test.com', 'salt.com']),
                'proxy.set_http_proxy': set_proxy_mock,
                'proxy.set_https_proxy': set_proxy_mock,
                'proxy.set_ftp_proxy': set_proxy_mock,
                'proxy.set_proxy_bypass': set_proxy_mock,
            }

            with patch.dict(proxy.__salt__, patches):
                out = proxy.managed('192.168.0.1', '3128', user='frank', password='passw0rd',
                                    bypass_domains=['salt.com', 'test.com'])

                assert not set_proxy_mock.called
                self.assertEqual(out, expected)

    def test_set_proxy_windows(self):
        '''
            Test to make sure we can set the proxy settings on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            expected = {
                'changes': {},
                'comment': 'Proxy settings updated correctly',
                'name': '192.168.0.1',
                'result': True
            }

            set_proxy_mock = MagicMock(return_value=True)
            patches = {
                'proxy.get_proxy_win': MagicMock(return_value={}),
                'proxy.get_proxy_bypass': MagicMock(return_value=[]),
                'proxy.set_proxy_win': set_proxy_mock,
            }

            with patch.dict(proxy.__salt__, patches):
                out = proxy.managed('192.168.0.1', '3128', user='frank', password='passw0rd',
                                    bypass_domains=['salt.com', 'test.com'])

                set_proxy_mock.assert_called_once_with('192.168.0.1', '3128', ['http', 'https', 'ftp'],
                                                       ['salt.com', 'test.com'])
                self.assertEqual(out, expected)

    def test_set_proxy_windows_same(self):
        '''
            Test to make sure we can set the proxy settings on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            expected = {
                'changes': {},
                'comment': 'Proxy settings already correct.',
                'name': '192.168.0.1',
                'result': True
            }

            proxy_val = {
                'enabled': True,
                'http': {
                    'enabled': True,
                    'server': '192.168.0.1',
                    'port': '3128'
                },
                'https': {
                    'enabled': True,
                    'server': '192.168.0.1',
                    'port': '3128'
                },
                'ftp': {
                    'enabled': True,
                    'server': '192.168.0.1',
                    'port': '3128'
                }
            }

            set_proxy_mock = MagicMock(return_value=True)
            patches = {
                'proxy.get_proxy_win': MagicMock(return_value=proxy_val),
                'proxy.get_proxy_bypass': MagicMock(return_value=['salt.com', 'test.com']),
                'proxy.set_proxy_win': set_proxy_mock,
            }

            with patch.dict(proxy.__salt__, patches):
                out = proxy.managed('192.168.0.1', '3128', user='frank', password='passw0rd',
                                    bypass_domains=['salt.com', 'test.com'])

                assert not set_proxy_mock.called
                self.assertEqual(out, expected)
