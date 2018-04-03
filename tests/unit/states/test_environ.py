# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)
# Import salt libs
import salt.states.environ as envstate
import salt.modules.environ as envmodule


class TestEnvironState(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        loader_globals = {
            '__env__': 'base',
            '__opts__': {'test': False},
            '__salt__': {'environ.setenv': envmodule.setenv}
        }
        return {envstate: loader_globals, envmodule: loader_globals}

    def setUp(self):
        original_environ = os.environ.copy()
        os.environ = {'INITIAL': 'initial'}

        def reset_environ(original_environ):
            os.environ = original_environ
        self.addCleanup(reset_environ, original_environ)

    def test_setenv(self):
        '''
        test that a subsequent calls of setenv changes nothing
        '''
        ret = envstate.setenv('test', 'value')
        self.assertEqual(ret['changes'], {'test': 'value'})

        ret = envstate.setenv('test', 'other')
        self.assertEqual(ret['changes'], {'test': 'other'})

        # once again with the same value
        ret = envstate.setenv('test', 'other')
        self.assertEqual(ret['changes'], {})

    def test_setenv_permanent(self):
        with patch.dict(envmodule.__salt__, {'reg.set_value': MagicMock(), 'reg.delete_value': MagicMock()}), \
                patch('salt.utils.platform.is_windows', MagicMock(return_value=True)):
            ret = envstate.setenv('test', 'value', permanent=True)
            self.assertEqual(ret['changes'], {'test': 'value'})
            envmodule.__salt__['reg.set_value'].assert_called_with("HKCU", "Environment", 'test', 'value')

            ret = envstate.setenv('test', False, false_unsets=True, permanent=True)
            self.assertEqual(ret['changes'], {'test': None})
            envmodule.__salt__['reg.delete_value'].assert_called_with("HKCU", "Environment", 'test')

    def test_setenv_dict(self):
        '''
        test that setenv can be invoked with dict
        '''
        ret = envstate.setenv('notimportant', {'test': 'value'})
        self.assertEqual(ret['changes'], {'test': 'value'})

    def test_setenv_int(self):
        '''
        test that setenv can not be invoked with int
        (actually it's anything other than strings and dict)
        '''
        ret = envstate.setenv('test', 1)
        self.assertEqual(ret['result'], False)

    def test_setenv_unset(self):
        '''
        test that ``false_unsets`` option removes variable from environment
        '''
        ret = envstate.setenv('test', 'value')
        self.assertEqual(ret['changes'], {'test': 'value'})

        ret = envstate.setenv('notimportant', {'test': False}, false_unsets=True)
        self.assertEqual(ret['changes'], {'test': None})
        self.assertEqual(envstate.os.environ, {'INITIAL': 'initial'})

    def test_setenv_clearall(self):
        '''
        test that ``clear_all`` option sets other values to ''
        '''
        ret = envstate.setenv('test', 'value', clear_all=True)
        self.assertEqual(ret['changes'], {'test': 'value', 'INITIAL': ''})
        self.assertEqual(envstate.os.environ, {'test': 'value', 'INITIAL': ''})

    def test_setenv_clearall_with_unset(self):
        '''
        test that ``clear_all`` option combined with ``false_unsets``
        unsets other values from environment
        '''
        ret = envstate.setenv('test', 'value', false_unsets=True, clear_all=True)
        self.assertEqual(ret['changes'], {'test': 'value', 'INITIAL': None})
        self.assertEqual(envstate.os.environ, {'test': 'value'})

    def test_setenv_unset_multi(self):
        '''
        test basically same things that above tests but with multiple values passed
        '''
        ret = envstate.setenv('notimportant', {'foo': 'bar'})
        self.assertEqual(ret['changes'], {'foo': 'bar'})

        with patch.dict(envstate.__salt__, {'reg.read_value': MagicMock()}):
            ret = envstate.setenv(
                'notimportant', {'test': False, 'foo': 'baz'}, false_unsets=True)
        self.assertEqual(ret['changes'], {'test': None, 'foo': 'baz'})
        self.assertEqual(envstate.os.environ, {'INITIAL': 'initial', 'foo': 'baz'})

        with patch.dict(envstate.__salt__, {'reg.read_value': MagicMock()}):
            ret = envstate.setenv('notimportant', {'test': False, 'foo': 'bax'})
        self.assertEqual(ret['changes'], {'test': '', 'foo': 'bax'})
        self.assertEqual(envstate.os.environ, {'INITIAL': 'initial', 'foo': 'bax', 'test': ''})

    def test_setenv_test_mode(self):
        '''
        test that imitating action returns good values
        '''
        with patch.dict(envstate.__opts__, {'test': True}):
            ret = envstate.setenv('test', 'value')
            self.assertEqual(ret['changes'], {'test': 'value'})
            ret = envstate.setenv('INITIAL', 'initial')
            self.assertEqual(ret['changes'], {})
