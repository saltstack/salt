# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import re

# Import Salt Testing libs
import tests.integration as integration


class KeyModuleTest(integration.ModuleCase):
    def test_key_finger(self):
        '''
        test key.finger to ensure we receive a valid fingerprint
        '''
        out = self.run_function('key.finger')
        match = re.match("([0-9a-z]{2}:){15,}[0-9a-z]{2}$", out)
        self.assertTrue(match)

    def test_key_finger_master(self):
        '''
        test key.finger_master to ensure we receive a valid fingerprint
        '''
        out = self.run_function('key.finger_master')
        match = re.match("([0-9a-z]{2}:){15,}[0-9a-z]{2}$", out)
        self.assertTrue(match)
