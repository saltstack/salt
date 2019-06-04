# -*- coding: utf-8 -*-
'''
:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
'''

# Import future libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import textwrap
import datetime

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import Salt Module
import salt.modules.acme as acme
import salt.utils.dictupdate
from salt.exceptions import SaltInvocationError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AcmeTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.acme
    '''

    def setup_loader_modules(self):
        return {acme: {}}

    def test_certs(self):
        '''
        Test listing certs
        '''
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'file.readdir': MagicMock(return_value=['.', '..', 'README', 'test_expired', 'test_valid'])
                }), \
                patch('os.path.isdir', side_effect=[False, True, True]):
            self.assertEqual(acme.certs(), ['test_expired', 'test_valid'])

    def test_has(self):
        '''
        Test checking if certificate (does not) exist.
        '''
        with patch.dict(acme.__salt__, {'file.file_exists': MagicMock(return_value=True)}):  # pylint: disable=no-member
            self.assertTrue(acme.has('test_expired'))
        with patch.dict(acme.__salt__, {'file.file_exists': MagicMock(return_value=False)}):  # pylint: disable=no-member
            self.assertFalse(acme.has('test_invalid'))

    def test_needs_renewal(self):
        '''
        Test if expired certs do indeed need renewal.
        '''
        expired = datetime.date.today() - datetime.timedelta(days=3) - datetime.date(1970, 1, 1)
        valid = datetime.date.today() + datetime.timedelta(days=3) - datetime.date(1970, 1, 1)
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'tls.cert_info': MagicMock(return_value={'not_after': expired.total_seconds()})
                }):
            self.assertTrue(acme.needs_renewal('test_expired'))
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'tls.cert_info': MagicMock(return_value={'not_after': valid.total_seconds()})
                }):
            self.assertFalse(acme.needs_renewal('test_valid'))
            # Test with integer window parameter
            self.assertTrue(acme.needs_renewal('test_valid', window=5))
            # Test with string-like window parameter
            self.assertTrue(acme.needs_renewal('test_valid', window='5'))
            # Test with invalid window parameter
            self.assertRaises(SaltInvocationError, acme.needs_renewal, 'test_valid', window='foo')

    def test_expires(self):
        '''
        Test if expires function functions properly.
        '''
        test_value = datetime.datetime.today() - datetime.timedelta(days=3)
        test_stamp = test_value - datetime.datetime(1970, 1, 1)
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'tls.cert_info': MagicMock(return_value={'not_after': test_stamp.total_seconds()})
                }):
            self.assertEqual(
                acme.expires('test_expired'),
                datetime.datetime.fromtimestamp(test_stamp.total_seconds()).isoformat()
            )

    def test_info(self):
        '''
        Test certificate information retrieval.
        '''
        certinfo_result = {
            "not_after": 1559471377,
            "signature_algorithm": "sha256WithRSAEncryption",
            "extensions": {},
            "fingerprint": ("FB:A4:5F:71:D6:5D:6C:B6:1D:2C:FD:91:09:2C:1C:52:"
                            "3C:EC:B6:4D:1A:95:65:37:04:D0:E2:5E:C7:64:0C:9C"),
            "serial_number": 6461481982668892235,
            "issuer": {},
            "not_before": 1559557777,
            "subject": {},
        }
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'tls.cert_info': MagicMock(return_value=certinfo_result),
                    'file.file_exists': MagicMock(return_value=True)
                }):
            self.assertEqual(acme.info('test'), certinfo_result)
        with patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'cmd.run': MagicMock(return_value='foo'),
                    'file.file_exists': MagicMock(return_value=True)
                }):
            self.assertEqual(acme.info('test'), 'foo')

    def test_cert(self):
        '''
        Test certificate retrieval/renewal
        '''
        valid_timestamp = (datetime.datetime.now() + datetime.timedelta(days=30) -
                           datetime.datetime(1970, 1, 1, 0, 0, 0, 0)).total_seconds()
        expired_timestamp = (datetime.datetime.now() - datetime.timedelta(days=3) -
                             datetime.datetime(1970, 1, 1, 0, 0, 0, 0)).total_seconds()
        cmd_new_cert = {
            'stdout': textwrap.dedent('''IMPORTANT NOTES:
                 - Congratulations! Your certificate and chain have been saved at:
                   /etc/letsencrypt/live/test/fullchain.pem
                   Your key file has been saved at:
                   /etc/letsencrypt/live/test/privkey.pem
                   Your cert will expire on 2019-08-07. To obtain a new or tweaked
                   version of this certificate in the future, simply run certbot
                   again. To non-interactively renew *all* of your certificates, run
                   "certbot renew"
                 - If you like Certbot, please consider supporting our work by:
                
                   Donating to ISRG / Let's Encrypt:   https://letsencrypt.org/donate
                   Donating to EFF:                    https://eff.org/donate-le
                '''),
            'stderr': textwrap.dedent('''Saving debug log to /var/log/letsencrypt/letsencrypt.log
                Plugins selected: Authenticator standalone, Installer None
                Starting new HTTPS connection (1): acme-v02.api.letsencrypt.org
                Obtaining a new certificate
                Resetting dropped connection: acme-v02.api.letsencrypt.org
                '''),
            'retcode': 0,
        }
        result_new_cert = {
            "comment": "Certificate test obtained",
            "not_after": datetime.datetime.fromtimestamp(valid_timestamp).isoformat(),
            "changes": {
                "mode": "0640"
            },
            "result": True
        }

        cmd_no_renew = {
            'stdout': textwrap.dedent('''
                - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                Certificate not yet due for renewal; no action taken.
                - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                '''),
            'stderr': textwrap.dedent('''Saving debug log to /var/log/letsencrypt/letsencrypt.log
                Plugins selected: Authenticator standalone, Installer None
                Starting new HTTPS connection (1): acme-v02.api.letsencrypt.org
                Cert not yet due for renewal
                Keeping the existing certificate
                '''),
            'retcode': 0
        }
        result_no_renew = {
            "comment": "Certificate /etc/letsencrypt/live/test/cert.pem unchanged",
            "not_after": datetime.datetime.fromtimestamp(valid_timestamp).isoformat(),
            "changes": {},
            "result": True
        }
        result_renew = {
            "comment": "Certificate test renewed",
            "not_after": datetime.datetime.fromtimestamp(expired_timestamp).isoformat(),
            "changes": {},
            "result": True
        }

        # Test fetching new certificate
        with patch('salt.modules.acme.LEA', 'certbot'), \
                patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'cmd.run_all': MagicMock(return_value=cmd_new_cert),
                    'file.file_exists': MagicMock(return_value=False),
                    'tls.cert_info': MagicMock(return_value={'not_after': valid_timestamp}),
                    'file.check_perms': MagicMock(
                        side_effect=lambda a, x, b, c, d, follow_symlinks: (
                            salt.utils.dictupdate.set_dict_key_value(x, 'changes:mode', '0640'),
                            None
                        )
                    )
                }):
            self.assertEqual(acme.cert('test'), result_new_cert)
        # Test not renewing a valid certificate
        with patch('salt.modules.acme.LEA', 'certbot'), \
                patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'cmd.run_all': MagicMock(return_value=cmd_no_renew),
                    'file.file_exists': MagicMock(return_value=True),
                    'tls.cert_info': MagicMock(return_value={'not_after': valid_timestamp}),
                    'file.check_perms': MagicMock(
                        side_effect=lambda a, x, b, c, d, follow_symlinks: (
                            salt.utils.dictupdate.set_dict_key_value(x, 'result', True),
                            None
                        )
                    )
                }):
            self.assertEqual(acme.cert('test'), result_no_renew)
        # Test renewing an expired certificate
        with patch('salt.modules.acme.LEA', 'certbot'), \
                patch.dict(acme.__salt__, {  # pylint: disable=no-member
                    'cmd.run_all': MagicMock(return_value=cmd_new_cert),
                    'file.file_exists': MagicMock(return_value=True),
                    'tls.cert_info': MagicMock(return_value={'not_after': expired_timestamp}),
                    'file.check_perms': MagicMock(
                        side_effect=lambda a, x, b, c, d, follow_symlinks: (
                            salt.utils.dictupdate.set_dict_key_value(x, 'result', True),
                            None
                        )
                    )
                }):
            self.assertEqual(acme.cert('test'), result_renew)
