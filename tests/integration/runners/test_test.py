# -*- coding: utf-8 -*-
'''
Tests for the test runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import ShellCase


class TestRunnerTest(ShellCase):
    '''
    Test the test runner.
    '''

    def test_get_opts(self):
        '''
        Test test.get_opts runner
        '''
        masterconfig = self.run_run('test.get_opts')
        # returns ['__cli:', '    cli_salt_run.py', '__role:', '    master', ......
        self.assertIsNotNone(masterconfig)
        self.assertIsInstance(masterconfig, list)
        # assert __role: master
        role_found = False
        for line in masterconfig:
            if line == '__role:':
                role_found = True
                continue
            if role_found:
                self.assertEqual(line, '    master')
                break
