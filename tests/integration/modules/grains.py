# -*- coding: utf-8 -*-

'''
Test the grains module
'''
# Import python libs
from __future__ import absolute_import
import os
import time

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
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
            self.run_function('grains.item', ['test_grain'])['test_grain'],
            opts['grains']['test_grain']
        )

    def test_ls(self):
        '''
        grains.ls
        '''
        check_for = (
            'cpu_flags',
            'cpu_model',
            'cpuarch',
            'domain',
            'fqdn',
            'gid',
            'groupname',
            'host',
            'kernel',
            'kernelrelease',
            'localhost',
            'mem_total',
            'num_cpus',
            'os',
            'os_family',
            'path',
            'pid',
            'ps',
            'pythonpath',
            'pythonversion',
            'saltpath',
            'saltversion',
            'uid',
            'username',
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
        time.sleep(5)
        ret = self.run_function('grains.item', ['setgrain'])
        if not ret:
            # Sleep longer, sometimes test systems get bogged down
            time.sleep(20)
            ret = self.run_function('grains.item', ['setgrain'])
        self.assertTrue(ret)

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
