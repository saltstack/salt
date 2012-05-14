# Import python libs
import os
import sys
import hashlib

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon

class AliasesTest(integration.ModuleCase):
    '''
    Validate aliases module
    '''
    def test_set_target(self):
        '''
        aliases.set_target and aliases.get_target
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        self.assertTrue(set_ret)
        tgt_ret = self.run_function(
                'aliases.get_target',
                alias='fred')
        self.assertEqual(tgt_ret, 'target=bob')

    def test_has_target(self):
        '''
        aliases.set_target and aliases.has_target
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        self.assertTrue(set_ret)
        tgt_ret = self.run_function(
                'aliases.has_target',
                alias='fred',
                target='bob')
        self.assertTrue(tgt_ret)
