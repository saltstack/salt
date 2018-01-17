# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

from __future__ import absolute_import, print_function, unicode_literals
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt libs
import salt.exceptions
import salt.state
from salt.utils import ssdp

try:
    import pytest
except ImportError as err:
    pytest = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSDPTestCase(TestCase):
    '''
    TestCase for SSDP-related parts.
    '''

    @patch('salt.utils.ssdp._json', None)
    @patch('salt.utils.ssdp.asyncio', None)
    def test_base_avail(self):
        '''
        Test SSDP base class availability method.
        :return:
        '''
        base = ssdp.SSDPBase()
        assert not base._is_available()

        with patch('salt.utils.ssdp._json', True):
            assert not base._is_available()

        with patch('salt.utils.ssdp.asyncio', True):
            assert not base._is_available()

        with patch('salt.utils.ssdp._json', True), patch('salt.utils.ssdp.asyncio', True):
            assert base._is_available()

    def test_base_protocol_settings(self):
        '''
        Tests default constants data.
        :return:
        '''
        base = ssdp.SSDPBase()
        v_keys = ['signature', 'answer', 'port', 'listen_ip', 'timeout']
        v_vals = ['__salt_master_service', {}, 4520, '0.0.0.0', 3]
        for key in v_keys:
            assert key in base.DEFAULTS

        for key in base.DEFAULTS.keys():
            assert key in v_keys

        for key, value in zip(v_keys, v_vals):
            assert base.DEFAULTS[key] == value

    def test_base_self_ip(self):
        '''
        Test getting self IP method.

        :return:
        '''
        def boom():
            '''
            Side effect
            :return:
            '''
            raise Exception('some network error')

        base = ssdp.SSDPBase()
        expected_ip = '192.168.1.10'
        expected_host = 'oxygen'
        sck = MagicMock()
        sck.getsockname = MagicMock(return_value=(expected_ip, 123456))

        sock_mock = MagicMock()
        sock_mock.socket = MagicMock(return_value=sck)
        sock_mock.gethostbyname = MagicMock(return_value=expected_host)

        with patch('salt.utils.ssdp.socket', sock_mock):
            assert base.get_self_ip() == expected_ip

        sck.getsockname.side_effect = boom
        with patch('salt.utils.ssdp.socket', sock_mock):
            assert base.get_self_ip() == expected_host
