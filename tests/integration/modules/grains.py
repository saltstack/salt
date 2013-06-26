'''
Test the grains module
'''
# Import python libs
import time
import os

# Import salt libs
import integration
from saltunittest import skipIf


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
            self.run_function('grains.item', ['test_grain'])['test_grain'],
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
            'os_family',
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

    @skipIf(os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None,
            'Travis environment can\'t keep up with salt refresh')
    def test_set_val(self):
        '''
        test grains.set_val
        '''
        self.assertEqual(
                self.run_function(
                    'grains.setval',
                    ['setgrain', 'grainval']),
                {'setgrain': 'grainval'})
        time.sleep(1)
        self.assertTrue(
                self.run_function(
                    'grains.item', ['setgrain']
                    )
                )

    def test_get(self):
        '''
        test grains.get
        '''
        self.assertEqual(
                self.run_function(
                    'grains.get',
                    ['level1:level2']),
                'foo')



if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestModulesGrains)
