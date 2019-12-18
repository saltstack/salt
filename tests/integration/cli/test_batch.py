# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import ShellCase

# Import Salt libs
import salt.utils.platform


class BatchTest(ShellCase):
    '''
    Integration tests for the salt.cli.batch module
    '''
    if salt.utils.platform.is_windows():
        run_timeout = 180
    else:
        run_timeout = 30

    def test_batch_run(self):
        '''
        Tests executing a simple batch command to help catch regressions
        '''
        ret = 'Executing run on [{0}]'.format(repr('sub_minion'))
        cmd = self.run_salt(
            '"*minion" test.echo "batch testing" -b 50%',
            timeout=self.run_timeout,
        )
        self.assertIn(ret, cmd)

    def test_batch_run_number(self):
        '''
        Tests executing a simple batch command using a number division instead of
        a percentage with full batch CLI call.
        '''
        ret = "Executing run on [{0}, {1}]".format(repr('minion'), repr('sub_minion'))
        cmd = self.run_salt(
            '"*minion" test.ping --batch-size 2',
            timeout=self.run_timeout,
        )
        self.assertIn(ret, cmd)

    def test_batch_run_grains_targeting(self):
        '''
        Tests executing a batch command using a percentage divisor as well as grains
        targeting.
        '''
        os_grain = ''
        sub_min_ret = "Executing run on [{0}]".format(repr('sub_minion'))
        min_ret = "Executing run on [{0}]".format(repr('minion'))

        for item in self.run_salt('minion grains.get os'):
            if item != 'minion:':
                os_grain = item

        os_grain = os_grain.strip()
        cmd = self.run_salt(
            '-C "G@os:{0} and not localhost" -b 25% test.ping'.format(os_grain),
            timeout=self.run_timeout,
        )
        self.assertIn(sub_min_ret, cmd)
        self.assertIn(min_ret, cmd)

    def test_batch_exit_code(self):
        '''
        Test that a failed state returns a non-zero exit code in batch mode
        '''
        cmd = self.run_salt(
            ' "*" state.single test.fail_without_changes name=test_me -b 25%',
            with_retcode=True,
            timeout=self.run_timeout,
        )
        self.assertEqual(cmd[-1], 2)

# Test for failhard + batch. The best possible solution here was to do something like that:
# assertRaises(StopIteration)
# But it's impossible due to nature of the tests execution via fork()

    def test_batch_module_stopping_after_error(self):
        '''
        Test that a failed command stops the batch run
        '''

        minions_list = []
        retcode = None

        # Executing salt with batch: 1 and with failhard. It should stop after the first error.
        cmd = self.run_salt(
            '"*minion" test.retcode 42 -b 1 --out=yaml --failhard',
            timeout=self.run_timeout,
        )

        # Parsing the output. Idea is to fetch number on minions and retcode of the execution.
        # retcode var could be overwritten in case of broken failhard but number of minions check should still fail.
        for line in cmd:
            if line.startswith('Executing run on'):
                minions_list.append(line)
            if line.startswith('retcode'):
                retcode = line[-1]
        # We expect to have only one minion to be run
        self.assertEqual(1, len(minions_list))
        # We expect to find a retcode in the output
        self.assertIsNot(None, retcode)
        # We expect retcode to be non-zero
        self.assertNotEqual(0, retcode)

    def test_batch_state_stopping_after_error(self):
        '''
        Test that a failed state stops the batch run
        '''

        minions_list = []
        retcode = None

        # Executing salt with batch: 1 and with failhard. It should stop after the first error.
        cmd = self.run_salt(
            '"*minion" state.single test.fail_without_changes name=test_me -b 1 --out=yaml --failhard',
            timeout=self.run_timeout,
        )

        # Parsing the output. Idea is to fetch number on minions and retcode of the execution.
        # retcode var could be overwritten in case of broken failhard but number of minions check should still fail.
        for line in cmd:
            if line.startswith('Executing run on'):
                minions_list.append(line)
            if line.startswith('retcode'):
                retcode = line[-1]
        # We expect to have only one minion to be run
        self.assertEqual(1, len(minions_list))
        # We expect to find a retcode in the output
        self.assertIsNot(None, retcode)
        # We expect retcode to be non-zero
        self.assertNotEqual(0, retcode)
