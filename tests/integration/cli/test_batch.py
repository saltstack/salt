# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
import tests.integration as integration


class BatchTest(integration.ShellCase):
    '''
    Integration tests for the salt.cli.batch module
    '''

    def test_batch_run(self):
        '''
        Tests executing a simple batch command to help catch regressions
        '''
        ret = 'Executing run on [\'sub_minion\']'
        cmd = self.run_salt('\'*\' test.echo \'batch testing\' -b 50%')
        self.assertIn(ret, cmd)

    def test_batch_run_number(self):
        '''
        Tests executing a simple batch command using a number division instead of
        a percentage with full batch CLI call.
        '''
        ret = "Executing run on ['minion', 'sub_minion']"
        cmd = self.run_salt('\'*\' test.ping --batch-size 2')
        self.assertIn(ret, cmd)

    def test_batch_run_grains_targeting(self):
        '''
        Tests executing a batch command using a percentage divisor as well as grains
        targeting.
        '''
        os_grain = ''
        sub_min_ret = "Executing run on ['sub_minion']"
        min_ret = "Executing run on ['minion']"

        for item in self.run_salt('minion grains.get os'):
            if item != 'minion':
                os_grain = item

        os_grain = os_grain.strip()
        cmd = self.run_salt('-G \'os:{0}\' -b 25% test.ping'.format(os_grain))
        self.assertIn(sub_min_ret, cmd)
        self.assertIn(min_ret, cmd)

    def test_batch_exit_code(self):
        '''
        Test that a failed state returns a non-zero exit code in batch mode
        '''
        cmd = self.run_salt(' "*" state.single test.fail_without_changes name=test_me -b 25%', with_retcode=True)
        self.assertEqual(cmd[-1], 2)
