# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import json

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import salt.modules.pagerduty as pagerduty


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PagerdutyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.pagerduty
    '''
    loader_module = pagerduty

    def loader_module_globals(self):
        return {
            '__salt__': {'config.option': MagicMock(return_value=None)}
        }

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
