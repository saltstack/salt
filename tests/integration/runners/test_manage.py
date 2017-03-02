# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class ManageTest(integration.ShellCase):
    '''
    Test the manage runner
    '''
    def test_up(self):
        '''
        manage.up
        '''
        ret = self.run_run_plus('manage.up')
        self.assertIn('minion', ret['return'])
        self.assertIn('sub_minion', ret['return'])
        self.assertTrue(any('- minion' in out for out in ret['out']))
        self.assertTrue(any('- sub_minion' in out for out in ret['out']))

    def test_down(self):
        '''
        manage.down
        '''
        ret = self.run_run_plus('manage.down')
        self.assertNotIn('minion', ret['return'])
        self.assertNotIn('sub_minion', ret['return'])
        self.assertNotIn('minion', ret['out'])
        self.assertNotIn('sub_minion', ret['out'])
