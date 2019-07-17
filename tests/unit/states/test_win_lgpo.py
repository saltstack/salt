# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import Salt Libs
import salt.states.win_lgpo as win_lgpo


class WinSystemTestCase(TestCase):
    '''
    Test cases for the win_lgpo state
    '''

    def test__compare_policies_string(self):
        '''
        ``_compare_policies`` should only return ``True`` when the string values
        are the same. All other scenarios should return ``False``
        '''
        compare_string = 'Salty test'
        # Same
        self.assertTrue(
            win_lgpo._compare_policies(compare_string, compare_string)
        )
        # Different
        self.assertFalse(
            win_lgpo._compare_policies(compare_string, 'Not the same')
        )
        # List
        self.assertFalse(
            win_lgpo._compare_policies(compare_string, ['item1', 'item2'])
        )
        # Dict
        self.assertFalse(
            win_lgpo._compare_policies(compare_string, {'key': 'value'})
        )
        # None
        self.assertFalse(
            win_lgpo._compare_policies(compare_string, None)
        )

    def test__compare_policies_list(self):
        '''
        ``_compare_policies`` should only return ``True`` when the lists are the
        same. All other scenarios should return ``False``
        '''
        compare_list = ['Salty', 'test']
        # Same
        self.assertTrue(
            win_lgpo._compare_policies(compare_list, compare_list)
        )
        # Different
        self.assertFalse(
            win_lgpo._compare_policies(compare_list, ['Not', 'the', 'same'])
        )
        # String
        self.assertFalse(
            win_lgpo._compare_policies(compare_list, 'Not a list')
        )
        # Dict
        self.assertFalse(
            win_lgpo._compare_policies(compare_list, {'key': 'value'})
        )
        # None
        self.assertFalse(
            win_lgpo._compare_policies(compare_list, None)
        )

    def test__compare_policies_dict(self):
        '''
        ``_compare_policies`` should only return ``True`` when the dicts are the
        same. All other scenarios should return ``False``
        '''
        compare_dict = {'Salty': 'test'}
        # Same
        self.assertTrue(
            win_lgpo._compare_policies(compare_dict, compare_dict)
        )
        # Different
        self.assertFalse(
            win_lgpo._compare_policies(compare_dict, {'key': 'value'})
        )
        # String
        self.assertFalse(
            win_lgpo._compare_policies(compare_dict, 'Not a dict')
        )
        # List
        self.assertFalse(
            win_lgpo._compare_policies(compare_dict, ['Not', 'a', 'dict'])
        )
        # None
        self.assertFalse(
            win_lgpo._compare_policies(compare_dict, None)
        )
