# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


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
        self.assertEqual(tgt_ret, 'bob')

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

    def test_list_aliases(self):
        '''
        aliases.list_aliases
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        self.assertTrue(set_ret)
        tgt_ret = self.run_function(
                'aliases.list_aliases')
        self.assertIsInstance(tgt_ret, dict)
        self.assertIn('fred', tgt_ret)

    def test_rm_alias(self):
        '''
        aliases.rm_alias
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='frank',
                target='greg')
        self.assertTrue(set_ret)
        self.run_function(
            'aliases.rm_alias',
            alias='frank')
        tgt_ret = self.run_function(
                'aliases.list_aliases')
        self.assertIsInstance(tgt_ret, dict)
        self.assertNotIn('alias=frank', tgt_ret)
