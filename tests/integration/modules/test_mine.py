# -*- coding: utf-8 -*-
'''
Test the salt mine system
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import time
import pprint

# Import Salt Testing libs
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class MineTest(ModuleCase):
    '''
    Test the mine system
    '''
    def setUp(self):
        self.wait_for_all_jobs()

    def test_get(self):
        '''
        test mine.get and mine.update
        '''
        assert self.run_function('mine.update', minion_tgt='minion')
        # The sub_minion does not have mine_functions defined in its configuration
        # In this case, mine.update returns None
        assert self.run_function(
                'mine.update',
                minion_tgt='sub_minion'
            ) is None
        # Since the minion has mine_functions defined in its configuration,
        # mine.update will return True
        assert self.run_function(
                'mine.get',
                ['minion', 'test.ping']
            )

    def test_send(self):
        '''
        test mine.send
        '''
        assert not self.run_function(
                'mine.send',
                ['foo.__spam_and_cheese']
            )
        assert self.run_function(
                'mine.send',
                ['grains.items'],
                minion_tgt='minion',
            )
        assert self.run_function(
                'mine.send',
                ['grains.items'],
                minion_tgt='sub_minion',
            )
        ret = self.run_function(
            'mine.get',
            ['sub_minion', 'grains.items']
        )
        assert ret['sub_minion']['id'] == 'sub_minion'
        ret = self.run_function(
            'mine.get',
            ['minion', 'grains.items'],
            minion_tgt='sub_minion'
        )
        assert ret['minion']['id'] == 'minion'

    def test_mine_flush(self):
        '''
        Test mine.flush
        '''
        # TODO The calls to sleep were added in an attempt to make this tests
        # less flaky. If we still see it fail we need to look for a more robust
        # solution.
        for minion_id in ('minion', 'sub_minion'):
            assert self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt=minion_id
                )
            time.sleep(1)
        for minion_id in ('minion', 'sub_minion'):
            ret = self.run_function(
                'mine.get',
                [minion_id, 'grains.items'],
                minion_tgt=minion_id
            )
            assert ret[minion_id]['id'] == minion_id
            time.sleep(1)
        assert self.run_function(
                'mine.flush',
                minion_tgt='minion'
            )
        time.sleep(1)
        ret_flushed = self.run_function(
            'mine.get',
            ['*', 'grains.items']
        )
        assert ret_flushed.get('minion', None) is None
        assert ret_flushed['sub_minion']['id'] == 'sub_minion'

    def test_mine_delete(self):
        '''
        Test mine.delete
        '''
        assert self.run_function(
                'mine.send',
                ['grains.items'],
                minion_tgt='minion'
            )
        self.wait_for_all_jobs(minions=('minion',))

        attempts = 10
        ret_grains = None
        while True:
            if ret_grains:
                break
            # Smoke testing that grains should now exist in the mine
            ret_grains = self.run_function(
                'mine.get',
                ['minion', 'grains.items'],
                minion_tgt='minion'
            )
            if ret_grains and 'minion' in ret_grains:
                break

            if attempts:
                attempts -= 1

            if attempts:
                time.sleep(1.5)
                continue

            self.fail(
                '\'minion\' was not found as a key of the \'mine.get\' \'grains.items\' call. Full return: {}'.format(
                    pprint.pformat(ret_grains)
                )
            )

        assert ret_grains['minion']['id'] == 'minion', \
            '{} != minion, full return payload: {}'.format(
                ret_grains['minion']['id'],
                pprint.pformat(ret_grains)
            )
        assert self.run_function(
                'mine.send',
                ['test.arg', 'foo=bar', 'fnord=roscivs'],
                minion_tgt='minion'
            )
        self.wait_for_all_jobs(minions=('minion',))
        ret_args = self.run_function(
            'mine.get',
            ['minion', 'test.arg']
        )
        expected = {
            'minion': {
                'args': [],
                'kwargs': {
                    'fnord': 'roscivs',
                    'foo': 'bar',
                },
            },
        }
        # Smoke testing that test.arg exists in the mine
        assert ret_args == expected
        assert self.run_function(
                'mine.send',
                ['test.echo', 'foo'],
                minion_tgt='minion'
            )
        self.wait_for_all_jobs(minions=('minion',))
        ret_echo = self.run_function(
            'mine.get',
            ['minion', 'test.echo'],
            minion_tgt='minion'
        )
        # Smoke testing that we were also able to set test.echo in the mine
        assert ret_echo['minion'] == 'foo'
        assert self.run_function(
                'mine.delete',
                ['test.arg'],
                minion_tgt='minion'
            )
        self.wait_for_all_jobs(minions=('minion',))
        ret_arg_deleted = self.run_function(
            'mine.get',
            ['minion', 'test.arg'],
            minion_tgt='minion'
        )
        # Now comes the real test - did we obliterate test.arg from the mine?
        # We could assert this a different way, but there shouldn't be any
        # other tests that are setting this mine value, so this should
        # definitely avoid any race conditions.
        assert not (ret_arg_deleted.get('minion', {})
                           .get('kwargs', {})
                           .get('fnord', None) == 'roscivs'), \
            '{} contained "fnord":"roscivs", which should be gone'.format(
                ret_arg_deleted,
            )
        ret_echo_stays = self.run_function(
            'mine.get',
            ['minion', 'test.echo'],
            minion_tgt='minion'
        )
        # Of course, one more health check - we want targeted removal.
        # This isn't horseshoes or hand grenades - test.arg should go away
        # but test.echo should still be available.
        assert ret_echo_stays['minion'] == 'foo'
