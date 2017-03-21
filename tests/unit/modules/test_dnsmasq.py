# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.modules.dnsmasq as dnsmasq


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DnsmasqTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for the salt.modules.at module
    '''
    loader_module = dnsmasq

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

    @patch('salt.modules.dnsmasq.get_config', MagicMock(return_value={'conf-dir': 'A'}))
    def test_set_config_filter_pub_kwargs(self):
        '''
        Test that the kwargs returned from running the set_config function
        do not contain the __pub that may have been passed through in **kwargs.
        '''
        mock_domain = 'local'
        mock_address = '/some-test-address.local/8.8.4.4'
        with patch.dict(dnsmasq.__salt__, {'file.append': MagicMock()}):
            ret = dnsmasq.set_config(follow=False,
                                     domain=mock_domain,
                                     address=mock_address,
                                     __pub_pid=8184,
                                     __pub_jid=20161101194639387946,
                                     __pub_tgt='salt-call')
        self.assertEqual(ret, {'domain': mock_domain, 'address': mock_address})

    def test_get_config(self):
        '''
        test to dumps all options from the config file.
        '''
        mock = MagicMock(return_value={'conf-dir': 'A'})
        with patch.object(dnsmasq, 'get_config', mock):
            mock = MagicMock(return_value=['.', '~', 'bak', '#'])
            with patch.object(os, 'listdir', mock):
                self.assertDictEqual(dnsmasq.get_config(), {'conf-dir': 'A'})

    def test_parse_dnsmasq_no_file(self):
        '''
        Tests that a CommandExecutionError is when a filename that doesn't exist is
        passed in.
        '''
        self.assertRaises(CommandExecutionError, dnsmasq._parse_dnamasq, 'filename')

    @patch('os.path.isfile', MagicMock(return_value=True))
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
