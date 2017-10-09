# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import SaltInvocationError
import salt.modules.logrotate as logrotate

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

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
class LogrotateTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.logrotate
    '''
    def setup_loader_modules(self):
        return {logrotate: {}}

    # 'show_conf' function tests: 1

    def test_show_conf(self):
        '''
        Test if it show parsed configuration
        '''
        with patch('salt.modules.logrotate._parse_conf',
                   MagicMock(return_value=True)):
            self.assertTrue(logrotate.show_conf())

    # 'set_' function tests: 4

    def test_set(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        with patch('salt.modules.logrotate._parse_conf',
                   MagicMock(return_value=PARSE_CONF)), \
                patch.dict(logrotate.__salt__,
                           {'file.replace': MagicMock(return_value=True)}):
            self.assertTrue(logrotate.set_('rotate', '2'))

    def test_set_failed(self):
        '''
        Test if it fails to set a new value for a specific configuration line
        '''
        with patch('salt.modules.logrotate._parse_conf', MagicMock(return_value=PARSE_CONF)):
            kwargs = {'key': '/var/log/wtmp', 'value': 2}
            self.assertRaises(SaltInvocationError, logrotate.set_, **kwargs)

    def test_set_setting(self):
        '''
        Test if it set a new value for a specific configuration line
        '''
        with patch.dict(logrotate.__salt__,
                        {'file.replace': MagicMock(return_value=True)}), \
                patch('salt.modules.logrotate._parse_conf',
                      MagicMock(return_value=PARSE_CONF)):
            self.assertTrue(logrotate.set_('/var/log/wtmp', 'rotate', '2'))

    def test_set_setting_failed(self):
        '''
        Test if it fails to set a new value for a specific configuration line
        '''
        with patch('salt.modules.logrotate._parse_conf', MagicMock(return_value=PARSE_CONF)):
            kwargs = {'key': 'rotate',
                      'value': '/var/log/wtmp',
                      'setting': '2'}
            self.assertRaises(SaltInvocationError, logrotate.set_, **kwargs)
