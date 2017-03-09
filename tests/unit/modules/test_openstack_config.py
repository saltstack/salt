# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import openstack_config
from salt.exceptions import CommandExecutionError

# Globals
openstack_config.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OpenstackConfigTestCase(TestCase):
    '''
    Test cases for salt.modules.openstack_config
    '''
    # 'set_' function tests: 1

    @patch('salt.utils.which', MagicMock(return_value=True))
    def test_set(self):
        '''
        Test if it set a value in an OpenStack configuration file.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(openstack_config.set_('/etc/keystone/keys.conf',
                                                   'sql', 'connection', 'foo'),
                             'salt')

        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, openstack_config.set_,
                              '/etc/keystone/keystone.conf', 'sql',
                              'connection', 'foo')

    # 'get' function tests: 1

    @patch('salt.utils.which', MagicMock(return_value=True))
    def test_get(self):
        '''
        Test if it get a value from an OpenStack configuration file.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(openstack_config.get('/etc/keystone/keys.conf',
                                                  'sql', 'connection'), 'salt')

        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, openstack_config.get,
                              '/etc/key/keystone.conf', 'sql', 'connection')

    # 'delete' function tests: 1

    @patch('salt.utils.which', MagicMock(return_value=True))
    def test_delete(self):
        '''
        Test if it delete a value from an OpenStack configuration file.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(openstack_config.delete('/etc/keystone/keys.conf',
                                                     'sql', 'connection'),
                             'salt')

        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'error',
                                       'stdout': 'salt'})
        with patch.dict(openstack_config.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, openstack_config.delete,
                              '/etc/key/keystone.conf', 'sql', 'connection')
