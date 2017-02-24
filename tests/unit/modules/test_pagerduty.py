# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
import salt.utils
from salt.modules import pagerduty
import json

# Globals
pagerduty.__opts__ = {}
pagerduty.__salt__ = {
    'config.option': MagicMock(return_value=None)
    }


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PagerdutyTestCase(TestCase):
    '''
    Test cases for salt.modules.pagerduty
    '''
    def test_list_services(self):
        '''
        Test for List services belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_services(), 'A')

    def test_list_incidents(self):
        '''
        Test for List incidents belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_incidents(), 'A')

    def test_list_users(self):
        '''
        Test for List users belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_users(), 'A')

    def test_list_schedules(self):
        '''
        Test for List schedules belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_schedules(), 'A')

    def test_list_windows(self):
        '''
        Test for List maintenance windows belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_windows(), 'A')

    def test_list_policies(self):
        '''
        Test for List escalation policies belonging to this account
        '''
        with patch.object(salt.utils.pagerduty,
                          'list_items', return_value='A'):
            self.assertEqual(pagerduty.list_policies(), 'A')

    def test_create_event(self):
        '''
        Test for Create an event in PagerDuty. Designed for use in states.
        '''
        with patch.object(json, 'loads', return_value=['A']):
            with patch.object(salt.utils.pagerduty, 'query',
                              return_value='A'):
                self.assertListEqual(pagerduty.create_event(), ['A'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PagerdutyTestCase, needs_daemon=False)
