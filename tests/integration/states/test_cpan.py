# -*- coding: utf-8 -*-
'''
    :codeauthor: Tyler Johnson (tjohnson@saltstack.com)

    tests.integration.states.cpan
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, requires_system_grains
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils.path

__testcontext__ = {}


@destructiveTest
class CpanStateTest(ModuleCase, SaltReturnAssertsMixin):
    @requires_system_grains
    def setUp(self, grains=None):  # pylint: disable=arguments-differ
        '''
        Ensure that cpan is installed through perl
        '''
        super(CpanStateTest, self).setUp()
        if 'cpan' not in __testcontext__:
            # Install perl
            self.assertSaltTrueReturn(self.run_state('pkg.installed', name='perl'))
            # Install cpan or docs
            cpan_docs = 'cpan'
            if grains['os_family'] == 'RedHat':
                cpan_docs = 'perl-CPAN'
            elif grains['os_family'] == 'Arch':
                cpan_docs = 'perl-docs'
            elif grains['os_family'] == 'Debian':
                cpan_docs = 'perl-doc'
            self.assertSaltTrueReturn(self.run_state('pkg.installed', name=cpan_docs))
            # Verify that the cpan binary exists on the system
            self.assertTrue(str(salt.utils.path.which('cpan')).endswith('cpan'), "cpan not installed")
            __testcontext__['cpan'] = True

    def test_cpan_installed_removed(self):
        '''
        Tests installed and removed states
        '''
        name = 'File::Temp'
        ret = self.run_function('cpan.show', module=name)
        self.assertIsInstance(ret, dict, "Return value should be a dictionary, instead got: {}".format(ret))
        version = ret.get('installed version', None)
        if version and ("not installed" not in version):
            # For now this is not implemented as state because it is experimental/non-stable
            self.run_function('cpan.remove', (name,))

        ret = self.run_state('cpan.installed', name=name)
        self.assertSaltTrueReturn(ret)

        # For now this is not implemented as state because it is experimental/non-stable
        self.run_function('cpan.remove', module=name)

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
            'Make sure `{}` is installed and in the PATH'.format(bin_env), ret)
