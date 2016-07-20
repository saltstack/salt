# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
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

from salt.modules import event
import salt.utils.event
import sys
sys.path.append('/home/kapil/salt/salt/utils')

# Globals
event.__grains__ = {}
event.__salt__ = {}
event.__context__ = {}
event.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EventTestCase(TestCase):
    '''
    Test cases for salt.modules.event
    '''
    @patch('salt.crypt.SAuth')
    @patch('salt.transport.Channel.factory')
    def test_fire_master(self,
                         salt_crypt_sauth,
                         salt_transport_channel_factory):
        '''
        Test for Fire an event off up to the master server
        '''

        preload = {'id': 'id', 'tag': 'tag', 'data': 'data',
                   'tok': 'salt', 'cmd': '_minion_event'}

        with patch.dict(event.__opts__, {'transport': 'raet',
                                         'id': 'id'}):
            with patch.object(salt_transport_channel_factory, 'send',
                              return_value=None):
                self.assertTrue(event.fire_master('data', 'tag'))

        with patch.dict(event.__opts__, {'transport': 'A',
                                         'id': 'id',
                                         'master_uri': 'localhost'}):
            with patch.object(salt_crypt_sauth, 'gen_token',
                              return_value='tok'):
                with patch.object(salt_transport_channel_factory, 'send',
                                  return_value=None):
                    self.assertTrue(event.fire_master('data', 'tag', preload))

        with patch.dict(event.__opts__, {'transport': 'A'}):
            with patch.object(salt.utils.event.MinionEvent, 'fire_event',
                              side_effect=Exception('foo')):
                self.assertFalse(event.fire_master('data', 'tag'))

    @patch('salt.utils.event')
    def test_fire(self, salt_utils_event):
        '''
        Test to fire an event on the local minion event bus.
        Data must be formed as a dict.
        '''
        with patch.object(salt_utils_event, 'get_event'):
            self.assertFalse(event.fire('data', 'tag'))

        with patch.dict(event.__opts__, {'sock_dir': True, 'transport': True}):
            with patch.object(salt_utils_event, 'get_event') as mock:
                mock.fire_event = MagicMock(return_value=True)
                self.assertTrue(event.fire('data', 'tag'))

    def test_send(self):
        '''
        Test for Send an event to the Salt Master
        '''
        with patch.object(event, 'fire_master', return_value='B'):
            self.assertEqual(event.send('tag'), 'B')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(EventTestCase, needs_daemon=False)
