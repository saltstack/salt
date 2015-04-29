# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

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
from salt.modules import dnsmasq

# Import python libs
import os

# Globals
dnsmasq.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DnsmasqTestCase(TestCase):
    '''
    TestCase for the salt.modules.at module
    '''
    def test_version(self):
        '''
        test to show installed version of dnsmasq.
        '''
        mock = MagicMock(return_value='A B C')
        with patch.dict(dnsmasq.__salt__, {'cmd.run': mock}):
            self.assertEqual(dnsmasq.version(), "C")

    def test_fullversion(self):
        '''
        Test to Show installed version of dnsmasq and compile options.
        '''
        mock = MagicMock(return_value='A B C\nD E F G H I')
        with patch.dict(dnsmasq.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(dnsmasq.fullversion(),
                                 {'version': 'C',
                                  'compile options': ['G', 'H', 'I']})

    def test_set_config(self):
        '''
        test to show installed version of dnsmasq.
        '''
        mock = MagicMock(return_value={'conf-dir': 'A'})
        with patch.object(dnsmasq, 'get_config', mock):
            mock = MagicMock(return_value=['.', '~', 'bak', '#'])
            with patch.object(os, 'listdir', mock):
                self.assertDictEqual(dnsmasq.set_config(), {})

    def test_get_config(self):
        '''
        test to dumps all options from the config file.
        '''
        mock = MagicMock(return_value={'conf-dir': 'A'})
        with patch.object(dnsmasq, 'get_config', mock):
            mock = MagicMock(return_value=['.', '~', 'bak', '#'])
            with patch.object(os, 'listdir', mock):
                self.assertDictEqual(dnsmasq.get_config(), {'conf-dir': 'A'})

    def test_parse_dnamasq(self):
        '''
        test for generic function for parsing dnsmasq files including includes.
        '''
        text_file_data = '\n'.join(["line here", "second line", "A=B", "#"])
        with patch('salt.utils.fopen',
                   mock_open(read_data=text_file_data),
                   create=True) as m:
            m.return_value.__iter__.return_value = text_file_data.splitlines()
            self.assertDictEqual(dnsmasq._parse_dnamasq('filename'),
                                 {'A': 'B',
                                  'unparsed': ['line here',
                                               'second line']})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DnsmasqTestCase, needs_daemon=False)
