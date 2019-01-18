# -*- coding: utf-8 -*-
'''
Test the salt mine system
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import time

# Import Salt Testing libs
from tests.support.case import ModuleCase


class MineTest(ModuleCase):
    '''
    Test the mine system
    '''
    def test_get(self):
        '''
        test mine.get and mine.update
        '''
        self.assertTrue(self.run_function('mine.update', minion_tgt='minion'))
        # The sub_minion does not have mine_functions defined in its configuration
        # In this case, mine.update returns None
        self.assertIsNone(
            self.run_function(
                'mine.update',
                minion_tgt='sub_minion'
            )
        )
        # Since the minion has mine_functions defined in its configuration,
        # mine.update will return True
        self.assertTrue(
            self.run_function(
                'mine.get',
                ['minion', 'test.ping']
            )
        )

    def test_send(self):
        '''
        test mine.send
        '''
        self.assertFalse(
            self.run_function(
                'mine.send',
                ['foo.__spam_and_cheese']
            )
        )
        self.assertTrue(
            self.run_function(
                'mine.send',
                ['grains.items'],
                minion_tgt='minion',
            )
        )
        self.assertTrue(
            self.run_function(
                'mine.send',
                ['grains.items'],
                minion_tgt='sub_minion',
            )
        )
        ret = self.run_function(
            'mine.get',
            ['sub_minion', 'grains.items']
        )
        self.assertEqual(ret['sub_minion']['id'], 'sub_minion')
        ret = self.run_function(
            'mine.get',
            ['minion', 'grains.items'],
            minion_tgt='sub_minion'
        )
        self.assertEqual(ret['minion']['id'], 'minion')

    def test_mine_flush(self):
        '''
        Test mine.flush
        '''
        # TODO The calls to sleep were added in an attempt to make this tests
        # less flaky. If we still see it fail we need to look for a more robust
        # solution.
        for minion_id in ('minion', 'sub_minion'):
            self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt=minion_id
                )
            )
            time.sleep(1)
        for minion_id in ('minion', 'sub_minion'):
            ret = self.run_function(
                'mine.get',
                [minion_id, 'grains.items'],
                minion_tgt=minion_id
            )
            self.assertEqual(ret[minion_id]['id'], minion_id)
            time.sleep(1)
        self.assertTrue(
            self.run_function(
                'mine.flush',
                minion_tgt='minion'
            )
        )
        time.sleep(1)
        ret_flushed = self.run_function(
            'mine.get',
            ['*', 'grains.items']
        )
        self.assertEqual(ret_flushed.get('minion', None), None)
        self.assertEqual(ret_flushed['sub_minion']['id'], 'sub_minion')

    def test_mine_delete(self):
        '''
        Test mine.delete
        '''
        # TODO The calls to sleep were added in an attempt to make this tests
        # less flaky. If we still see it fail we need to look for a more robust
        # solution.
        self.assertTrue(
            self.run_function(
                'mine.send',
                ['grains.items']
            )
        )
        time.sleep(1)
        # Smoke testing that grains should now exist in the mine
        ret_grains = self.run_function(
            'mine.get',
            ['minion', 'grains.items']
        )
        self.assertEqual(ret_grains['minion']['id'], 'minion')
        self.assertTrue(
            self.run_function(
                'mine.send',
                ['test.arg', 'foo=bar', 'fnord=roscivs'],
            )
        )
        time.sleep(1)
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
        self.assertDictEqual(ret_args, expected)
        self.assertTrue(
            self.run_function(
                'mine.send',
                ['test.echo', 'foo']
            )
        )
        time.sleep(1)
        ret_echo = self.run_function(
            'mine.get',
            ['minion', 'test.echo']
        )
        # Smoke testing that we were also able to set test.echo in the mine
        self.assertEqual(ret_echo['minion'], 'foo')
        self.assertTrue(
            self.run_function(
                'mine.delete',
                ['test.arg']
            )
        )
        time.sleep(1)
        ret_arg_deleted = self.run_function(
            'mine.get',
            ['minion', 'test.arg']
        )
        # Now comes the real test - did we obliterate test.arg from the mine?
        # We could assert this a different way, but there shouldn't be any
        # other tests that are setting this mine value, so this should
        # definitely avoid any race conditions.
        self.assertFalse(
            ret_arg_deleted.get('minion', {})
                           .get('kwargs', {})
                           .get('fnord', None) == 'roscivs',
            '{} contained "fnord":"roscivs", which should be gone'.format(
                ret_arg_deleted,
            )
        )
        ret_echo_stays = self.run_function(
            'mine.get',
            ['minion', 'test.echo']
        )
        # Of course, one more health check - we want targeted removal.
        # This isn't horseshoes or hand grenades - test.arg should go away
        # but test.echo should still be available.
        self.assertEqual(ret_echo_stays['minion'], 'foo')
