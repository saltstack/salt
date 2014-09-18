# -*- coding: utf-8 -*-

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
                'test.ping',
                )
        for ret in cmd_iter:
            self.assertTrue(ret['minion'])

        # Test timeouts, a timeout of > 0 should timeout
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=2
                )
        self.assertRaises(StopIteration,
                          cmd_iter.next)

        # A timeout of 0 means wait until done
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=0
                )
        num_ret = 0
        for ret in cmd_iter:
            num_ret += 1
            self.assertTrue(ret['minion'])
        assert num_ret > 0

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

        # Test timeouts, a timeout of > 0 should timeout
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=2
                )
        self.assertRaises(StopIteration,
                          cmd_iter.next)

        # A timeout of 0 means wait until done
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=0
                )
        num_ret = 0
        for ret in cmd_iter:
            num_ret += 1
            self.assertTrue(ret['minion'])
        assert num_ret > 0

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

        # Test timeouts, a timeout of > 0 should timeout
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=2
                )
        num_ret = 0
        for ret in cmd_iter:
            if ret is None:
                continue
            num_ret += 1
        assert num_ret == 0

        # A timeout of 0 means wait until done
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=0
                )
        num_ret = 0
        for ret in cmd_iter:
            if ret is None:
                continue
            num_ret += 1
            self.assertTrue(ret['minion'])
        assert num_ret > 0

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

        # Test timeouts, a timeout of > 0 should timeout
        ret = self.client.cmd_full_return(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=2
                )
        assert len(ret) == 0

        # A timeout of 0 means wait until done
        ret = self.client.cmd_full_return(
                'minion',
                'test.sleep',
                arg=[5],
                timeout=0
                )
        assert len(ret) > 0

if __name__ == '__main__':
    from integration import run_tests
    run_tests(StdTest)
