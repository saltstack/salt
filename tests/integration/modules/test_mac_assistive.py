# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

OSA_SCRIPT = '/usr/bin/osascript'


@destructiveTest
@skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
class MacAssistiveTest(integration.ModuleCase):
    '''
    Integration tests for the mac_assistive module.
    '''

    def setUp(self):
        '''
        Sets up test requirements
        '''
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Darwin':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

        # Let's install a bundle to use in tests
        self.run_function('assistive.install', [OSA_SCRIPT, True])

    def tearDown(self):
        '''
        Clean up after tests
        '''
        # Delete any bundles that were installed
        osa_script = self.run_function('assistive.installed', [OSA_SCRIPT])
        if osa_script:
            self.run_function('assistive.remove', [OSA_SCRIPT])

        smile_bundle = 'com.smileonmymac.textexpander'
        smile_bundle_present = self.run_function('assistive.installed', [smile_bundle])
        if smile_bundle_present:
            self.run_function('assistive.remove', [smile_bundle])

    def test_install_and_remove(self):
        '''
        Tests installing and removing a bundled ID or command to use assistive access.
        '''
        new_bundle = 'com.smileonmymac.textexpander'
        self.assertTrue(
            self.run_function('assistive.install', [new_bundle])
        )
        self.assertTrue(
            self.run_function('assistive.remove', [new_bundle])
        )

    def test_installed(self):
        '''
        Tests the True and False return of assistive.installed.
        '''
        # OSA script should have been installed in setUp function
        self.assertTrue(
            self.run_function('assistive.installed', [OSA_SCRIPT])
        )
        # Clean up install
        self.run_function('assistive.remove', [OSA_SCRIPT])
        # Installed should now return False
        self.assertFalse(
            self.run_function('assistive.installed', [OSA_SCRIPT])
        )

    def test_enable(self):
        '''
        Tests setting the enabled status of a bundled ID or command.
        '''
        # OSA script should have been installed and enabled in setUp function
        # Now let's disable it, which should return True.
        self.assertTrue(
            self.run_function('assistive.enable', [OSA_SCRIPT, False])
        )
        # Double check the script was disabled, as intended.
        self.assertFalse(
            self.run_function('assistive.enabled', [OSA_SCRIPT])
        )
        # Now re-enable
        self.assertTrue(
            self.run_function('assistive.enable', [OSA_SCRIPT])
        )
        # Double check the script was enabled, as intended.
        self.assertTrue(
            self.run_function('assistive.enabled', [OSA_SCRIPT])
        )

    def test_enabled(self):
        '''
        Tests if a bundled ID or command is listed in assistive access returns True.
        '''
        # OSA script should have been installed in setUp function, which sets
        # enabled to True by default.
        self.assertTrue(
            self.run_function('assistive.enabled', [OSA_SCRIPT])
        )
        # Disable OSA Script
        self.run_function('assistive.enable', [OSA_SCRIPT, False])
        # Assert against new disabled status
        self.assertFalse(
            self.run_function('assistive.enabled', [OSA_SCRIPT])
        )
