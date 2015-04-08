# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Pyatkin <asp@thexyz.net`
'''
# Import Python libs
from __future__ import absolute_import
import json

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


@skipIf(salt.utils.which('bower') is None, 'bower not installed')
class BowerStateTest(integration.ModuleCase,
                     integration.SaltReturnAssertsMixIn):

    @destructiveTest
    def test_bower_installed_removed(self):
        '''
        Basic test to determine if Bower package was successfully installed and
        removed.
        '''
        ret = self.run_state('file.directory', name='/salt_test_bower_1',
                             makedirs=True)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('bower.installed', name='underscore',
                             dir='/salt_test_bower_1')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('bower.removed', name='underscore',
                             dir='/salt_test_bower_1')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('file.absent', name='/salt_test_bower_1')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    def test_bower_installed_pkgs(self):
        '''
        Basic test to determine if Bower package successfully installs multiple
        packages.
        '''
        ret = self.run_state('file.directory', name='/salt_test_bower_2',
                             makedirs=True)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('bower.installed', name='test',
                             dir='/salt_test_bower_2',
                             pkgs=['numeral', 'underscore'])
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('file.absent', name='/salt_test_bower_2')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    def test_bower_installed_from_file(self):
        ret = self.run_state('file.directory', name='/salt_test_bower_3',
                             makedirs=True)
        self.assertSaltTrueReturn(ret)
        bower_json = json.dumps({
            'name': 'salt_test_bower_3',
            'dependencies': {
                'numeral': '~1.5.3',
                'underscore': '~1.7.0'
            }
        })
        ret = self.run_state('file.managed',
                             name='/salt_test_bower_3/bower.json',
                             contents=bower_json)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('bower.bootstrap', name='/salt_test_bower_3')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('file.absent', name='/salt_test_bower_3')
        self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BowerStateTest)
