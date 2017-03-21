# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.states.event as event

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

event.__opts__ = {}
event.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EventTestCase(TestCase):
    '''
        Validate the event state
    '''
    def test_send(self):
        '''
            Test to send an event to the Salt Master
        '''
        with patch.dict(event.__opts__, {'test': True}):
            self.assertDictEqual(event.send("salt"),
                                 {'changes': {'data': None, 'tag': 'salt'},
                                  'comment': 'Event would have been fired',
                                  'name': 'salt',
                                  'result': None
                                  }
                                 )

        with patch.dict(event.__opts__, {'test': False}):
            mock = MagicMock(return_value=True)
            with patch.dict(event.__salt__, {'event.send': mock}):
                self.assertDictEqual(event.send("salt"),
                                     {'changes': {'data': None, 'tag': 'salt'},
                                      'comment': 'Event fired',
                                      'name': 'salt',
                                      'result': True
                                      })

    def test_wait(self):
        '''
            Test to fire an event on the Salt master
        '''
        self.assertDictEqual(event.wait("salt"),
                             {'changes': {},
                              'comment': '',
                              'name': 'salt',
                              'result': True}
                             )
