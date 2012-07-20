'''
Test the grains module
'''
import integration


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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestModulesGrains)
