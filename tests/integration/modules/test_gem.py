# -*- coding: utf-8 -*-
'''
Integration tests for Ruby Gem module
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import salt libs
import salt.utils
import salt.utils.http

GEM = 'tidy'
GEM_VER = '1.1.2'
OLD_GEM = 'thor'
OLD_VERSION = '0.17.0'
GEM_LIST = [GEM, OLD_GEM]


def check_status():
    '''
    Check the status of the rubygems source
    '''
    try:
        ret = salt.utils.http.query('https://rubygems.org', status=True)
    except Exception:
        return False
    return ret['status'] == 200


@destructiveTest
@skipIf(not salt.utils.which('gem'), 'Gem is not available')
@skipIf(not check_status(), 'External source \'https://rubygems.org\' is not available')
class GemModuleTest(integration.ModuleCase):
    '''
    Validate gem module
    '''

    def test_install_uninstall(self):
        '''
        gem.install
        gem.uninstall
        '''
        # Remove gem if it is already installed
        if self.run_function('gem.list', [GEM]):
            self.run_function('gem.uninstall', [GEM])

        self.run_function('gem.install', [GEM])
        gem_list = self.run_function('gem.list', [GEM])
        self.assertIn(GEM, gem_list)

        self.run_function('gem.uninstall', [GEM])
        self.assertFalse(self.run_function('gem.list', [GEM]))

    def test_install_version(self):
        '''
        gem.install rake version=11.1.2
        '''
        # Remove gem if it is already installed
        if self.run_function('gem.list', [GEM]):
            self.run_function('gem.uninstall', [GEM])

        self.run_function('gem.install', [GEM], version=GEM_VER)
        gem_list = self.run_function('gem.list', [GEM])
        self.assertIn(GEM, gem_list)
        self.assertIn(GEM_VER, gem_list[GEM])

        self.run_function('gem.uninstall', [GEM])
        self.assertFalse(self.run_function('gem.list', [GEM]))

    def test_list(self):
        '''
        gem.list
        '''
        self.run_function('gem.install', [' '.join(GEM_LIST)])

        all_ret = self.run_function('gem.list')
        for gem in GEM_LIST:
            self.assertIn(gem, all_ret)

        single_ret = self.run_function('gem.list', [GEM])
        self.assertIn(GEM, single_ret)

        self.run_function('gem.uninstall', [' '.join(GEM_LIST)])

    def test_list_upgrades(self):
        '''
        gem.list_upgrades
        '''
        # install outdated gem
        self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)

        ret = self.run_function('gem.list_upgrades')
        self.assertIn(OLD_GEM, ret)

        self.run_function('gem.uninstall', [OLD_GEM])

    def test_sources_add_remove(self):
        '''
        gem.sources_add
        gem.sources_remove
        '''
        source = 'http://gems.github.com'

        self.run_function('gem.sources_add', [source])
        sources_list = self.run_function('gem.sources_list')
        self.assertIn(source, sources_list)

        self.run_function('gem.sources_remove', [source])
        sources_list = self.run_function('gem.sources_list')
        self.assertNotIn(source, sources_list)

    def test_update(self):
        '''
        gem.update
        '''
        # Remove gem if it is already installed
        if self.run_function('gem.list', [OLD_GEM]):
            self.run_function('gem.uninstall', [OLD_GEM])

        self.run_function('gem.install', [OLD_GEM], version=OLD_VERSION)
        gem_list = self.run_function('gem.list', [OLD_GEM])
        self.assertEqual({'thor': ['0.17.0']}, gem_list)

        self.run_function('gem.update', [OLD_GEM])
        gem_list = self.run_function('gem.list', [OLD_GEM])
        self.assertEqual({'thor': ['0.19.4', '0.17.0']}, gem_list)

        self.run_function('gem.uninstall', [OLD_GEM])
        self.assertFalse(self.run_function('gem.list', [OLD_GEM]))

    def test_udpate_system(self):
        '''
        gem.udpate_system
        '''
        ret = self.run_function('gem.update_system')
        self.assertTrue(ret)
