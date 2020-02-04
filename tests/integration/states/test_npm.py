# -*- coding: utf-8 -*-
'''
    :codeauthor: Erik Johnson (erik@saltstack.com)
    tests.integration.states.npm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, requires_network
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.utils.path
import salt.utils.platform
from salt.utils.versions import LooseVersion

MAX_NPM_VERSION = '5.0.0'


@skipIf(salt.utils.path.which('npm') is None, 'npm not installed')
class NpmStateTest(ModuleCase, SaltReturnAssertsMixin):

    @requires_network()
    @destructiveTest
    def test_npm_installed_removed(self):
        '''
        Basic test to determine if NPM module was successfully installed and
        removed.
        '''
        ret = self.run_state('npm.installed', name='pm2@2.10.4', registry="http://registry.npmjs.org/")
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('npm.removed', name='pm2')
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_darwin(), 'TODO this test hangs on mac.')
    @requires_network()
    @destructiveTest
    def test_npm_install_url_referenced_package(self):
        '''
        Determine if URL-referenced NPM module can be successfully installed.
        '''
        npm_version = self.run_function('cmd.run', ['npm -v'])
        if LooseVersion(npm_version) >= LooseVersion(MAX_NPM_VERSION):
            user = os.environ.get('SUDO_USER', 'root')
            npm_dir = os.path.join(RUNTIME_VARS.TMP, 'git-install-npm')
            self.run_state('file.directory', name=npm_dir, user=user, dir_mode='755')
        else:
            user = None
            npm_dir = None
        ret = self.run_state('npm.installed',
                             name='request/request#v2.81.1',
                             runas=user,
                             dir=npm_dir,
                             registry="http://registry.npmjs.org/")
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('npm.removed', name='git://github.com/request/request', runas=user, dir=npm_dir)
        self.assertSaltTrueReturn(ret)
        if npm_dir is not None:
            self.run_state('file.absent', name=npm_dir)

    @requires_network()
    @destructiveTest
    def test_npm_installed_pkgs(self):
        '''
        Basic test to determine if NPM module successfully installs multiple
        packages.
        '''
        ret = self.run_state('npm.installed', name='unused', pkgs=['pm2@2.10.4', 'grunt@1.0.2'], registry="http://registry.npmjs.org/")
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    def test_npm_cache_clean(self):
        '''
        Basic test to determine if NPM successfully cleans its cached packages.
        '''
        npm_version = self.run_function('cmd.run', ['npm -v'])
        if LooseVersion(npm_version) >= LooseVersion(MAX_NPM_VERSION):
            self.skipTest('Skip with npm >= 5.0.0 until #41770 is fixed')
        ret = self.run_state('npm.cache_cleaned', name='unused', force=True)
        self.assertSaltTrueReturn(ret)
