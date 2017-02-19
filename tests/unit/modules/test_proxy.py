# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import proxy as proxy

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProxyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.proxy
    '''
    loader_module = proxy

    def loader_module_globals(self):
        return {'__grains__': {'os': 'Darwin'}}

    def test_get_http_proxy_macos(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on macOS
        '''
        mock = MagicMock(return_value='Enabled: Yes\nServer: 192.168.0.1\nPort: 3128\nAuthenticated Proxy Enabled: 0')
        expected = {
            'enabled': True,
            'server': '192.168.0.1',
            'port': '3128'
        }

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.get_http_proxy()
            mock.assert_called_once_with('networksetup -getwebproxy Ethernet')
            self.assertEqual(expected, out)

    def test_get_https_proxy_macos(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on macOS
        '''
        mock = MagicMock(return_value='Enabled: Yes\nServer: 192.168.0.1\nPort: 3128\nAuthenticated Proxy Enabled: 0')
        expected = {
            'enabled': True,
            'server': '192.168.0.1',
            'port': '3128'
        }

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.get_https_proxy()
            mock.assert_called_once_with('networksetup -getsecurewebproxy Ethernet')
            self.assertEqual(expected, out)

    def test_get_ftp_proxy_macos(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on macOS
        '''
        mock = MagicMock(return_value='Enabled: Yes\nServer: 192.168.0.1\nPort: 3128\nAuthenticated Proxy Enabled: 0')
        expected = {
            'enabled': True,
            'server': '192.168.0.1',
            'port': '3128'
        }

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.get_ftp_proxy()
            mock.assert_called_once_with('networksetup -getftpproxy Ethernet')
            self.assertEqual(expected, out)

    def test_get_http_proxy_macos_none(self):
        '''
            Test to make sure that we correctly return when theres no proxy set
        '''
        mock = MagicMock(return_value='Enabled: No\nServer:\nPort: 0\nAuthenticated Proxy Enabled: 0')

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.get_http_proxy()
            mock.assert_called_once_with('networksetup -getwebproxy Ethernet')
            self.assertEqual({}, out)

    def test_set_http_proxy_macos(self):
        '''
            Test to make sure that we correctly set the proxy info
            on macOS
        '''
        mock = MagicMock()

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.set_http_proxy('192.168.0.1', 3128, 'frank', 'badpassw0rd', bypass_hosts='.moo.com,.salt.com')
            mock.assert_called_once_with('networksetup -setwebproxy Ethernet 192.168.0.1 3128 On frank badpassw0rd')
            self.assertTrue(out)

    def test_set_https_proxy_macos(self):
        '''
            Test to make sure that we correctly set the proxy info
            on macOS
        '''
        mock = MagicMock()

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.set_https_proxy('192.168.0.1', 3128, 'frank', 'passw0rd', bypass_hosts='.moo.com,.salt.com')
            mock.assert_called_once_with('networksetup -setsecurewebproxy Ethernet 192.168.0.1 3128 On frank passw0rd')
            self.assertTrue(out)

    def test_set_ftp_proxy_macos(self):
        '''
            Test to make sure that we correctly set the proxy info
            on macOS
        '''
        mock = MagicMock()

        with patch.dict(proxy.__salt__, {'cmd.run': mock}):
            out = proxy.set_ftp_proxy('192.168.0.1', 3128, 'frank', 'badpassw0rd', bypass_hosts='.moo.com,.salt.com')
            mock.assert_called_once_with('networksetup -setftpproxy Ethernet 192.168.0.1 3128 On frank badpassw0rd')
            self.assertTrue(out)

    def test_get_http_proxy_windows(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            result = {
                'vdata': 'http=192.168.0.1:3128;https=192.168.0.2:3128;ftp=192.168.0.3:3128'
            }
            mock = MagicMock(return_value=result)
            expected = {
                'server': '192.168.0.1',
                'port': '3128'
            }
            with patch.dict(proxy.__salt__, {'reg.read_value': mock}):
                out = proxy.get_http_proxy()
                mock.assert_called_once_with('HKEY_CURRENT_USER',
                                             'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                                             'ProxyServer')
                self.assertEqual(expected, out)

    def test_get_https_proxy_windows(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            result = {
                'vdata': 'http=192.168.0.1:3128;https=192.168.0.2:3128;ftp=192.168.0.3:3128'
            }
            mock = MagicMock(return_value=result)
            expected = {
                'server': '192.168.0.2',
                'port': '3128'
            }
            with patch.dict(proxy.__salt__, {'reg.read_value': mock}):
                out = proxy.get_https_proxy()
                mock.assert_called_once_with('HKEY_CURRENT_USER',
                                             'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                                             'ProxyServer')
                self.assertEqual(expected, out)

    def test_get_ftp_proxy_windows(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            result = {
                'vdata': 'http=192.168.0.1:3128;https=192.168.0.2:3128;ftp=192.168.0.3:3128'
            }
            mock = MagicMock(return_value=result)
            expected = {
                'server': '192.168.0.3',
                'port': '3128'
            }
            with patch.dict(proxy.__salt__, {'reg.read_value': mock}):
                out = proxy.get_ftp_proxy()
                mock.assert_called_once_with('HKEY_CURRENT_USER',
                                             'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                                             'ProxyServer')
                self.assertEqual(expected, out)

    def test_get_all_proxies_macos_fails(self):
        mock = MagicMock()
        with patch.dict(proxy.__salt__, {'reg.read_value': mock}):
            out = proxy.get_proxy_win()
            assert not mock.called
            self.assertEqual(out, None)

    def test_get_all_proxies_windows(self):
        '''
            Test to make sure that we correctly get the current proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            results = [
                {
                    'vdata': 'http=192.168.0.1:3128;https=192.168.0.2:3128;ftp=192.168.0.3:3128'
                },
                {
                    'vdata': 1
                }
            ]
            mock = MagicMock(side_effect=results)

            expected = {
                'enabled': True,
                'http': {
                    'server': '192.168.0.1',
                    'port': '3128'
                },
                'https': {
                    'server': '192.168.0.2',
                    'port': '3128'
                },
                'ftp': {
                    'server': '192.168.0.3',
                    'port': '3128'
                }
            }
            with patch.dict(proxy.__salt__, {'reg.read_value': mock}):
                out = proxy.get_proxy_win()
                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable'),
                ]

                mock.assert_has_calls(calls)
                self.assertEqual(expected, out)

    def test_set_http_proxy_windows(self):
        '''
            Test to make sure that we correctly set the proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            mock_reg = MagicMock()
            mock_cmd = MagicMock()

            with patch.dict(proxy.__salt__, {'reg.set_value': mock_reg, 'cmd.run': mock_cmd}):
                out = proxy.set_http_proxy('192.168.0.1', 3128, bypass_hosts=['.moo.com', '.salt.com'])

                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer',
                         'http=192.168.0.1:3128;'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable',
                         1,
                         vtype='REG_DWORD'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyOverride',
                         '<local>;.moo.com;.salt.com')
                ]
                mock_reg.assert_has_calls(calls)
                mock_cmd.assert_called_once_with('netsh winhttp import proxy source=ie')
                self.assertTrue(out)

    def test_set_https_proxy_windows(self):
        '''
            Test to make sure that we correctly set the proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            mock_reg = MagicMock()
            mock_cmd = MagicMock()

            with patch.dict(proxy.__salt__, {'reg.set_value': mock_reg, 'cmd.run': mock_cmd}):
                out = proxy.set_https_proxy('192.168.0.1', 3128, bypass_hosts=['.moo.com', '.salt.com'])

                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer',
                         'https=192.168.0.1:3128;'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable',
                         1,
                         vtype='REG_DWORD'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyOverride',
                         '<local>;.moo.com;.salt.com')
                ]
                mock_reg.assert_has_calls(calls)
                mock_cmd.assert_called_once_with('netsh winhttp import proxy source=ie')
                self.assertTrue(out)

    def test_set_ftp_proxy_windows(self):
        '''
            Test to make sure that we correctly set the proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            mock_reg = MagicMock()
            mock_cmd = MagicMock()

            with patch.dict(proxy.__salt__, {'reg.set_value': mock_reg, 'cmd.run': mock_cmd}):
                out = proxy.set_ftp_proxy('192.168.0.1', 3128, bypass_hosts=['.moo.com', '.salt.com'])

                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer',
                         'ftp=192.168.0.1:3128;'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable',
                         1,
                         vtype='REG_DWORD'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyOverride',
                         '<local>;.moo.com;.salt.com')
                ]
                mock_reg.assert_has_calls(calls)
                mock_cmd.assert_called_once_with('netsh winhttp import proxy source=ie')
                self.assertTrue(out)

    def test_set_proxy_windows(self):
        '''
            Test to make sure that we correctly set the proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            mock_reg = MagicMock()
            mock_cmd = MagicMock()

            with patch.dict(proxy.__salt__, {'reg.set_value': mock_reg, 'cmd.run': mock_cmd}):
                out = proxy.set_proxy_win('192.168.0.1', 3128, bypass_hosts=['.moo.com', '.salt.com'])

                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer',
                         'http=192.168.0.1:3128;https=192.168.0.1:3128;ftp=192.168.0.1:3128;'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable',
                         1,
                         vtype='REG_DWORD'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyOverride',
                         '<local>;.moo.com;.salt.com')
                ]
                mock_reg.assert_has_calls(calls)
                mock_cmd.assert_called_once_with('netsh winhttp import proxy source=ie')
                self.assertTrue(out)

    def test_set_proxy_windows_no_ftp(self):
        '''
            Test to make sure that we correctly set the proxy info
            on Windows
        '''
        with patch.dict(proxy.__grains__, {'os': 'Windows'}):
            mock_reg = MagicMock()
            mock_cmd = MagicMock()

            with patch.dict(proxy.__salt__, {'reg.set_value': mock_reg, 'cmd.run': mock_cmd}):
                out = proxy.set_proxy_win('192.168.0.1', 3128, types=['http', 'https'],
                                          bypass_hosts=['.moo.com', '.salt.com'])

                calls = [
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyServer',
                         'http=192.168.0.1:3128;https=192.168.0.1:3128;'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyEnable',
                         1,
                         vtype='REG_DWORD'),
                    call('HKEY_CURRENT_USER',
                         'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings',
                         'ProxyOverride',
                         '<local>;.moo.com;.salt.com')
                ]
                mock_reg.assert_has_calls(calls)
                mock_cmd.assert_called_once_with('netsh winhttp import proxy source=ie')
                self.assertTrue(out)
