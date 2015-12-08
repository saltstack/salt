# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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
from salt.modules import chef

# Globals
chef.__grains__ = {}
chef.__salt__ = {}
chef.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ChefTestCase(TestCase):
    '''
    Test cases for salt.modules.chef
    '''
    # 'client' function tests: 1

    @patch('salt.modules.chef._exec_cmd', MagicMock(return_value={}))
    @patch('salt.utils.which', MagicMock(return_value=True))
    def test_client(self):
        '''
        Test if it execute a chef client run and return a dict
        '''
        self.assertDictEqual(chef.client(), {})

    # 'solo' function tests: 1

    @patch('salt.modules.chef._exec_cmd', MagicMock(return_value={}))
    @patch('salt.utils.which', MagicMock(return_value=True))
    def test_solo(self):
        '''
        Test if it execute a chef solo run and return a dict
        '''
        self.assertDictEqual(chef.solo('/dev/sda1'), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ChefTestCase, needs_daemon=False)
