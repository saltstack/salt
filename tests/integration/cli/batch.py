# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import integration

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class BatchTest(integration.ShellCase):
    '''
    Integration tests for the salt.cli.batch module
    '''

    def test_batch_run(self):
        '''
        Tests executing a simple batch command to help catch regressions
        '''
        ret = ['',
               "Executing run on ['sub_minion']",
               '',
               'sub_minion:',
               'retcode:',
               '    0',
               '    batch testing',
               '',
               "Executing run on ['minion']",
               '',
               'minion:',
               'retcode:',
               '    0',
               '    batch testing']
        ret = sorted(ret)
        cmd = sorted(self.run_salt('\'*\' test.echo \'batch testing\' -b 50%'))
        self.assertListEqual(cmd, ret)

    def test_batch_run_number(self):
        '''
        Tests executing a simple batch command using a number division instead of
        a percentage with full batch CLI call.
        '''
        ret = ['',
               "Executing run on ['sub_minion', 'minion']",
               '',
               'retcode:',
               '    0',
               'sub_minion:',
               '    True',
               'minion:',
               '    True',
               'retcode:',
               '    0']
        cmd = sorted(self.run_salt('\'*\' test.ping --batch-size 2'))
        self.assertListEqual(cmd, sorted(ret))

    def test_batch_run_grains_targeting(self):
        '''
        Tests executing a batch command using a percentage divisor as well as grains
        targeting.
        '''
        os_grain = ''
        ret = ['',
               "Executing run on ['sub_minion']",
               '',
               'retcode:',
               '    0',
               'sub_minion:',
               '    True',
               '',
               "Executing run on ['minion']",
               '',
               'minion:',
               '    True',
               'retcode:',
               '    0']

        for item in self.run_salt('minion grains.get os'):
            if item != 'minion':
                os_grain = item

        os_grain = os_grain.strip()
        cmd = sorted(self.run_salt('-G \'os:{0}\' -b 25% test.ping'.format(os_grain)))
        self.assertListEqual(cmd, sorted(ret))

    def test_batch_exit_code(self):
        '''
        Test that a failed state returns a non-zero exit code in batch mode
        '''
        cmd = self.run_salt(' "*" state.single test.fail_without_changes name=test_me -b 25%', with_retcode=True)
        self.assertEqual(cmd[-1], 2)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(BatchTest)
