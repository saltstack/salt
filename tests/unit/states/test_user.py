# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.states.user as user


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UserTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the user state
    '''
    def setup_loader_modules(self):
        return {user: {}}

    def test_present(self):
        '''
            Test to ensure that the named user is present with
            the specified properties
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        mock_false = MagicMock(return_value=False)
        mock_empty_list = MagicMock(return_value=[])
        with patch.dict(user.__grains__, {"kernel": 'Linux'}):
            with patch.dict(user.__salt__, {'group.info': mock_false,
                                            'user.info': mock_empty_list,
                                            "user.chkey": mock_empty_list,
                                            'user.add': mock_false}):
                ret.update({'comment': 'The following group(s) are'
                            ' not present: salt'})
                self.assertDictEqual(user.present('salt', groups=['salt']), ret)

                mock_false = MagicMock(side_effect=[{'key': 'value'}, {'key': 'value'},
                                              {'key': 'value'}, False, False])
                with patch.object(user, '_changes', mock_false):
                    with patch.dict(user.__opts__, {"test": True}):
                        ret.update(
                            {'comment': 'The following user attributes are set '
                                        'to be changed:\n'
                                        'key: value\n',
                             'result': None})
                        self.assertDictEqual(user.present('salt'), ret)

                    with patch.dict(user.__opts__, {"test": False}):
                        # pylint: disable=repr-flag-used-in-string
                        comment = (
                            'These values could not be changed: {0!r}'
                            .format({'key': 'value'})
                        )
                        # pylint: enable=repr-flag-used-in-string
                        ret.update({'comment': comment, 'result': False})
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
