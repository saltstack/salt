# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

import pytest


@pytest.mark.windows_whitelisted
class PublishModuleTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the publish module
    '''
    def test_publish(self):
        '''
        publish.publish
        '''
        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.ping'],
            f_timeout=50
        )
        assert ret == {'minion': True}

        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.kwarg'],
            f_arg='cheese=spam',
            f_timeout=50
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
            assert name in ret

        assert ret['cheese'] == 'spam'
        assert ret['__pub_arg'] == [{'cheese': 'spam'}]
        assert ret['__pub_id'] == 'minion'
        assert ret['__pub_fun'] == 'test.kwarg'

    def test_publish_yaml_args(self):
        '''
        test publish.publish yaml args formatting
        '''
        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.ping'],
            f_timeout=50
        )
        assert ret == {'minion': True}

        test_args_list = ['saltines, si', 'crackers, nein', 'cheese, indeed']
        test_args = '["{args[0]}", "{args[1]}", "{args[2]}"]'.format(args=test_args_list)
        ret = self.run_function(
            'publish.publish',
            ['minion', 'test.arg', test_args],
            f_timeout=50
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
            assert name in ret['kwargs']

        assert ret['args'] == test_args_list
        assert ret['kwargs']['__pub_id'] == 'minion'
        assert ret['kwargs']['__pub_fun'] == 'test.arg'

    def test_full_data(self):
        '''
        publish.full_data
        '''
        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.fib', 20],
            f_timeout=50
        )
        assert ret
        assert ret['minion']['ret'][0] == 6765

    def test_kwarg(self):
        '''
        Verify that the pub data is making it to the minion functions
        '''
        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.kwarg'],
            f_arg='cheese=spam',
            f_timeout=50
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
            assert name in ret

        assert ret['cheese'] == 'spam'
        assert ret['__pub_arg'] == [{'cheese': 'spam'}]
        assert ret['__pub_id'] == 'minion'
        assert ret['__pub_fun'] == 'test.kwarg'

        ret = self.run_function(
            'publish.full_data',
            ['minion', 'test.kwarg'],
            cheese='spam',
            f_timeout=50
        )
        assert 'The following keyword arguments are not valid' in ret

    def test_reject_minion(self):
        '''
        Test bad authentication
        '''
        ret = self.run_function(
            'publish.publish',
            ['minion', 'cmd.run', ['echo foo']],
            f_timeout=50
        )
        assert ret == {}
