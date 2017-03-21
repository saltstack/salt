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
import salt.states.hipchat as hipchat

hipchat.__salt__ = {}
hipchat.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HipchatTestCase(TestCase):
    '''
    Test cases for salt.states.hipchat
    '''
    # 'send_message' function tests: 1

    def test_send_message(self):
        '''
        Test to send a message to a Hipchat room.
        '''
        name = 'salt'
        room_id = '123456'
        from_name = 'SuperAdmin'
        message = 'This state was executed successfully.'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        with patch.dict(hipchat.__opts__, {'test': True}):
            comt = ('The following message is to be sent to Hipchat: {0}'
                    .format(message))
            ret.update({'comment': comt})
            self.assertDictEqual(hipchat.send_message(name, room_id, from_name,
                                                      message), ret)

        with patch.dict(hipchat.__opts__, {'test': False}):
            comt = ('Hipchat room id is missing: {0}'.format(name))
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(hipchat.send_message(name, None, from_name,
                                                      message), ret)

            comt = ('Hipchat from name is missing: {0}'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(hipchat.send_message(name, room_id, None,
                                                      message), ret)

            comt = ('Hipchat message is missing: {0}'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(hipchat.send_message(name, room_id, from_name,
                                                      None), ret)

            mock = MagicMock(return_value=True)
            with patch.dict(hipchat.__salt__, {'hipchat.send_message': mock}):
                comt = ('Sent message: {0}'.format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(hipchat.send_message(name, room_id,
                                                          from_name, message),
                                     ret)
