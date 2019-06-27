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
        self.assertIsNotNone(masterconfig)
        self.assertIsInstance(masterconfig, dict)
        self.assertEqual(masterconfig['__role'], {'master'})
