# -*- coding: utf-8 -*-
'''
integration tests for mac_service
'''

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class MacServiceModuleTest(integration.ModuleCase):
    '''
    Validate the mac_service module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('launchctl'):
            self.skipTest('Test requires launchctl binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

    def tearDown(self):
        '''
        Reset to original settings
        '''
        pass


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacServiceModuleTest)

