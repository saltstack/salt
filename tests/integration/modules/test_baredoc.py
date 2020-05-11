# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase


class BaredocTest(ModuleCase):
    '''
    Validate baredoc module
    '''
    def test_baredoc_module_and_args(self):
        '''
        baredoc.modules_and_args
        '''
        ret = self.run_function('baredoc.modules_and_args', states=True)
        self.assertIn('state.highstate', ret)
        self.assertIn('xml.value_present', ret)
        self.assertIn('xpath', ret['xml.value_present'])

    def test_baredoc_modules_with_test(self):
        '''
        baredoc.modules_and_args
        '''
        ret = self.run_function('baredoc.modules_with_test')
        self.assertIn('pkg.install', ret)
