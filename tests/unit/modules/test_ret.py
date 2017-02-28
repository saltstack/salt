# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import ret
import salt.loader

# Globals
ret.__opts__ = {}
ret.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RetTestCase(TestCase):
    '''
    Test cases for salt.modules.ret
    '''
    # 'get_jid' function tests: 1

    def test_get_jid(self):
        '''
        Test if it return the information for a specified job id
        '''
        mock_ret = MagicMock(return_value='DB')
        with patch.object(salt.loader, 'returners',
                          MagicMock(return_value={'redis.get_jid': mock_ret})):
            self.assertEqual(ret.get_jid('redis', 'net'), 'DB')

    # 'get_fun' function tests: 1

    def test_get_fun(self):
        '''
        Test if it return info about last time fun was called on each minion
        '''
        mock_ret = MagicMock(return_value='DB')
        with patch.object(salt.loader, 'returners',
                          MagicMock(return_value={'mysql.get_fun': mock_ret})):
            self.assertEqual(ret.get_fun('mysql', 'net'), 'DB')

    # 'get_jids' function tests: 1

    def test_get_jids(self):
        '''
        Test if it return a list of all job ids
        '''
        mock_ret = MagicMock(return_value='DB')
        with patch.object(salt.loader, 'returners',
                          MagicMock(return_value={'mysql.get_jids': mock_ret})):
            self.assertEqual(ret.get_jids('mysql'), 'DB')

    # 'get_minions' function tests: 1

    def test_get_minions(self):
        '''
        Test if it return a list of all minions
        '''
        mock_ret = MagicMock(return_value='DB')
        with patch.object(salt.loader, 'returners',
                          MagicMock(return_value=
                                    {'mysql.get_minions': mock_ret})):
            self.assertEqual(ret.get_minions('mysql'), 'DB')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RetTestCase, needs_daemon=False)
