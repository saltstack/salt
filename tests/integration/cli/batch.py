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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BatchTest)
