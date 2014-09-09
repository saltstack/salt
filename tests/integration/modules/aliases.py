# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AliasesTest)
