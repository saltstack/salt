# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import aptpkg

aptpkg.__opts__ = {}
aptpkg.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AptTestCase(TestCase):
    '''
    Test cases for salt.states.aptpkg
    '''
    # 'held' function tests: 1

    def test_held(self):
        '''
        Test to set package in 'hold' state, meaning it will not be upgraded.
        '''
        name = 'tmux'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': 'Package {0} does not have a state'.format(name)}

        mock = MagicMock(return_value=False)
        with patch.dict(aptpkg.__salt__, {'pkg.get_selections': mock}):
            self.assertDictEqual(aptpkg.held(name), ret)
