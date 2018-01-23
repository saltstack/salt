# -*- coding: utf-8 -*-
'''
Tests man spm
'''
# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase


class SPMManTest(ModuleCase):
    '''
    Validate man spm
    '''
    def test_man_spm(self):
        '''
        test man spm
        '''
        cmd = self.run_function('cmd.run', ['man spm'])
        self.assertIn('Salt Package Manager', cmd)
        self.assertIn('command for managing Salt packages', cmd)
