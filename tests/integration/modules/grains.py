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
        opts = self.minion_opts()
        self.assertEqual(self.run_function('grains.items')['test_grain'], opts['grains']['test_grain'])

    def test_item(self):
        '''
        grains.item
        '''
        opts = self.minion_opts()
        self.assertEqual(self.run_function('grains.item', ['test_grain']), opts['grains']['test_grain'])

    def test_ls(self):
        '''
        grains.ls
        '''
        lsgrains = self.run_function('grains.ls')
        self.assertTrue('cpu_model' in lsgrains)
        self.assertTrue('cpu_flags' in lsgrains)
        self.assertTrue('cpuarch' in lsgrains)
        self.assertTrue('domain' in lsgrains)
        self.assertTrue('fqdn' in lsgrains)
        self.assertTrue('host' in lsgrains)
        self.assertTrue('kernel' in lsgrains)
        self.assertTrue('kernelrelease' in lsgrains)
        self.assertTrue('localhost' in lsgrains)
        self.assertTrue('mem_total' in lsgrains)
        self.assertTrue('num_cpus' in lsgrains)
        self.assertTrue('os' in lsgrains)
        self.assertTrue('path' in lsgrains)
        self.assertTrue('ps' in lsgrains)
        self.assertTrue('pythonpath' in lsgrains)
        self.assertTrue('pythonversion' in lsgrains)
        self.assertTrue('saltpath' in lsgrains)
        self.assertTrue('saltversion' in lsgrains)
        self.assertTrue('virtual' in lsgrains)
