# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration

GEM = 'rake'
GEM_VER = '11.1.2'
OLD_GEM = 'thor'
OLD_VERSION = '0.17.0'
DEFAULT_GEMS = ['bigdecimal', 'rake', 'json', 'rdoc']


class GemModuleTest(integration.ModuleCase):
    '''
    Validate gem module
    '''

    def test_install_uninstall(self):
        '''
        gem.install
        gem.uninstall
        '''
        ret = self.run_function('gem.install', [GEM])
        self.assertIn('Successfully installed {0}'.format(GEM), ret)

        rm_ret = self.run_function('gem.uninstall', [GEM])
        self.assertIn('Successfully uninstalled {0}'.format(GEM), rm_ret)

    def test_install_version(self):
        '''
        gem.install rake version=11.1.2
        '''
        ret = self.run_function('gem.install', [GEM], version=GEM_VER)
        self.assertEqual('Successfully installed rake-11.1.2\n1 gem installed', ret)

        self.run_function('gem.uninstall', [GEM])

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
        self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)

        ret = self.run_function('gem.list_upgrades')
        self.assertIn('thor', ret)

        self.run_function('gem.uninstalled', [OLD_GEM])

    def test_sources_add_remove(self):
        '''
        gem.sources_add
        gem.sources_remove
        '''
        source = 'http://gems.github.com'
        add_ret = self.run_function('gem.sources_add', [source])
        self.assertEqual('http://gems.github.com added to sources', add_ret)

        rm_ret = self.run_function('gem.sources_remove', [source])
        self.assertEqual('http://gems.github.com removed from sources', rm_ret)

    def test_sources_list(self):
        '''
        gem.sources_list
        '''
        ret = self.run_function('gem.sources_list')
        self.assertEqual(['https://rubygems.org/'], ret)

    def test_update(self):
        '''
        gem.update
        '''
        self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)
        ret = self.run_function('gem.update', [OLD_GEM])
        self.assertIn('Gems updated: thor', ret)
        self.run_function('gem.uninstall', [OLD_GEM])

    def test_udpate_system(self):
        '''
        gem.udpate_system
        '''
        ret = self.run_function('gem.update_system')
        self.assertTrue(ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(GemInstallTest, GemModuletest)
