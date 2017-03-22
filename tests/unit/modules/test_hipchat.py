# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.hipchat as hipchat


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HipchatTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.hipchat
    '''
    def setup_loader_modules(self):
        return {hipchat: {}}

    # 'list_rooms' function tests: 1

    @patch('salt.modules.hipchat._query', MagicMock(return_value=True))
    def test_list_rooms(self):
        '''
        Test if it list all HipChat rooms.
        '''
        self.assertEqual(hipchat.list_rooms(), True)

    # 'list_users' function tests: 1

    @patch('salt.modules.hipchat._query', MagicMock(return_value=True))
    def test_list_users(self):
        '''
        Test if it list all HipChat users.
        '''
        self.assertEqual(hipchat.list_users(), True)

    # 'find_room' function tests: 1

    def test_find_room(self):
        '''
        Test if it find a room by name and return it.
        '''
        mock = MagicMock(return_value=[{'name': 'Development Room'}])
        with patch.object(hipchat, 'list_rooms', mock):
            self.assertEqual(hipchat.find_room('Development Room'),
                             {'name': 'Development Room'})

            self.assertEqual(hipchat.find_room('QA Room'), False)

    # 'find_user' function tests: 1

    def test_find_user(self):
        '''
        Test if it find a user by name and return it.
        '''
        mock = MagicMock(return_value=[{'name': 'Thomas Hatch'}])
        with patch.object(hipchat, 'list_rooms', mock):
            self.assertEqual(hipchat.find_room('Thomas Hatch'),
                             {'name': 'Thomas Hatch'})

            self.assertEqual(hipchat.find_user('Salt QA'), False)

    # 'send_message' function tests: 1

    @patch('salt.modules.hipchat._query', MagicMock(return_value=True))
    def test_send_message(self):
        '''
        Test if it send a message to a HipChat room.
        '''
        self.assertEqual(hipchat.send_message('Development Room',
                                              'Build is done',
                                              'Build Server'), True)

    @patch('salt.modules.hipchat._query', MagicMock(return_value=False))
    def test_send_message_false(self):
        '''
        Test if it send a message to a HipChat room.
        '''
        self.assertEqual(hipchat.send_message('Development Room',
                                              'Build is done',
                                              'Build Server'), False)
