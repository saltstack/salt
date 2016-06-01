# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration

GEM = 'rake'
GEM_VER = '11.1.2'
OLD_GEM = 'thor'
OLD_VERSION = '0.17.0'
DEFAULT_GEMS = ['bigdecimal', 'rake', 'json', 'rdoc']


@destructiveTest
class GemModuleTest(integration.ModuleCase):
    '''
    Validate gem module
    '''

    def test_install_uninstall(self):
        '''
        gem.install
        gem.uninstall
        '''
        self.assertFalse(self.run_function('gem.list', [GEM]))

        self.run_function('gem.install', [GEM])
        gem_list = self.run_function('gem.list', [GEM])
        self.assertEqual({'rake': ['11.1.2']}, gem_list)

        self.run_function('gem.uninstall', [GEM])
        self.assertFalse(self.run_function('gem.list', [GEM]))

    def test_install_version(self):
        '''
        gem.install rake version=11.1.2
        '''
        self.assertFalse(self.run_function('gem.list', [GEM]))

        self.run_function('gem.install', [GEM], version=GEM_VER)
        gem_list = self.run_function('gem.list', [GEM])
        self.assertEqual({'rake': ['11.1.2']}, gem_list)

        self.run_function('gem.uninstall', [GEM])
        self.assertFalse(self.run_function('gem.list', [GEM]))

    def test_list(self):
        '''
        gem.list
        '''
        self.run_function('gem.install', [GEM])

        all_ret = self.run_function('gem.list')
        for gem in DEFAULT_GEMS:
            self.assertIn(gem, all_ret)

        single_ret = self.run_function('gem.list', [GEM])
        self.assertEqual({'rake': ['11.1.2']}, single_ret)

        self.run_function('gem.uninstall', [GEM])

    def test_list_upgrades(self):
        '''
        gem.list_upgrades
        '''
        # install outdated gem
        ret = self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)

        ret = self.run_function('gem.list_upgrades')
        self.assertIn(OLD_GEM, ret)

        self.run_function('gem.uninstall', [OLD_GEM])

    def test_sources_add_remove(self):
        '''
        gem.sources_add
        gem.sources_remove
        '''
        sources_list = self.run_function('gem.sources_list')
        source = 'http://gems.github.com'
        self.assertNotIn(source, sources_list)

        self.run_function('gem.sources_add', [source])
        sources_list = self.run_function('gem.sources_list')
        self.assertIn(source, sources_list)

        self.run_function('gem.sources_remove', [source])
        sources_list = self.run_function('gem.sources_list')
        self.assertNotIn(source, sources_list)

    def test_sources_list(self):
        '''
        gem.sources_list
        '''
        ret = self.run_function('gem.sources_list')
        self.assertIn('https://rubygems.org/', ret)

    def test_update(self):
        '''
        gem.update
        '''
        self.assertFalse(self.run_function('gem.list', [OLD_GEM]))

        self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)
        gem_list = self.run_function('gem.list', [OLD_GEM])
        self.assertEqual({'thor': ['0.17.0']} , gem_list)

        ret = self.run_function('gem.update', [OLD_GEM])
        gem_list = self.run_function('gem.list', [OLD_GEM])
        self.assertEqual({'thor': ['0.19.1', '0.17.0']} , gem_list)

        ret = self.run_function('gem.uninstall', [OLD_GEM])
        self.assertFalse(self.run_function('gem.list', [OLD_GEM]))

    def test_udpate_system(self):
        '''
        gem.udpate_system
        '''
        ret = self.run_function('gem.update_system')
        self.assertTrue(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(GemModuleTest)
