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
from tests.support.mixins import SaltReturnAssertsMixin


class CpanStateTest(ModuleCase, SaltReturnAssertsMixin):
    def test_cpan_installed_removed(self):
        '''
        Tests installed and removed states
        '''
        # Verify that cpan is installed
        ret = self.run_state('pkg.installed', name='cpan')
        self.assertSaltTrueReturn(ret)

        name = 'Template::Alloy'
        version = self.run_function('cpan.show', (name,))['installed version']
        if version and ("not installed" not in version):
            # For now this is not implemented as state because it is experimental/non-stable
            # self.run_state('cpan.removed', name=name)
            self.run_function('cpan.remove', (name,))

        ret = self.run_state('cpan.installed', name=name)
        self.assertSaltTrueReturn(ret)

        # For now this is not implemented as state because it is experimental/non-stable
        # self.run_state('cpan.removed', name=name)
        self.run_function('cpan.remove', module=(name,))

    def test_missing_cpan(self):
        """
        Test cpan not being installed on the system
        """
        module = "Nonexistant::Module"
        # Use the name of a binary that doesn't exist
        bin_env = "no_cpan"
        ret = self.run_state('cpan.installed', name=module, bin_env=bin_env)
        self.assertSaltFalseReturn(ret)
        self.assertInSaltComment(
            'Unable to locate `{}` binary, Make sure it is installed and in the PATH'.format(
                bin_env), ret
        )
