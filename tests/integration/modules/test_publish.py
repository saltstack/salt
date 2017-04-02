# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
import tests.integration as integration


class PublishModuleTest(integration.ModuleCase,
                        integration.SaltReturnAssertsMixin):
    '''
    Validate the publish module
    '''
    def test_publish(self):
        '''
        publish.publish
        '''
        ret = self.run_function('publish.publish', ['minion', 'test.ping'])
        self.assertEqual(ret, {'minion': True})

        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.kwarg'],
            f_arg='cheese=spam'
        )
        ret = ret['minion']

        check_true = (
            'cheese',
            '__pub_arg',
            '__pub_fun',
            '__pub_id',
            '__pub_jid',
            '__pub_ret',
            '__pub_tgt',
            '__pub_tgt_type',
        )
        for name in check_true:
            if name not in ret:
                print(name)
            self.assertTrue(name in ret)

        self.assertEqual(ret['cheese'], 'spam')
        self.assertEqual(ret['__pub_arg'], [{'cheese': 'spam'}])
        self.assertEqual(ret['__pub_id'], 'minion')
        self.assertEqual(ret['__pub_fun'], 'test.kwarg')

    def test_publish_yaml_args(self):
        '''
        test publish.publish yaml args formatting
        '''
        ret = self.run_function('publish.publish', ['minion', 'test.ping'])
        self.assertEqual(ret, {'minion': True})

        test_args_list = ['saltines, si', 'crackers, nein', 'cheese, indeed']
        test_args = '["{args[0]}", "{args[1]}", "{args[2]}"]'.format(args=test_args_list)
        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.arg', test_args]
        )
        ret = ret['minion']

        check_true = (
            '__pub_arg',
            '__pub_fun',
            '__pub_id',
            '__pub_jid',
            '__pub_ret',
            '__pub_tgt',
            '__pub_tgt_type',
        )
        for name in check_true:
            if name not in ret['kwargs']:
                print(name)
            self.assertTrue(name in ret['kwargs'])

        self.assertEqual(ret['args'], test_args_list)
        self.assertEqual(ret['kwargs']['__pub_id'], 'minion')
        self.assertEqual(ret['kwargs']['__pub_fun'], 'test.arg')

    def test_full_data(self):
        '''
        publish.full_data
        '''
        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.fib', 20]
        )
        self.assertTrue(ret)
        self.assertEqual(ret['minion']['ret'][0], 6765)

    def test_kwarg(self):
        '''
        Verify that the pub data is making it to the minion functions
        '''
        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.kwarg'],
            f_arg='cheese=spam'
        )
        ret = ret['minion']['ret']

        check_true = (
            'cheese',
            '__pub_arg',
            '__pub_fun',
            '__pub_id',
            '__pub_jid',
            '__pub_ret',
            '__pub_tgt',
            '__pub_tgt_type',
        )
        for name in check_true:
            if name not in ret:
                print(name)
            self.assertTrue(name in ret)

        self.assertEqual(ret['cheese'], 'spam')
        self.assertEqual(ret['__pub_arg'], [{'cheese': 'spam'}])
        self.assertEqual(ret['__pub_id'], 'minion')
        self.assertEqual(ret['__pub_fun'], 'test.kwarg')

        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.kwarg'],
            cheese='spam'
        )
        self.assertIn(
            'The following keyword arguments are not valid', ret
        )

    def test_reject_minion(self):
        '''
        Test bad authentication
        '''
        ret = self.run_function(
            'publish.publish',
            ['minion', 'cmd.run', ['echo foo']]
        )
        self.assertEqual(ret, {})
