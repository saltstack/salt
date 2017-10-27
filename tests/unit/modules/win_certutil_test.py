# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import win_certutil as certutil

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

certutil.__salt__ = {}


class CertUtilTestCase(TestCase):

    def test_get_serial(self):
        '''
            Test getting the serial number from a certificate
        '''
        expected = '180720d39cd2db3244ba037417241e90'
        mock = MagicMock(return_value=(
            'CertInfo\r\n'
            'Cert Serial Number: 180720d39cd2db3244ba037417241e90\r\n'
            '\r\n'
            'OtherStuff'))
        with patch.dict(certutil.__salt__, {'cmd.run': mock}):
            out = certutil.get_cert_serial('/path/to/cert.cer')
            mock.assert_called_once_with(
                'certutil.exe -silent -verify /path/to/cert.cer')
            self.assertEqual(expected, out)

    def test_get_serials(self):
        '''
            Test getting all the serial numbers from a store
        '''
        expected = ['180720d39cd2db3244ba037417241e90',
                    '1768ac4e5b72bf1d0df0df118b34b959']
        mock = MagicMock(return_value=(
            'CertInfo\r\n'
            '================ Certificate 0 ================\r\n'
            'Serial Number: 180720d39cd2db3244ba037417241e90\r\n'
            'OtherStuff\r\n'
            '\r\n'
            '================ Certificate 1 ================\r\n'
            'Serial Number: 1768ac4e5b72bf1d0df0df118b34b959\r\n'
            'OtherStuff'))
        with patch.dict(certutil.__salt__, {'cmd.run': mock}):
            out = certutil.get_stored_cert_serials('TrustedPublisher')
            mock.assert_called_once_with(
                'certutil.exe -store TrustedPublisher')
            self.assertEqual(expected, out)

    def test_add_store(self):
        '''
            Test adding a certificate to a specific store
        '''
        cmd_mock = MagicMock(return_value=(
            'CertInfo\r\n'
            '================ Certificate 0 ================\r\n'
            'Serial Number: 180720d39cd2db3244ba037417241e90\r\n'
            'OtherStuff'))
        cache_mock = MagicMock(return_value='/tmp/cert.cer')
        with patch.dict(certutil.__salt__, {'cmd.run': cmd_mock,
                                            'cp.cache_file': cache_mock}):
            certutil.add_store('salt://path/to/file', 'TrustedPublisher')
            cmd_mock.assert_called_once_with(
                'certutil.exe -addstore TrustedPublisher /tmp/cert.cer')
            cache_mock.assert_called_once_with('salt://path/to/file', 'base')

    @patch('salt.modules.win_certutil.get_cert_serial')
    def test_del_store(self, cert_serial_mock):
        '''
            Test removing a certificate to a specific store
        '''
        cmd_mock = MagicMock(return_value=(
            'CertInfo\r\n'
            '================ Certificate 0 ================\r\n'
            'Serial Number: 180720d39cd2db3244ba037417241e90\r\n'
            'OtherStuff'))
        cache_mock = MagicMock(return_value='/tmp/cert.cer')
        cert_serial_mock.return_value = 'ABCDEF'
        with patch.dict(certutil.__salt__, {'cmd.run': cmd_mock,
                                            'cp.cache_file': cache_mock}):
            certutil.del_store('salt://path/to/file', 'TrustedPublisher')
            cmd_mock.assert_called_once_with(
                'certutil.exe -delstore TrustedPublisher ABCDEF')
            cache_mock.assert_called_once_with('salt://path/to/file', 'base')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CertUtilTestCase, needs_daemon=False)
