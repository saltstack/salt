'''
Test the grains module
'''
# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class TestModulesGrains(integration.ModuleCase):
    '''
    Test the grains module
    '''
    def test_items(self):
        '''
        grains.items
        '''
        opts = self.minion_opts
        self.assertEqual(
            self.run_function('grains.items')['test_grain'],
            opts['grains']['test_grain']
        )

    def test_item(self):
        '''
        grains.item
        '''
        opts = self.minion_opts
        self.assertEqual(
            self.run_function('grains.item', ['test_grain']),
            opts['grains']['test_grain']
        )

    def test_ls(self):
        '''
        grains.ls
        '''
        check_for = (
            'cpuarch',
            'cpu_flags',
            'cpu_model',
            'domain',
            'fqdn',
            'host',
            'kernel',
            'kernelrelease',
            'localhost',
            'mem_total',
            'num_cpus',
            'os',
            'path',
            'ps',
            'pythonpath',
            'pythonversion',
            'saltpath',
            'saltversion',
            'virtual',
        )
        lsgrains = self.run_function('grains.ls')
        for grain_name in check_for:
            self.assertTrue(grain_name in lsgrains)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestModulesGrains)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
