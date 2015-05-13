# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Joe Julian <me@joejulian.name>`
'''

# Import Python libs
from __future__ import absolute_import
import shutil
import tempfile
import os

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import tls
import integration


# Globals
tls.__grains__ = {}
tls.__salt__ = {}
tls.__context__ = {}
tls.__opts__ = {}

_TLS_TEST_DATA = {
    'ca_cert': '''-----BEGIN CERTIFICATE-----
MIIEejCCA2KgAwIBAgIRANW6IUG5rMez0vPi3cSmS3QwDQYJKoZIhvcNAQELBQAw
eTELMAkGA1UEBhMCVVMxDTALBgNVBAgMBFV0YWgxFzAVBgNVBAcMDlNhbHQgTGFr
ZSBDaXR5MRIwEAYDVQQKDAlTYWx0U3RhY2sxEjAQBgNVBAMMCWxvY2FsaG9zdDEa
MBgGCSqGSIb3DQEJARYLeHl6QHBkcS5uZXQwHhcNMTUwNTA1MTYzOTIxWhcNMTYw
NTA0MTYzOTIxWjB5MQswCQYDVQQGEwJVUzENMAsGA1UECAwEVXRhaDEXMBUGA1UE
BwwOU2FsdCBMYWtlIENpdHkxEjAQBgNVBAoMCVNhbHRTdGFjazESMBAGA1UEAwwJ
bG9jYWxob3N0MRowGAYJKoZIhvcNAQkBFgt4eXpAcGRxLm5ldDCCASIwDQYJKoZI
hvcNAQEBBQADggEPADCCAQoCggEBAMNvHc8LwpI5/NiwRTWYG34WQ5vau8gkj+8p
5KehXDNmDcCY8QW9xNaCxY6Atg2Dwh5vEacubKRcnQL9SFKYHa4ddtnkISzSkdZN
ImY7ZVQteDIVNJmy7DrZ4RvWTr2ezXYLv8oNkqrKhynt5xIBXZWslWUav1pOp8z8
N+LeXaASVyajqB5TiN8HJR/up9MlSfy/zhtm6x6SIUsEZa+zK7m06/Glrr4WZFOV
LbOwxl36JpjywWTNcrXJd052U/377tUATXpepALBUUOIvWeGF7mrSTZkdhqRZRTe
Jr2+48zIuyMeB+JlY4UpR04pQNqstHimkyjxFfN/TKFqlhYqYjkCAwEAAaOB/DCB
+TASBgNVHRMBAf8ECDAGAQH/AgEAMA4GA1UdDwEB/wQEAwIBBjAdBgNVHQ4EFgQU
WBvk3qjnltkxKtEQxqYn5+KwYWkwgbMGA1UdIwSBqzCBqIAUWBvk3qjnltkxKtEQ
xqYn5+KwYWmhfaR7MHkxCzAJBgNVBAYTAlVTMQ0wCwYDVQQIDARVdGFoMRcwFQYD
VQQHDA5TYWx0IExha2UgQ2l0eTESMBAGA1UECgwJU2FsdFN0YWNrMRIwEAYDVQQD
DAlsb2NhbGhvc3QxGjAYBgkqhkiG9w0BCQEWC3h5ekBwZHEubmV0ghEA1bohQbms
x7PS8+LdxKZLdDANBgkqhkiG9w0BAQsFAAOCAQEALe312Oe8e+VjhnItcjQFuwcP
TaLf3+DTWaQLU1C8H78E75WE9UiRiVCyTpOLt/nONFkIKE275nCLPGCXn5JTZYVB
CxGFTRqnQ+8bdhZA6LYQPXieGikjTy+P2oiKOvPnYsATUXLbZ3ee+zEgBFGbbxNX
Argd3Vahg7Onu3ynsJz9a+hmwVqTX70Ykrrm+b/YtwKPfHeXTMxkX23jc4R7D+ED
VvROFJ27hFPLVaJrsq3EHb8ZkQHmRCzK2sMIPyJb2e0BOKDEZEphNxiIjerDnH7n
xDSMW0jK9FEv/W/sSBwoEolh3Q2e0gfd2vo7bEGvNF4eTqFsoAfeiAjWk65q0Q==
-----END CERTIFICATE-----''',
    'ca_cert_key': '''-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDDbx3PC8KSOfzY
sEU1mBt+FkOb2rvIJI/vKeSnoVwzZg3AmPEFvcTWgsWOgLYNg8IebxGnLmykXJ0C
/UhSmB2uHXbZ5CEs0pHWTSJmO2VULXgyFTSZsuw62eEb1k69ns12C7/KDZKqyocp
7ecSAV2VrJVlGr9aTqfM/Dfi3l2gElcmo6geU4jfByUf7qfTJUn8v84bZusekiFL
BGWvsyu5tOvxpa6+FmRTlS2zsMZd+iaY8sFkzXK1yXdOdlP9++7VAE16XqQCwVFD
iL1nhhe5q0k2ZHYakWUU3ia9vuPMyLsjHgfiZWOFKUdOKUDarLR4ppMo8RXzf0yh
apYWKmI5AgMBAAECggEBAIRqIRRLr4VL7NkUdZAeg2Imy6Apz9mHjE5LYDWDyui4
WNEJzyRIs7lz2U74PmFhyIC+WIOhnNKwPWHtIrdzgYibRg/T1fZ8pXtBv/DshXdH
Z4zneUA6TnyBa1hlF+y6UBOPWl8YWyuFFZd/LXSxoCrtSDu8p7IUYPUuXt9EMsNk
+rQhBZH7iiOx2M7ckLb/gG4tElqh/QQ0Qhuy1e80oMfO9w1XxIThETx0LxQ7Uad5
vk5BQoEI+n/W1tPhXwQ/hndn3ub3pgfpKXIKi7AdySsdxTda4pJLyEwAm9MHrMNm
XvlBdQ+/vq4NSRk2oVVFzJ1yX7bfmrw+6ZqY36oOrUECgYEA4KvnSgeUyG4ouwA9
zTehvFhEWfFyj/y8Tl2OcaIeCvHahN3n6n++Rx25JYrQDhguMGgMHJ0dcZr0Wvvc
EPOAxjam96p2HJMYdpYmrwpguHDu4Jk+fOqgc8Ms541P3+sMej1UQxRaQ6c/g1EM
Pl0g2GdDN4bw60nbEwOXp0qFI1UCgYEA3q+GJDA+gkXcMqKN06VEdjPvm+BpOygx
VvO0cG6njcmVjJKPePIYbjcBHduQRbCGxLmntLOyVg6Ign1+r/LaG7AADYXMdURD
cn4J9ANKuT1lZcs/JRatA1qigwlk8E7vIqq0E/1EiEbRWVE34lgN3dkUOqAXLBfi
9p2aJMOtC1UCgYAKnDOtDFSbbpBf3HAOu/zYXzbDJKLrZ90gukxa03Qlwiw2sCAe
s++xfhbbTgXrVHsB8Df6NfVJAy9dCJ3o8wb21WfnNFalnNC/8PFcvNm6fCLb2oDX
92Ciduos+UB3a6tILpNHI7Prk/9s3Sv92foOHjpPagEAq5k7+aR00xEcjQKBgEhn
r+kCWsDG8ELygcToPqtkVatMO0sF1Y0dLnVENWyvt9V+LfI4XWMwtUc9Bdry+87p
QrNJnlnG3fH31gJlpy9Leajr8T/L01ZdzuStUVWLtfV0MXLgvZ6SkLakjlJoh+6w
rF63gdoBlL5C3zXURaX1mFM7jG1E0wI22lDL4u8FAoGAaeghxaW4V0keS0KpdPvL
kmEhQ5VDAG92fmzQa0wkBoTbsS4kitHj5QTfNJgdCDJbZ7srkMbQR7oVGeZKIDBk
L7lyhyrtHaR/r/fdUNEJAVsQt3Shaa5c5srLh6vzGcBsV7/nQqrEP+GadvGSbHNT
bymYbi0l2pWqQLA2sPoRHNw=
-----END PRIVATE KEY-----''',
    'ca_signed_cert': '''
    ''',
    'ca_signed_key': '''
    ''',
    'create_ca': {
        'bits': 2048,
        'CN': 'localhost',
        'C': 'US',
        'ST': 'Utah',
        'L': 'Salt Lake City',
        'O': 'SaltStack',
        'OU': 'Test Unit',
        'emailAddress': 'xyz@pdq.net',
        'digest': 'sha256',
        'replace': False
        }
    }

@skipIf(NO_MOCK, NO_MOCK_REASON)
class TLSAddTestCase(TestCase):
    '''
    Test cases for salt.modules.tls
    '''
    def test_cert_base_path(self):
        '''
        Test for retrieving cert base path
        '''
        ca_path = '/etc/tls'
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertEqual(tls.cert_base_path(), ca_path)

    def test_set_ca_cert_path(self):
        '''
        Test for setting the cert base path
        '''
        ca_path = '/tmp/ca_cert_test_path'
        mock = MagicMock(return_value='/etc/tls')
        ret = {'ca.contextual_cert_base_path': '/tmp/ca_cert_test_path'}
        with patch.dict(tls.__salt__, {'config.option': mock}):
            tls.set_ca_path(ca_path)
            self.assertDictEqual(tls.__opts__, ret)

    @patch('os.path.exists', MagicMock(return_value=False))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_ca_exists(self):
        '''
        Test to see if ca does not exist
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertFalse(tls.ca_exists(ca_name))

    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_ca_exists_true(self):
        '''
        Test to see if ca exists
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertTrue(tls.ca_exists(ca_name))

    @patch('os.path.exists', MagicMock(return_value=False))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_get_ca_fail(self):
        '''
        Test get_ca failure
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertRaises(ValueError, tls.get_ca, ca_name)

    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    @patch('salt.utils.fopen', mock_open(read_data=_TLS_TEST_DATA['ca_cert']))
    def test_get_ca_text(self):
        '''
        Test get_ca text
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertEqual(tls.get_ca(ca_name, as_text=True),
                             _TLS_TEST_DATA['ca_cert'])

    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_get_ca(self):
        '''
        Test get_ca
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        certp = '{0}/{1}/{2}_ca_cert.crt'.format(
            ca_path,
            ca_name,
            ca_name)
        mock = MagicMock(return_value=ca_path)
        with patch.dict(tls.__salt__, {'config.option': mock}):
            self.assertEqual(tls.get_ca(ca_name), certp)

    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    @patch('salt.utils.fopen', mock_open(read_data=_TLS_TEST_DATA['ca_cert']))
    def test_cert_info(self):
        '''
        Test cert info
        '''
        ca_path = '/tmp/test_tls'
        ca_name = 'test_ca'
        certp = '{0}/{1}/{2}_ca_cert.crt'.format(
            ca_path,
            ca_name,
            ca_name)
        ret = {
            'not_after': 1462405161.0,
            'signature_algorithm': 'sha256WithRSAEncryption',
            'extensions': ['subjectKeyIdentifier', 'keyUsage',
                           'authorityKeyIdentifier', 'basicConstraints'],
            'fingerprint': ('96:72:B3:0A:1D:34:37:05:75:57:44:7E:08:81:A7:09:'
                            '0C:E1:8F:5F:4D:0C:49:CE:5B:D2:6B:45:D3:4D:FF:31'),
            'serial_number': 284092004844685647925744086791559203700L,
            'subject': {
                'C': 'US',
                'CN': 'localhost',
                'L': 'Salt Lake City',
                'O': 'SaltStack',
                'ST': 'Utah',
                'emailAddress':
                'xyz@pdq.net'},
            'not_before': 1430869161.0,
            'issuer': {
                'C': 'US',
                'CN': 'localhost',
                'L': 'Salt Lake City',
                'O': 'SaltStack',
                'ST': 'Utah',
                'emailAddress': 'xyz@pdq.net'}
            }
        def extensions_to_list(data):
            '''
            Convert dict of extensions to a list of extension names
            '''
            if 'extensions' in data.keys():
                data['extensions'] = data['extensions'].keys()
            return data
        self.assertEqual(extensions_to_list(tls.cert_info(certp)), ret)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_create_ca(self):
        '''
        Test creating CA cert
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/{2}_ca_cert.crt'.format(
                ca_path,
                ca_name,
                ca_name)
            certk = '{0}/{1}/{2}_ca_cert.key'.format(
                ca_path,
                ca_name,
                ca_name)
            ret = 'Created Private Key: "{0}." Created CA "{1}": "{2}."'.format(
                certk, ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    self.assertEqual(
                        tls.create_ca(
                            ca_name,
                            days=365,
                            fixmode=False,
                            **_TLS_TEST_DATA['create_ca']),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_recreate_ca(self):
        '''
        Test creating CA cert when one already exists
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/{2}_ca_cert.crt'.format(
                ca_path,
                ca_name,
                ca_name)
            certk = '{0}/{1}/{2}_ca_cert.key'.format(
                ca_path,
                ca_name,
                ca_name)
            ret = 'Created Private Key: "{0}." Created CA "{1}": "{2}."'.format(
                certk, ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    with patch.dict(_TLS_TEST_DATA['create_ca'],
                                    {'replace': True}):
                        tls.create_ca(ca_name)
                        self.assertEqual(
                            tls.create_ca(
                                ca_name,
                                days=365,
                                fixmode=False,
                                **_TLS_TEST_DATA['create_ca']),
                            ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_create_csr(self):
        '''
        Test creating certificate signing request
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.csr'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            certk = '{0}/{1}/certs/{2}.key'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = ('Created Private Key: "{0}." '
                   'Created CSR for "{1}": "{2}."').format(
                       certk, ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    tls.create_ca(ca_name)
                    self.assertEqual(
                        tls.create_csr(
                            ca_name,
                            **_TLS_TEST_DATA['create_ca']),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_recreate_csr(self):
        '''
        Test creating certificate signing request when one already exists
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.csr'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            certk = '{0}/{1}/certs/{2}.key'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = ('Created Private Key: "{0}." '
                   'Created CSR for "{1}": "{2}."').format(
                       certk, ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    with patch.dict(_TLS_TEST_DATA['create_ca'],
                                    {'replace': True}):
                        tls.create_ca(ca_name)
                        tls.create_csr(ca_name)
                        self.assertEqual(
                            tls.create_csr(
                                ca_name,
                                **_TLS_TEST_DATA['create_ca']),
                            ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_create_self_signed_cert(self):
        '''
        Test creating self signed certificate
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            tls_dir = 'test_tls'
            certp = '{0}/{1}/certs/{2}.crt'.format(
                ca_path,
                tls_dir,
                _TLS_TEST_DATA['create_ca']['CN'])
            certk = '{0}/{1}/certs/{2}.key'.format(
                ca_path,
                tls_dir,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = ('Created Private Key: "{0}." '
                   'Created Certificate: "{1}."').format(
                       certk, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    self.assertEqual(
                        tls.create_self_signed_cert(
                            tls_dir=tls_dir,
                            days=365,
                            **_TLS_TEST_DATA['create_ca']),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_recreate_self_signed_cert(self):
        '''
        Test creating self signed certificate when one already exists
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            tls_dir = 'test_tls'
            certp = '{0}/{1}/certs/{2}.crt'.format(
                ca_path,
                tls_dir,
                _TLS_TEST_DATA['create_ca']['CN'])
            certk = '{0}/{1}/certs/{2}.key'.format(
                ca_path,
                tls_dir,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = ('Created Private Key: "{0}." '
                   'Created Certificate: "{1}."').format(
                       certk, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    self.assertEqual(
                        tls.create_self_signed_cert(
                            tls_dir=tls_dir,
                            days=365,
                            **_TLS_TEST_DATA['create_ca']),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_create_ca_signed_cert(self):
        '''
        Test signing certificate from request
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.crt'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = 'Created Certificate for "{0}": "{1}"'.format(
                ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    tls.create_ca(ca_name)
                    tls.create_csr(ca_name, **_TLS_TEST_DATA['create_ca'])
                    self.assertEqual(
                        tls.create_ca_signed_cert(
                            ca_name,
                            **_TLS_TEST_DATA['create_ca']),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_recreate_ca_signed_cert(self):
        '''
        Test signing certificate from request when certificate exists
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.crt'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = 'Created Certificate for "{0}": "{1}"'.format(
                ca_name, certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    with patch.dict(_TLS_TEST_DATA['create_ca'],
                                    {'replace': True}):
                        tls.create_ca(ca_name)
                        tls.create_csr(ca_name)
                        tls.create_ca_signed_cert(ca_name,
                                                  **_TLS_TEST_DATA['create_ca'])
                        self.assertEqual(
                            tls.create_ca_signed_cert(
                                ca_name,
                                **_TLS_TEST_DATA['create_ca']),
                            ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_create_pkcs12(self):
        '''
        Test creating pkcs12
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.p12'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = 'Created PKCS#12 Certificate for "{0}": "{1}"'.format(
                _TLS_TEST_DATA['create_ca']['CN'], certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    tls.create_ca(ca_name)
                    tls.create_csr(ca_name, **_TLS_TEST_DATA['create_ca'])
                    tls.create_ca_signed_cert(ca_name,
                                              **_TLS_TEST_DATA['create_ca'])
                    self.assertEqual(
                        tls.create_pkcs12(ca_name,
                                          _TLS_TEST_DATA['create_ca']['CN'],
                                          'password'),
                        ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

    @patch('salt.modules.tls.maybe_fix_ssl_version',
           MagicMock(return_value=True))
    def test_recreate_pkcs12(self):
        '''
        Test creating pkcs12 when it already exists
        '''
        ca_path = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            ca_name = 'test_ca'
            certp = '{0}/{1}/certs/{2}.p12'.format(
                ca_path,
                ca_name,
                _TLS_TEST_DATA['create_ca']['CN'])
            ret = 'Created PKCS#12 Certificate for "{0}": "{1}"'.format(
                _TLS_TEST_DATA['create_ca']['CN'], certp)
            mock = MagicMock(return_value=ca_path)
            with patch.dict(tls.__salt__, {'config.option': mock}):
                with patch.dict(tls.__opts__, {'hash_type': 'sha256',
                                               'cachedir': ca_path}):
                    with patch.dict(_TLS_TEST_DATA['create_ca'],
                                    {'replace': True}):
                        tls.create_ca(ca_name)
                        tls.create_csr(ca_name)
                        tls.create_ca_signed_cert(ca_name,
                                                  **_TLS_TEST_DATA['create_ca'])
                        tls.create_pkcs12(ca_name,
                                          _TLS_TEST_DATA['create_ca']['CN'],
                                          'password')
                        self.assertEqual(
                            tls.create_pkcs12(ca_name,
                                              _TLS_TEST_DATA['create_ca']['CN'],
                                              'password',
                                              replace=True),
                            ret)
        finally:
            if os.path.isdir(ca_path):
                shutil.rmtree(ca_path)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TLSAddTestCase, needs_daemon=False)
