# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
import integration
import salt.ext.six as six


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
        cmd = self.run_salt('\'*\' test.echo \'batch testing\' -b 50%')
        if six.PY3:
            self.assertCountEqual(cmd, ret)
        else:
            self.assertListEqual(sorted(cmd), sorted(ret))

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
        cmd = self.run_salt('\'*\' test.ping --batch-size 2')
        if six.PY3:
            self.assertCountEqual(cmd, ret)
        else:
            self.assertListEqual(sorted(cmd), sorted(ret))

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
        cmd = self.run_salt('-G \'os:{0}\' -b 25% test.ping'.format(os_grain))
        if six.PY3:
            self.assertCountEqual(cmd, ret)
        else:
            self.assertListEqual(sorted(cmd), sorted(ret))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BatchTest)
