# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import aliases
from salt.exceptions import SaltInvocationError

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AliasesTestCase(TestCase):
    '''
    TestCase for salt.modules.aliases module
    '''

    mock_alias = [('foo', 'bar@example.com', '')]
    mock_alias_mult = [('foo', 'bar@example.com', ''),
                       ('hello', 'world@earth.com, earth@world.com', '')]

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias))
    def test_list_aliases(self):
        '''
        Tests the return of a file containing one alias
        '''
        ret = {'foo': 'bar@example.com'}
        self.assertEqual(aliases.list_aliases(), ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_list_aliases_mult(self):
        '''
        Tests the return of a file containing multiple aliases
        '''
        ret = {'foo': 'bar@example.com',
               'hello': 'world@earth.com, earth@world.com'}
        self.assertEqual(aliases.list_aliases(), ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias))
    def test_get_target(self):
        '''
        Tests the target returned by an alias with one target
        '''
        ret = 'bar@example.com'
        self.assertEqual(aliases.get_target('foo'), ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_get_target_mult(self):
        '''
        Tests the target returned by an alias with multiple targets
        '''
        ret = 'world@earth.com, earth@world.com'
        self.assertEqual(aliases.get_target('hello'), ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias))
    def test_get_target_no_alias(self):
        '''
        Tests return of an alias doesn't exist
        '''
        self.assertEqual(aliases.get_target('pizza'), '')

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias))
    def test_has_target(self):
        '''
        Tests simple return known alias and target
        '''
        ret = aliases.has_target('foo', 'bar@example.com')
        self.assertTrue(ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias))
    def test_has_target_no_alias(self):
        '''
        Tests return of empty alias and known target
        '''
        ret = aliases.has_target('', 'bar@example.com')
        self.assertFalse(ret)

    def test_has_target_no_target(self):
        '''
        Tests return of known alias and empty target
        '''
        self.assertRaises(SaltInvocationError, aliases.has_target, 'foo', '')

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_has_target_mult(self):
        '''
        Tests return of multiple targets to one alias
        '''
        ret = aliases.has_target('hello',
                                 'world@earth.com, earth@world.com')
        self.assertTrue(ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_has_target_mult_differs(self):
        '''
        Tests return of multiple targets to one alias in opposite order
        '''
        ret = aliases.has_target('hello',
                                 'earth@world.com, world@earth.com')
        self.assertFalse(ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_has_target_list_mult(self):
        '''
        Tests return of target as same list to know alias
        '''
        ret = aliases.has_target('hello', ['world@earth.com',
                                           'earth@world.com'])
        self.assertTrue(ret)

    @patch('salt.modules.aliases.__parse_aliases',
           MagicMock(return_value=mock_alias_mult))
    def test_has_target_list_mult_differs(self):
        '''
        Tests return of target as differing list to known alias
        '''
        ret = aliases.has_target('hello', ['world@earth.com',
                                           'mars@space.com'])
        self.assertFalse(ret)

    @patch('salt.modules.aliases.get_target', MagicMock(return_value='bar@example.com'))
    def test_set_target_equal(self):
        '''
        Tests return when target is already present
        '''
        alias = 'foo'
        target = 'bar@example.com'
        ret = aliases.set_target(alias, target)
        self.assertTrue(ret)

    def test_set_target_empty_alias(self):
        '''
        Tests return of empty alias
        '''
        self.assertRaises(SaltInvocationError, aliases.set_target, '', 'foo')

    def test_set_target_empty_target(self):
        '''
        Tests return of known alias and empty target
        '''
        self.assertRaises(SaltInvocationError, aliases.set_target, 'foo', '')

    @patch('salt.modules.aliases.get_target', MagicMock(return_value=''))
    def test_rm_alias_absent(self):
        '''
        Tests return when alias is not present
        '''
        ret = aliases.rm_alias('foo')
        self.assertTrue(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AliasesTestCase, needs_daemon=False)
