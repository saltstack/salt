# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import SaltInvocationError
from salt.modules import logrotate

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Globals
logrotate.__salt__ = {}

PARSE_CONF = {
    'include files': {
        'rsyslog': ['/var/log/syslog']
    },
    'rotate': 1,
    '/var/log/wtmp': {
        'rotate': 1
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogrotateTestCase(TestCase):
    '''
    Test cases for salt.modules.logrotate
    '''
    # 'show_conf' function tests: 1

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=True))
    def test_show_conf(self):
        '''
        Test if it show parsed configuration
        '''
        self.assertTrue(logrotate.show_conf())

    # 'set_' function tests: 4

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=PARSE_CONF))
    def test_set(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        with patch.dict(logrotate.__salt__,
                        {'file.replace': MagicMock(return_value=True)}):
            self.assertTrue(logrotate.set_('rotate', '2'))

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=PARSE_CONF))
    def test_set_failed(self):
        '''
        Test if it fails to set a new value for a specific configuration line
        '''
        kwargs = {'key': '/var/log/wtmp',
                  'value': 2}
        self.assertRaises(SaltInvocationError, logrotate.set_, **kwargs)

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=PARSE_CONF))
    def test_set_setting(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        with patch.dict(logrotate.__salt__,
                        {'file.replace': MagicMock(return_value=True)}):
            self.assertTrue(logrotate.set_('/var/log/wtmp', 'rotate', '2'))

    @patch('salt.modules.logrotate._parse_conf',
           MagicMock(return_value=PARSE_CONF))
    def test_set_setting_failed(self):
        '''
        Test if it fails to set a new value for a specific configuration line
        '''
        kwargs = {'key': 'rotate',
                  'value': '/var/log/wtmp',
                  'setting': '2'}
        self.assertRaises(SaltInvocationError, logrotate.set_, **kwargs)
