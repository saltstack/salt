# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class AliasesTest(integration.ModuleCase):
    '''
    Validate aliases module
    '''
    def not_test_set_target(self):
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

    def not_test_has_target(self):
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

    def not_test_list_aliases(self):
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
        self.assertIn('alias=fred', tgt_ret)

    def test_rm_alias(self):
        '''
        aliases.rm_alias
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='frank',
                target='greg')
        self.assertTrue(set_ret)
        set_ret = self.run_function(
                'aliases.rm_alias',
                alias='frank')
        tgt_ret = self.run_function(
                'aliases.list_aliases')
        self.assertIsInstance(tgt_ret, dict)
        self.assertNotIn('alias=frank', tgt_ret)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(AliasesTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
