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
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.exceptions import SaltInvocationError
import salt.states.test as test


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the test state
    '''
    def setup_loader_modules(self):
        return {test: {'__low__': {'__reqs__': {'watch': ''}}}}

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
        Test test.configurable_test_state with and without comment
        '''
        # Configure mock parameters
        mock_name = 'cheese_shop'
        mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
        mock_changes = {
            'testing': {
                'old': 'Unchanged',
                'new': 'Something pretended to change'
            }
        }

        # Test default state with comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': True,
                        'comment': ''}
            ret = test.configurable_test_state(mock_name)
            self.assertDictEqual(ret, mock_ret)

        # Test default state without comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': True,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

    def test_configurable_test_state_changes(self):
        '''
        Test test.configurable_test_state with permutations of changes and with
        comment
        '''
        # Configure mock parameters
        mock_name = 'cheese_shop'
        mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
        mock_changes = {
            'testing': {
                'old': 'Unchanged',
                'new': 'Something pretended to change'
            }
        }

        # Test changes=Random and comment
        with patch.dict(test.__opts__, {'test': False}):
            ret = test.configurable_test_state(mock_name,
                                               changes='Random',
                                               comment=mock_comment)
            self.assertEqual(ret['name'], mock_name)
            self.assertIn(ret['changes'], [mock_changes, {}])
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['comment'], mock_comment)

        # Test changes=True and comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': True,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               changes=True,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test changes=False and comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': {},
                        'result': True,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               changes=False,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test changes=Cheese
        with patch.dict(test.__opts__, {'test': False}):
            self.assertRaises(SaltInvocationError,
                              test.configurable_test_state,
                              mock_name,
                              changes='Cheese')

    def test_configurable_test_state_result(self):
        '''
        Test test.configurable_test_state with permutations of result and with
        comment
        '''
        # Configure mock parameters
        mock_name = 'cheese_shop'
        mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
        mock_changes = {
            'testing': {
                'old': 'Unchanged',
                'new': 'Something pretended to change'
            }
        }

        # Test result=Random and comment
        with patch.dict(test.__opts__, {'test': False}):
            ret = test.configurable_test_state(mock_name,
                                               result='Random',
                                               comment=mock_comment)
            self.assertEqual(ret['name'], mock_name)
            self.assertEqual(ret['changes'], mock_changes)
            self.assertIn(ret['result'], [True, False])
            self.assertEqual(ret['comment'], mock_comment)

        # Test result=True and comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': True,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               result=True,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test result=False and comment
        with patch.dict(test.__opts__, {'test': False}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': False,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               result=False,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test result=Cheese
        with patch.dict(test.__opts__, {'test': False}):
            self.assertRaises(SaltInvocationError,
                              test.configurable_test_state,
                              mock_name,
                              result='Cheese')

    def test_configurable_test_state_test(self):
        '''
        Test test.configurable_test_state with test=True with and without
        comment
        '''
        # Configure mock parameters
        mock_name = 'cheese_shop'
        mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
        mock_changes = {
            'testing': {
                'old': 'Unchanged',
                'new': 'Something pretended to change'
            }
        }

        # Test test=True without comment
        with patch.dict(test.__opts__, {'test': True}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': None,
                        'comment': 'This is a test'}
            ret = test.configurable_test_state(mock_name)
            self.assertDictEqual(ret, mock_ret)

        # Test test=True with comment
        with patch.dict(test.__opts__, {'test': True}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': None,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test test=True and changes=True with comment
        with patch.dict(test.__opts__, {'test': True}):
            mock_ret = {'name': mock_name,
                        'changes': mock_changes,
                        'result': None,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               changes=True,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

        # Test test=True and changes=False with comment
        with patch.dict(test.__opts__, {'test': True}):
            mock_ret = {'name': mock_name,
                        'changes': {},
                        'result': True,
                        'comment': mock_comment}
            ret = test.configurable_test_state(mock_name,
                                               changes=False,
                                               comment=mock_comment)
            self.assertDictEqual(ret, mock_ret)

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
