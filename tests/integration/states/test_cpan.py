# -*- coding: utf-8 -*-
'''
    :codeauthor: Tyler Johnson (tjohnson@saltstack.com)


    tests.integration.states.cpan
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.path

log = logging.getLogger(__name__)

__testcontext__ = {}


class CpanStateTest(ModuleCase, SaltReturnAssertsMixin):
    def setUp(self):
        '''
        Ensure that cpan is installed through perl
        '''
        super(CpanStateTest, self).setUp()
        if 'cpan' not in __testcontext__:
            if __grains__['os'] == 'CentOS':
                self.run_state('pkg.installed', name='perl-doc')
                if __grains__['osrelease'] == '7':
                    self.run_state('pkg.installed', name='perl-cpan')
                elif __grains__['osrelease'] == '6':
                    self.run_state('pkg.installed', name='perl-CPAN')
            elif __grains__['os_family'] in ('Debian', 'Arch'):
                # It is part of the perl package for these distrobutionss
                self.run_state('pkg.installed', name='perl')
            else:
                self.run_state('pkg.installed', name='cpan')
            self.assertTrue(salt.utils.path.which('cpan').endswith('cpan'), "cpan not installed")
            __testcontext__['cpan'] = True

    @destructiveTest
    def test_cpan_installed_removed(self):
        '''
        Tests installed and removed states
        '''
        name = 'File::Temp'
        ret = self.run_function('cpan.show', (name,))
        version = ret.get('installed version', None)
        if version and ("not installed" not in version):
            # For now this is not implemented as state because it is experimental/non-stable
            self.run_function('cpan.remove', (name,))

        ret = self.run_state('cpan.installed', name=name)
        self.assertSaltTrueReturn(ret)

        # For now this is not implemented as state because it is experimental/non-stable
        self.run_function('cpan.remove', module=(name,))

    def test_missing_cpan(self):
        '''
        Test cpan not being installed on the system
        '''
        module = "Nonexistant::Module"
        # Use the name of a binary that doesn't exist
        bin_env = "no_cpan"
        ret = self.run_state('cpan.installed', name=module, bin_env=bin_env)
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            'Unable to locate `{}` binary, Make sure it is installed and in the PATH'.format(
                bin_env), ret
        )
