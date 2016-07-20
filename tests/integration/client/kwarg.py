# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class StdTest(integration.ModuleCase):
    '''
    Test standard client calls
    '''
    def test_cli(self):
        '''
        Test cli function
        '''
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_iter(self):
        '''
        test cmd_iter
        '''
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_iter_no_block(self):
        '''
        test cmd_iter_no_block
        '''
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            if ret is None:
                continue
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_full_returns(self):
        '''
        test cmd_iter
        '''
        ret = self.client.cmd_full_return(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        data = ret['minion']
        self.assertIn('foo', data['ret'])
        self.assertIn('baz', data['ret'])
        self.assertIn('qux', data['ret'])
        self.assertEqual(data['ret']['foo'], 'bar')
        self.assertEqual(data['ret']['baz'], 'quo')
        self.assertEqual(data['ret']['qux'], 'quux')

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StdTest)
