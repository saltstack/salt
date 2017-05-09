# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.win_certutil as certutil

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)


class CertUtilTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {certutil: {}}

    def test_get_serial(self):
        '''
            Test getting the serial number from a certificate
        '''
        expected = 'XYZABC'
        mock = MagicMock(return_value='CertInfo\r\nSerial: XYZABC\r\nOtherStuff')
        with patch.dict(certutil.__salt__, {'cmd.run': mock}):
            out = certutil.get_cert_serial('/path/to/cert.cer')
            mock.assert_called_once_with('certutil.exe -verify /path/to/cert.cer')
            self.assertEqual(expected, out)

    def test_get_serials(self):
        '''
            Test getting the all the serial numbers from a store
        '''
        expected = ['XYZABC', '123456']
        mock = MagicMock(return_value='CertInfo\r\nSerial Number: XYZABC\r\nSerial Number: 123456\r\n')
        with patch.dict(certutil.__salt__, {'cmd.run': mock}):
            out = certutil.get_stored_cert_serials('TrustedPublisher')
            mock.assert_called_once_with('certutil.exe -store TrustedPublisher')
            self.assertEqual(expected, out)

    def test_add_store(self):
        '''
            Test adding a certificate to a specific store
        '''
        cmd_mock = MagicMock(return_value='CertInfo\r\nSerial: XYZABC\r\nOtherStuff')
        cache_mock = MagicMock(return_value='/tmp/cert.cer')
        with patch.dict(certutil.__salt__, {'cmd.run': cmd_mock,
                                            'cp.cache_file': cache_mock}):
            certutil.add_store('salt://path/to/file', 'TrustedPublisher')
            cmd_mock.assert_called_once_with('certutil.exe -addstore TrustedPublisher /tmp/cert.cer')
            cache_mock.assert_called_once_with('salt://path/to/file', 'base')

    def test_del_store(self):
        '''
            Test removing a certificate to a specific store
        '''
        with patch('salt.modules.win_certutil.get_cert_serial') as cert_serial_mock:
            cmd_mock = MagicMock(return_value='CertInfo\r\nSerial: XYZABC\r\nOtherStuff')
            cache_mock = MagicMock(return_value='/tmp/cert.cer')
            cert_serial_mock.return_value = "ABCDEF"
            with patch.dict(certutil.__salt__, {'cmd.run': cmd_mock,
                                                'cp.cache_file': cache_mock}):
                certutil.del_store('salt://path/to/file', 'TrustedPublisher')
                cmd_mock.assert_called_once_with('certutil.exe -delstore TrustedPublisher ABCDEF')
                cache_mock.assert_called_once_with('salt://path/to/file', 'base')
