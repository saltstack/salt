# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import junos

# Globals
junos.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JunosTestCase(TestCase):
    '''
    Test cases for salt.modules.junos
    '''
    def test_facts_refresh(self):
        '''
        Test for Reload the facts dictionary from the device
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertTrue(junos.facts_refresh())

    def test_set_hostname(self):
        '''
        Test for set hostname
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertEqual(junos.set_hostname(), {'out': False})

            with patch.object(junos, 'commit', return_value=None):
                self.assertIsNone(junos.set_hostname('host', True))

            self.assertDictEqual(junos.set_hostname('host', False),
                                 {'msg': 'set system host-name host is queued',
                                  'out': True})

    def test_commit(self):
        '''
        Test for commit
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertDictEqual(junos.commit(),
                                 {'message': 'Commit Successful.',
                                  'out': True})

    def test_rollback(self):
        '''
        Test for rollback
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertEqual(junos.rollback()['message'],
                             'Rollback successful')

    def test_diff(self):
        '''
        Test for diff
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertTrue(junos.diff()['out'])

    def test_ping(self):
        '''
        Test for ping
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(junos.__opts__, {'proxyobject': mock}):
            self.assertIsNone(junos.ping())

if __name__ == '__main__':
    from integration import run_tests
    run_tests(JunosTestCase, needs_daemon=False)
