# -*- coding: utf-8 -*-
'''
integration tests for mac_xattr
'''

# Import python libs
from __future__ import absolute_import
import sys

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class MacXattrModuleTest(integration.ModuleCase):
    '''
    Validate the mac_xattr module
    '''

    def create_test_file(self):
        ret = self.run_function('file.touch', ['tmp/test.txt'])
        if not ret:
            self.skipTest('test file not created')



