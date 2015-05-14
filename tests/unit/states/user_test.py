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
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import user

# Globals
user.__salt__ = {}
user.__opts__ = {}
user.__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UserTestCase(TestCase):
    '''
        Validate the user state
    '''
    def test_present(self):
        '''
            Test to ensure that the named user is present with
            the specified properties
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        mock = MagicMock(return_value=False)
        mock2 = MagicMock(return_value=[])
        with patch.dict(user.__salt__, {'group.info': mock,
                                        'user.info': mock2,
                                        "user.chkey": mock2,
                                        'user.add': mock}):
            ret.update({'comment': 'The following group(s) are'
                        ' not present: salt'})
            self.assertDictEqual(user.present('salt', groups=['salt']), ret)

            mock = MagicMock(side_effect=[{'key': 'value'}, {'key': 'value'},
                                          {'key': 'value'}, False, False])
            with patch.object(user, '_changes', mock):
                with patch.dict(user.__opts__, {"test": True}):
                    ret.update({'comment': 'The following user attributes are'
                                ' set to be changed:\nkey: value\n',
                                'result': None})
                    self.assertDictEqual(user.present('salt'), ret)

                with patch.dict(user.__opts__, {"test": False}):
                    with patch.dict(user.__grains__, {"kernel": False}):
                        ret.update({'comment': "These values could not be"
                                    " changed: {'key': 'value'}",
                                    'result': False})
                        self.assertDictEqual(user.present('salt'), ret)

                        with patch.dict(user.__opts__, {"test": True}):
                            ret.update({'comment': 'User salt set to'
                                        ' be added', 'result': None})
                            self.assertDictEqual(user.present('salt'), ret)

                        with patch.dict(user.__opts__, {"test": False}):
                            ret.update({'comment': 'Failed to create new'
                                        ' user salt', 'result': False})
                            self.assertDictEqual(user.present('salt'), ret)

    def test_absent(self):
        '''
            Test to ensure that the named user is absent
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}
        mock = MagicMock(side_effect=[True, True, False])
        mock1 = MagicMock(return_value=False)
        with patch.dict(user.__salt__, {'user.info': mock,
                                        'user.delete': mock1,
                                        'group.info': mock1}):
            with patch.dict(user.__opts__, {"test": True}):
                ret.update({'comment': 'User salt set for removal'})
                self.assertDictEqual(user.absent('salt'), ret)

            with patch.dict(user.__opts__, {"test": False}):
                ret.update({'comment': 'Failed to remove user salt',
                            'result': False})
                self.assertDictEqual(user.absent('salt'), ret)

            ret.update({'comment': 'User salt is not present',
                        'result': True})
            self.assertDictEqual(user.absent('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UserTestCase, needs_daemon=False)
