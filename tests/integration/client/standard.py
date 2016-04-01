# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


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
                'test.ping',
                )
        for ret in cmd_iter:
            self.assertTrue(ret['minion'])

        # make sure that the iter waits for long running jobs too
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.sleep',
                [6]
                )
        num_ret = 0
        for ret in cmd_iter:
            num_ret += 1
            self.assertTrue(ret['minion'])
        assert num_ret > 0

        # ping a minion that doesn't exist, to make sure that it doesn't hang forever
        # create fake mininion
        key_file = os.path.join(self.master_opts['pki_dir'], 'minions', 'footest')
        # touch the file
        salt.utils.fopen(key_file, 'a').close()
        # ping that minion and ensure it times out
        try:
            cmd_iter = self.client.cmd_cli(
                    'footest',
                    'test.ping',
                    )
            num_ret = 0
            for ret in cmd_iter:
                num_ret += 1
                self.assertTrue(ret['minion'])
            assert num_ret == 0
        finally:
            os.unlink(key_file)

    def test_iter(self):
        '''
        test cmd_iter
        '''
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.ping',
                )
        for ret in cmd_iter:
            self.assertTrue(ret['minion'])

    def test_iter_no_block(self):
        '''
        test cmd_iter_no_block
        '''
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.ping',
                )
        for ret in cmd_iter:
            if ret is None:
                continue
            self.assertTrue(ret['minion'])

    def test_full_returns(self):
        '''
        test cmd_iter
        '''
        ret = self.client.cmd_full_return(
                'minion',
                'test.ping',
                )
        self.assertIn('minion', ret)
        self.assertEqual({'ret': True, 'success': True}, ret['minion'])

        ret = self.client.cmd_full_return(
                'minion',
                'test.pong',
                )
        self.assertIn('minion', ret)

        if self.master_opts['transport'] == 'zeromq':
            self.assertEqual(
                {
                    'out': 'nested',
                    'ret': '\'test.pong\' is not available.',
                    'success': False
                },
                ret['minion']
            )
        elif self.master_opts['transport'] == 'raet':
            self.assertEqual(
                {'success': False, 'ret': '\'test.pong\' is not available.'},
                ret['minion']
            )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(StdTest)
