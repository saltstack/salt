# -*- coding: utf-8 -*-
'''
Integration tests for Ruby Gem module
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import salt libs
import salt.utils.path

# Import 3rd-party libs
import pytest
from salt.ext.tornado.httpclient import HTTPClient


def check_status():
    '''
    Check the status of the rubygems source
    '''
    try:
        return HTTPClient().fetch('https://rubygems.org').code == 200
    except Exception:  # pylint: disable=broad-except
        return False


@pytest.mark.destructive_test
@skipIf(not salt.utils.path.which('gem'), 'Gem is not available')
@pytest.mark.windows_whitelisted
class GemModuleTest(ModuleCase):
    '''
    Validate gem module
    '''

    def setUp(self):
        if check_status() is False:
            self.skipTest('External resource \'https://rubygems.org\' is not available')

        self.GEM = 'tidy'
        self.GEM_VER = '1.1.2'
        self.OLD_GEM = 'brass'
        self.OLD_VERSION = '1.0.0'
        self.NEW_VERSION = '1.2.1'
        self.GEM_LIST = [self.GEM, self.OLD_GEM]
        for name in ('GEM', 'GEM_VER', 'OLD_GEM', 'OLD_VERSION', 'NEW_VERSION', 'GEM_LIST'):
            self.addCleanup(delattr, self, name)

        def uninstall_gem():
            # Remove gem if it is already installed
            if self.run_function('gem.list', [self.GEM]):
                self.run_function('gem.uninstall', [self.GEM])

        self.addCleanup(uninstall_gem)

    def test_install_uninstall(self):
        '''
        gem.install
        gem.uninstall
        '''
        self.run_function('gem.install', [self.GEM])
        gem_list = self.run_function('gem.list', [self.GEM])
        assert self.GEM in gem_list

        self.run_function('gem.uninstall', [self.GEM])
        assert not self.run_function('gem.list', [self.GEM])

    def test_install_version(self):
        '''
        gem.install rake version=11.1.2
        '''
        self.run_function('gem.install', [self.GEM], version=self.GEM_VER)
        gem_list = self.run_function('gem.list', [self.GEM])
        assert self.GEM in gem_list
        assert self.GEM_VER in gem_list[self.GEM]

        self.run_function('gem.uninstall', [self.GEM])
        assert not self.run_function('gem.list', [self.GEM])

    def test_list(self):
        '''
        gem.list
        '''
        self.run_function('gem.install', [' '.join(self.GEM_LIST)])

        all_ret = self.run_function('gem.list')
        for gem in self.GEM_LIST:
            assert gem in all_ret

        single_ret = self.run_function('gem.list', [self.GEM])
        assert self.GEM in single_ret

        self.run_function('gem.uninstall', [' '.join(self.GEM_LIST)])

    def test_list_upgrades(self):
        '''
        gem.list_upgrades
        '''
        # install outdated gem
        self.run_function('gem.install', [self.OLD_GEM], version=self.OLD_VERSION)

        ret = self.run_function('gem.list_upgrades')
        assert self.OLD_GEM in ret

        self.run_function('gem.uninstall', [self.OLD_GEM])

    def test_sources_add_remove(self):
        '''
        gem.sources_add
        gem.sources_remove
        '''
        source = 'http://production.cf.rubygems.org'

        self.run_function('gem.sources_add', [source])
        sources_list = self.run_function('gem.sources_list')
        assert source in sources_list

        self.run_function('gem.sources_remove', [source])
        sources_list = self.run_function('gem.sources_list')
        assert source not in sources_list

    def test_update(self):
        '''
        gem.update
        '''
        self.run_function('gem.install', [self.OLD_GEM], version=self.OLD_VERSION)
        gem_list = self.run_function('gem.list', [self.OLD_GEM])
        assert {self.OLD_GEM: [self.OLD_VERSION]} == gem_list

        self.run_function('gem.update', [self.OLD_GEM])
        gem_list = self.run_function('gem.list', [self.OLD_GEM])
        assert {self.OLD_GEM: [self.NEW_VERSION, self.OLD_VERSION]} == gem_list

        self.run_function('gem.uninstall', [self.OLD_GEM])
        assert not self.run_function('gem.list', [self.OLD_GEM])

    def test_update_system(self):
        '''
        gem.update_system
        '''
        ret = self.run_function('gem.update_system')
        assert ret
