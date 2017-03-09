# -*- coding: utf-8 -*-
'''
Tests for the salt runner

.. versionadded:: 2016.11.0
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class SaltRunnerTest(integration.ShellCase):
    '''
    Test the salt runner
    '''
    def test_salt_cmd(self):
        '''
        test return values of salt.cmd
        '''
        ret = self.run_run_plus('salt.cmd', 'test.ping')
        out_ret = ret.get('out')[0]
        return_ret = ret.get('return')

        self.assertEqual(out_ret, 'True')
        self.assertTrue(return_ret)
