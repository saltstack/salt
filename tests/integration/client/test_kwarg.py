# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase


class StdTest(ModuleCase):
    '''
    Test standard client calls
    '''
    def test_cli(self):
        '''
        Test cli function
        '''
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.arg',
                ['foo', 'bar', 'baz'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertEqual(data['args'], ['foo', 'bar', 'baz'])
            self.assertEqual(data['kwargs']['qux'], 'quux')

    def test_iter(self):
        '''
        test cmd_iter
        '''
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.arg',
                ['foo', 'bar', 'baz'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertEqual(data['args'], ['foo', 'bar', 'baz'])
            self.assertEqual(data['kwargs']['qux'], 'quux')

    def test_iter_no_block(self):
        '''
        test cmd_iter_no_block
        '''
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.arg',
                ['foo', 'bar', 'baz'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            if ret is None:
                continue
            data = ret['minion']['ret']
            self.assertEqual(data['args'], ['foo', 'bar', 'baz'])
            self.assertEqual(data['kwargs']['qux'], 'quux')

    def test_full_returns(self):
        '''
        test cmd_iter
        '''
        ret = self.client.cmd_full_return(
                'minion',
                'test.arg',
                ['foo', 'bar', 'baz'],
                kwarg={'qux': 'quux'}
                )
        data = ret['minion']['ret']
        self.assertEqual(data['args'], ['foo', 'bar', 'baz'])
        self.assertEqual(data['kwargs']['qux'], 'quux')

    def test_kwarg_type(self):
        '''
        Test that kwargs end up on the client as the same type
        '''
        terrible_yaml_string = 'foo: ""\n# \''
        ret = self.client.cmd_full_return(
                'minion',
                'test.arg_type',
                ['a', 1],
                kwarg={'outer': {'a': terrible_yaml_string},
                       'inner': 'value'}
                )
        data = ret['minion']['ret']
        self.assertIn('str', data['args'][0])
        self.assertIn('int', data['args'][1])
        self.assertIn('dict', data['kwargs']['outer'])
        self.assertIn('str', data['kwargs']['inner'])

    def test_full_return_kwarg(self):
        ret = self.client.cmd('minion', 'test.ping', full_return=True)
        for mid, data in ret.items():
            self.assertIn('retcode', data)
