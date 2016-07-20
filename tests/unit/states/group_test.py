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
from salt.states import group

# Globals
group.__salt__ = {}
group.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GroupTestCase(TestCase):
    '''
        Validate the group state
    '''
    def test_present(self):
        '''
            Test to ensure that a group is present
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': {}
               }

        ret.update({'comment': 'Error: Conflicting options "members" with'
                    ' "addusers" and/or "delusers" can not be used together. ',
                    'result': None})
        self.assertDictEqual(group.present("salt", delusers=True,
                                           members=True), ret)

        ret.update({'comment': 'Error. Same user(s) can not be'
                    ' added and deleted simultaneously'})
        self.assertDictEqual(group.present("salt", addusers=['a'],
                                           delusers=['a']), ret)

        ret.update({'comment': 'The following group attributes are set'
                    ' to be changed:\nkey1: value1\nkey0: value0\n'})
        mock = MagicMock(side_effect=[{'key0': 'value0',
                                       'key1': 'value1'}, False, False, False])
        with patch.object(group, '_changes', mock):
            with patch.dict(group.__opts__, {"test": True}):
                self.assertDictEqual(group.present("salt"), ret)

                ret.update({'comment': 'Group salt set to be added'})
                self.assertDictEqual(group.present("salt"), ret)

            with patch.dict(group.__opts__, {"test": False}):
                mock = MagicMock(return_value=[{'gid': 1, 'name': 'stack'}])
                with patch.dict(group.__salt__, {'group.getent': mock}):
                    ret.update({'result': False,
                                'comment': 'Group salt is not present but'
                                ' gid 1 is already taken by group stack'})
                    self.assertDictEqual(group.present("salt", 1), ret)

                    mock = MagicMock(return_value=False)
                    with patch.dict(group.__salt__, {'group.add': mock}):
                        ret.update({'comment':
                                    'Failed to create new group salt'})
                        self.assertDictEqual(group.present("salt"), ret)

    def test_absent(self):
        '''
            Test to ensure that the named group is absent
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': {}
               }
        mock = MagicMock(side_effect=[True, True, True, False])
        with patch.dict(group.__salt__, {'group.info': mock}):
            with patch.dict(group.__opts__, {"test": True}):
                ret.update({'result': None,
                            'comment': 'Group salt is set for removal'})
                self.assertDictEqual(group.absent("salt"), ret)

            with patch.dict(group.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, False])
                with patch.dict(group.__salt__, {'group.delete': mock}):
                    ret.update({'result': True, 'changes': {'salt': ''},
                                'comment': 'Removed group salt'})
                    self.assertDictEqual(group.absent('salt'), ret)

                    ret.update({'changes': {}, 'result': False,
                                'comment': 'Failed to remove group salt'})
                    self.assertDictEqual(group.absent('salt'), ret)

            ret.update({'result': True,
                        'comment': 'Group not present'})
            self.assertDictEqual(group.absent('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GroupTestCase, needs_daemon=False)
