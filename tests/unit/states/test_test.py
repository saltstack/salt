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
from salt.states import test

# Globals
test.__salt__ = {}
test.__opts__ = {}
test.__low__ = {'__reqs__': {'watch': ''}}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestTestCase(TestCase):
    '''
        Validate the test state
    '''
    def test_succeed_without_changes(self):
        '''
            Test to returns successful.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        with patch.dict(test.__opts__, {"test": False}):
            ret.update({'comment': 'Success!'})
            self.assertDictEqual(test.succeed_without_changes('salt'), ret)

    def test_fail_without_changes(self):
        '''
            Test to returns failure.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        with patch.dict(test.__opts__, {"test": False}):
            ret.update({'comment': 'Failure!'})
            self.assertDictEqual(test.fail_without_changes('salt'), ret)

    def test_succeed_with_changes(self):
        '''
            Test to returns successful and changes is not empty
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        with patch.dict(test.__opts__, {"test": False}):
            ret.update({'changes': {'testing': {'new': 'Something pretended'
                                                ' to change',
                                                'old': 'Unchanged'}},
                        'comment': 'Success!', 'result': True})
            self.assertDictEqual(test.succeed_with_changes('salt'), ret)

    def test_fail_with_changes(self):
        '''
            Test to returns failure and changes is not empty.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        with patch.dict(test.__opts__, {"test": False}):
            ret.update({'changes': {'testing': {'new': 'Something pretended'
                                                ' to change',
                                                'old': 'Unchanged'}},
                        'comment': 'Success!',
                        'result': True})
            self.assertDictEqual(test.succeed_with_changes('salt'), ret)

    def test_configurable_test_state(self):
        '''
            Test of a configurable test state which
            determines its output based on the inputs.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        with patch.dict(test.__opts__, {"test": False}):
            ret.update({'changes': {'testing': {'new': 'Something pretended'
                                                ' to change',
                                                'old': 'Unchanged'}},
                        'comment': 'Success!'})
            self.assertDictEqual(test.succeed_with_changes('salt'), ret)

    def test_mod_watch(self):
        '''
            Test to call this function via a watch statement
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        ret.update({'changes': {'Requisites with changes': []},
                    'comment': 'Watch statement fired.'})
        self.assertDictEqual(test.mod_watch('salt'), ret)

    def test_check_pillar_present(self):
        '''
            Test to ensure the check_pillar function
            works properly with the 'present' keyword in
            the absence of a 'type' keyword.
        '''
        ret = {
            'name': 'salt',
            'changes': {},
            'result': True,
            'comment': ''
        }
        pillar_return = 'I am a pillar.'
        pillar_mock = MagicMock(return_value=pillar_return)
        with patch.dict(test.__salt__, {'pillar.get': pillar_mock}):
            self.assertEqual(test.check_pillar('salt', present='my_pillar'), ret)

    def test_check_pillar_dictionary(self):
        '''
            Test to ensure the check_pillar function
            works properly with the 'key_type' checks,
            using the dictionary key_type.
        '''
        ret = {
            'name': 'salt',
            'changes': {},
            'result': True,
            'comment': ''
        }
        pillar_return = {'this': 'dictionary'}
        pillar_mock = MagicMock(return_value=pillar_return)
        with patch.dict(test.__salt__, {'pillar.get': pillar_mock}):
            self.assertEqual(test.check_pillar('salt', dictionary='my_pillar'), ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestTestCase, needs_daemon=False)
