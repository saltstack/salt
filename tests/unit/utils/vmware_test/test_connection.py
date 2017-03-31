# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for connections related functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging
import base64
import ssl
import sys

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, call, \
        PropertyMock
import salt.exceptions as excs

# Import Salt libraries
import salt.utils.vmware
# Import Third Party Libs
try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

try:
    import gssapi
    HAS_GSSAPI = True
except ImportError:
    HAS_GSSAPI = False

if sys.version_info[:3] > (2, 7, 8):
    SSL_VALIDATION = True
else:
    SSL_VALIDATION = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
@patch('gssapi.Name', MagicMock(return_value='service'))
@patch('gssapi.InitContext', MagicMock())
class GssapiTokenTest(TestCase):
    '''
    Test cases for salt.utils.vmware.get_gssapi_token
    '''

    @patch('salt.utils.vmware.HAS_GSSAPI', False)
    def test_no_gssapi(self):
        with self.assertRaises(ImportError) as excinfo:
            salt.utils.vmware.get_gssapi_token('principal', 'host', 'domain')
            self.assertIn('The gssapi library is not imported.',
                          excinfo.exception.message)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_service_name(self):
        mock_name = MagicMock()
        with patch.object(salt.utils.vmware.gssapi, 'Name', mock_name):

            with self.assertRaises(excs.CommandExecutionError):
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            mock_name.assert_called_once_with('principal/host@domain',
                                              gssapi.C_NT_USER_NAME)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_out_token_defined(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = False
        mock_context.return_value.step = MagicMock(return_value='out_token')
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            ret = salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                     'domain')
            self.assertEqual(mock_context.return_value.step.called, 1)
            self.assertEqual(ret, base64.b64encode('out_token'))

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_out_token_undefined(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = False
        mock_context.return_value.step = MagicMock(return_value=None)
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            with self.assertRaises(excs.CommandExecutionError) as excinfo:
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            self.assertEqual(mock_context.return_value.step.called, 1)
            self.assertIn('Can\'t receive token',
                          excinfo.exception.strerror)

    @skipIf(not HAS_GSSAPI, 'The \'gssapi\' library is missing')
    def test_context_extablished(self):
        mock_context = MagicMock(return_value=MagicMock())
        mock_context.return_value.established = True
        mock_context.return_value.step = MagicMock(return_value='out_token')
        with patch.object(salt.utils.vmware.gssapi, 'InitContext',
                          mock_context):
            mock_context.established = True
            mock_context.step = MagicMock(return_value=None)
            with self.assertRaises(excs.CommandExecutionError) as excinfo:
                salt.utils.vmware.get_gssapi_token('principal', 'host',
                                                   'domain')
            self.assertEqual(mock_context.step.called, 0)
            self.assertIn('Context established, but didn\'t receive token',
                          excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.SmartConnect', MagicMock())
@patch('salt.utils.vmware.Disconnect', MagicMock())
@patch('salt.utils.vmware.get_gssapi_token',
       MagicMock(return_value='fake_token'))
class PrivateGetServiceInstanceTestCase(TestCase):
    '''Tests for salt.utils.vmware._get_service_instance'''

    def test_invalid_mechianism(self):
        with self.assertRaises(excs.CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='invalid_mechanism',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('Unsupported mechanism', excinfo.exception.strerror)

    def test_userpass_mechanism_empty_username(self):
        with self.assertRaises(excs.CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username=None,
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('mandatory parameter \'username\'',
                      excinfo.exception.strerror)

    def test_userpass_mechanism_empty_password(self):
        with self.assertRaises(excs.CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password=None,
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
        self.assertIn('mandatory parameter \'password\'',
                      excinfo.exception.strerror)

    def test_userpass_mechanism_no_domain(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain=None)
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')

    def test_userpass_mech_domain_unused(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username@domain',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username@domain',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')
            mock_sc.reset_mock()
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='domain\\fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='userpass',
                principal='fake principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='domain\\fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token=None,
                mechanism='userpass')

    def test_sspi_empty_principal(self):
        with self.assertRaises(excs.CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal=None,
                domain='fake_domain')
        self.assertIn('mandatory parameters are missing',
                      excinfo.exception.strerror)

    def test_sspi_empty_domain(self):
        with self.assertRaises(excs.CommandExecutionError) as excinfo:
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal='fake_principal',
                domain=None)
        self.assertIn('mandatory parameters are missing',
                      excinfo.exception.strerror)

    def test_sspi_get_token_error(self):
        mock_token = MagicMock(side_effect=Exception('Exception'))

        with patch('salt.utils.vmware.get_gssapi_token', mock_token):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')
            mock_token.assert_called_once_with('fake_principal',
                                               'fake_host.fqdn',
                                               'fake_domain')
            self.assertEqual('Exception', excinfo.exception.strerror)

    def test_sspi_get_token_success_(self):
        mock_token = MagicMock(return_value='fake_token')
        mock_sc = MagicMock()

        with patch('salt.utils.vmware.get_gssapi_token', mock_token):
            with patch('salt.utils.vmware.SmartConnect', mock_sc):
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')
            mock_token.assert_called_once_with('fake_principal',
                                               'fake_host.fqdn',
                                               'fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token='fake_token',
                mechanism='sspi')

    def test_first_attempt_successful_connection(self):
        mock_sc = MagicMock()
        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            salt.utils.vmware._get_service_instance(
                host='fake_host.fqdn',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='sspi',
                principal='fake_principal',
                domain='fake_domain')
            mock_sc.assert_called_once_with(
                host='fake_host.fqdn',
                user='fake_username',
                pwd='fake_password',
                protocol='fake_protocol',
                port=1,
                b64token='fake_token',
                mechanism='sspi')

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_second_attempt_successful_connection(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        mock_sc = MagicMock(side_effect=[exc, None])
        mock_ssl = MagicMock()

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with patch('ssl._create_unverified_context',
                       mock_ssl):

                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                mock_ssl.assert_called_once_with()
                calls = [call(host='fake_host.fqdn',
                              user='fake_username',
                              pwd='fake_password',
                              protocol='fake_protocol',
                              port=1,
                              b64token='fake_token',
                              mechanism='sspi'),
                         call(host='fake_host.fqdn',
                              user='fake_username',
                              pwd='fake_password',
                              protocol='fake_protocol',
                              port=1,
                              sslContext=mock_ssl.return_value,
                              b64token='fake_token',
                              mechanism='sspi')]
                mock_sc.assert_has_calls(calls)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_third_attempt_successful_connection(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        exc2 = Exception('certificate verify failed')
        mock_sc = MagicMock(side_effect=[exc, exc2, None])
        mock_ssl_unverif = MagicMock()
        mock_ssl_context = MagicMock()

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with patch('ssl._create_unverified_context',
                       mock_ssl_unverif):

                with patch('ssl.SSLContext', mock_ssl_context):

                    salt.utils.vmware._get_service_instance(
                        host='fake_host.fqdn',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='sspi',
                        principal='fake_principal',
                        domain='fake_domain')

                    mock_ssl_context.assert_called_once_with(ssl.PROTOCOL_TLSv1)
                    mock_ssl_unverif.assert_called_once_with()
                    calls = [call(host='fake_host.fqdn',
                                  user='fake_username',
                                  pwd='fake_password',
                                  protocol='fake_protocol',
                                  port=1,
                                  b64token='fake_token',
                                  mechanism='sspi'),
                             call(host='fake_host.fqdn',
                                  user='fake_username',
                                  pwd='fake_password',
                                  protocol='fake_protocol',
                                  port=1,
                                  sslContext=mock_ssl_unverif.return_value,
                                  b64token='fake_token',
                                  mechanism='sspi'),
                             call(host='fake_host.fqdn',
                                  user='fake_username',
                                  pwd='fake_password',
                                  protocol='fake_protocol',
                                  port=1,
                                  sslContext=mock_ssl_context.return_value,
                                  b64token='fake_token',
                                  mechanism='sspi'),
                            ]
                    mock_sc.assert_has_calls(calls)

    def test_first_attempt_unsuccessful_connection_default_error(self):
        exc = Exception('Exception')
        mock_sc = MagicMock(side_effect=exc)

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 1)
                self.assertIn('Could not connect to host \'fake_host.fqdn\'',
                              excinfo.Exception.message)

    def test_first_attempt_unsuccessful_connection_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault'
        mock_sc = MagicMock(side_effect=exc)

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 1)
                self.assertEqual('VimFault', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_second_attempt_unsuccsessful_connection_default_error(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        exc2 = Exception('Exception')
        mock_sc = MagicMock(side_effect=[exc, exc2])

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 2)
                self.assertIn('Could not connect to host \'fake_host.fqdn\'',
                              excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_second_attempt_unsuccsessful_connection_vim_fault(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        exc2 = vim.fault.VimFault()
        exc2.msg = 'VimFault'
        mock_sc = MagicMock(side_effect=[exc, exc2])

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 2)
                self.assertIn('VimFault', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_third_attempt_unsuccessful_connection_detault_error(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        exc2 = Exception('certificate verify failed')
        exc3 = Exception('Exception')
        mock_sc = MagicMock(side_effect=[exc, exc2, exc3])

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 3)
                self.assertIn('Exception', excinfo.Exception.message)

    @skipIf(not SSL_VALIDATION, 'SSL validation is not enabled')
    @patch('ssl.SSLContext', MagicMock())
    @patch('ssl._create_unverified_context', MagicMock())
    def test_third_attempt_unsuccessful_connection_vim_fault(self):
        exc = vim.fault.HostConnectFault()
        exc.msg = '[SSL: CERTIFICATE_VERIFY_FAILED]'
        exc2 = Exception('certificate verify failed')
        exc3 = vim.fault.VimFault()
        exc3.msg = 'VimFault'
        mock_sc = MagicMock(side_effect=[exc, exc2, exc3])

        with patch('salt.utils.vmware.SmartConnect', mock_sc):
            with self.assertRaises(excs.VMwareConnectionError) as excinfo:
                salt.utils.vmware._get_service_instance(
                    host='fake_host.fqdn',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='sspi',
                    principal='fake_principal',
                    domain='fake_domain')

                self.assertEqual(mock_sc.call_count, 3)
                self.assertIn('VimFault', excinfo.Exception.message)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.GetSi', MagicMock(return_value=None))
@patch('salt.utils.vmware._get_service_instance',
       MagicMock(return_value=MagicMock()))
class GetServiceInstanceTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_service_instance'''

    def test_default_params(self):
        mock_get_si = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            salt.utils.vmware.get_service_instance(
                host='fake_host'
            )
            mock_get_si.assert_called_once_with('fake_host', None, None,
                                                'https', 443, 'userpass', None,
                                                None)

    @patch('salt.utils.is_proxy', MagicMock(return_value=True))
    def test_no_cached_service_instance_same_host_on_proxy(self):
        # Service instance is uncached when using class default mock objs
        mock_get_si = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            salt.utils.vmware.get_service_instance(
                host='fake_host',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='fake_mechanism',
                principal='fake_principal',
                domain='fake_domain'
            )
            mock_get_si.assert_called_once_with('fake_host',
                                                'fake_username',
                                                'fake_password',
                                                'fake_protocol',
                                                1,
                                                'fake_mechanism',
                                                'fake_principal',
                                                'fake_domain')

    def test_cached_service_instance_different_host(self):
        mock_si = MagicMock()
        mock_si_stub = MagicMock()
        mock_disconnect = MagicMock()
        mock_get_si = MagicMock(return_value=mock_si)
        mock_getstub = MagicMock()
        with patch('salt.utils.vmware.GetSi', mock_get_si):
            with patch('salt.utils.vmware.GetStub', mock_getstub):
                with patch('salt.utils.vmware.Disconnect', mock_disconnect):
                    salt.utils.vmware.get_service_instance(
                        host='fake_host',
                        username='fake_username',
                        password='fake_password',
                        protocol='fake_protocol',
                        port=1,
                        mechanism='fake_mechanism',
                        principal='fake_principal',
                        domain='fake_domain'
                    )
            self.assertEqual(mock_get_si.call_count, 1)
            self.assertEqual(mock_getstub.call_count, 1)
            self.assertEqual(mock_disconnect.call_count, 1)

    def test_uncached_service_instance(self):
        # Service instance is uncached when using class default mock objs
        mock_get_si = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            salt.utils.vmware.get_service_instance(
                host='fake_host',
                username='fake_username',
                password='fake_password',
                protocol='fake_protocol',
                port=1,
                mechanism='fake_mechanism',
                principal='fake_principal',
                domain='fake_domain'
            )
            mock_get_si.assert_called_once_with('fake_host',
                                                'fake_username',
                                                'fake_password',
                                                'fake_protocol',
                                                1,
                                                'fake_mechanism',
                                                'fake_principal',
                                                'fake_domain')

    def test_unauthenticated_service_instance(self):
        mock_si_current_time = MagicMock(side_effect=vim.fault.NotAuthenticated)
        mock_si = MagicMock()
        mock_get_si = MagicMock(return_value=mock_si)
        mock_si.CurrentTime = mock_si_current_time
        mock_disconnect = MagicMock()
        with patch('salt.utils.vmware._get_service_instance', mock_get_si):
            with patch('salt.utils.vmware.Disconnect', mock_disconnect):
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain'
                )
                self.assertEqual(mock_si_current_time.call_count, 1)
                self.assertEqual(mock_disconnect.call_count, 1)
                self.assertEqual(mock_get_si.call_count, 2)

    def test_current_time_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vmware._get_service_instance',
                   MagicMock(return_value=MagicMock(
                       CurrentTime=MagicMock(side_effect=exc)))):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain')
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_current_time_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        with patch('salt.utils.vmware._get_service_instance',
                   MagicMock(return_value=MagicMock(
                       CurrentTime=MagicMock(side_effect=exc)))):
            with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
                salt.utils.vmware.get_service_instance(
                    host='fake_host',
                    username='fake_username',
                    password='fake_password',
                    protocol='fake_protocol',
                    port=1,
                    mechanism='fake_mechanism',
                    principal='fake_principal',
                    domain='fake_domain')
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class DisconnectTestCase(TestCase):
    '''Tests for salt.utils.vmware.disconnect'''

    def setUp(self):
        self.mock_si = MagicMock()

    def test_disconnect(self):
        mock_disconnect = MagicMock()
        with patch('salt.utils.vmware.Disconnect', mock_disconnect):
            salt.utils.vmware.disconnect(
                service_instance=self.mock_si)
            mock_disconnect.assert_called_once_with(self.mock_si)

    def test_disconnect_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        with patch('salt.utils.vmware.Disconnect', MagicMock(side_effect=exc)):
            with self.assertRaises(excs.VMwareApiError) as excinfo:
                salt.utils.vmware.disconnect(
                    service_instance=self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_disconnect_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        with patch('salt.utils.vmware.Disconnect', MagicMock(side_effect=exc)):
            with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
                salt.utils.vmware.disconnect(
                    service_instance=self.mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
class IsConnectionToAVCenterTestCase(TestCase):
    '''Tests for salt.utils.vmware.is_connection_to_a_vcenter'''

    def test_api_type_raise_vim_fault(self):
        exc = vim.fault.VimFault()
        exc.msg = 'VimFault msg'
        mock_si = MagicMock()
        type(mock_si.content.about).apiType = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'VimFault msg')

    def test_api_type_raise_runtime_fault(self):
        exc = vmodl.RuntimeFault()
        exc.msg = 'RuntimeFault msg'
        mock_si = MagicMock()
        type(mock_si.content.about).apiType = PropertyMock(side_effect=exc)
        with self.assertRaises(excs.VMwareRuntimeError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertEqual(excinfo.exception.strerror, 'RuntimeFault msg')

    def test_connected_to_a_vcenter(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'VirtualCenter'

        ret = salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertTrue(ret)

    def test_connected_to_a_host(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'HostAgent'

        ret = salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertFalse(ret)

    def test_connected_to_invalid_entity(self):
        mock_si = MagicMock()
        mock_si.content.about.apiType = 'UnsupportedType'

        with self.assertRaises(excs.VMwareApiError) as excinfo:
            salt.utils.vmware.is_connection_to_a_vcenter(mock_si)
        self.assertIn('Unexpected api type \'UnsupportedType\'',
                      excinfo.exception.strerror)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.vim.ServiceInstance', MagicMock())
class GetServiceInstanceFromManagedObjectTestCase(TestCase):
    '''Tests for salt.utils.vmware.get_managed_instance_from_managed_object'''

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_stub = PropertyMock()
        self.mock_mo_ref = MagicMock(_stub=self.mock_stub)

    def test_default_name_parameter(self):
        mock_trace = MagicMock()
        type(salt.utils.vmware.log).trace = mock_trace
        salt.utils.vmware.get_service_instance_from_managed_object(
            self.mock_mo_ref)
        mock_trace.assert_called_once_with('[<unnamed>] Retrieving service '
                                           'instance from managed object')

    def test_name_parameter_passed_in(self):
        mock_trace = MagicMock()
        type(salt.utils.vmware.log).trace = mock_trace
        salt.utils.vmware.get_service_instance_from_managed_object(
            self.mock_mo_ref, 'fake_mo_name')
        mock_trace.assert_called_once_with('[fake_mo_name] Retrieving service '
                                           'instance from managed object')

    def test_service_instance_instantiation(self):
        mock_service_instance_ini = MagicMock()
        with patch('salt.utils.vmware.vim.ServiceInstance',
                   mock_service_instance_ini):
            salt.utils.vmware.get_service_instance_from_managed_object(
                self.mock_mo_ref)
        mock_service_instance_ini.assert_called_once_with('ServiceInstance')

    def test_si_return_and_stub_assignment(self):
        with patch('salt.utils.vmware.vim.ServiceInstance',
                   MagicMock(return_value=self.mock_si)):
            ret = salt.utils.vmware.get_service_instance_from_managed_object(
                self.mock_mo_ref)
        self.assertEqual(ret, self.mock_si)
        self.assertEqual(ret._stub, self.mock_stub)
