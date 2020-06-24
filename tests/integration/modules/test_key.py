# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import re

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import slowTest


@pytest.mark.windows_whitelisted
class KeyModuleTest(ModuleCase):
    @slowTest
    def test_key_finger(self):
        """
        test key.finger to ensure we receive a valid fingerprint
        """
        out = self.run_function("key.finger")
        match = re.match("([0-9a-z]{2}:){15,}[0-9a-z]{2}$", out)
        self.assertTrue(match)

    @slowTest
    def test_key_finger_master(self):
        """
        test key.finger_master to ensure we receive a valid fingerprint
        """
        out = self.run_function("key.finger_master")
        match = re.match("([0-9a-z]{2}:){15,}[0-9a-z]{2}$", out)
        self.assertTrue(match)
