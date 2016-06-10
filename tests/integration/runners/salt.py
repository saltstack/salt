# -*- coding: utf-8 -*-
'''
Tests for the salt runner

.. versionadded:: Carbon
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class SaltRunnerTest(integration.ShellCase):
    '''
    Test the salt runner
    '''
    def test_salt_cmd(self):
        '''
        salt.cmd
        '''
        ret = self.run_run_plus('salt.cmd', 'test.ping')
        self.assertTrue(ret.get('out')[0])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SaltRunnerTest)
