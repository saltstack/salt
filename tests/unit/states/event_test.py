# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.states import event

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

ensure_in_syspath('../../')

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EventTestCase, needs_daemon=False)
