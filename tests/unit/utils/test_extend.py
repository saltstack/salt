# -*- coding: utf-8 -*-
"""
    tests.unit.utils.extend_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt extend script, leave templates/test alone to keep this working!
"""
from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil
from datetime import date

import salt.utils.extend
import salt.utils.files
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf


class ExtendTestCase(TestCase):
    def setUp(self):
        self.out = None

    def tearDown(self):
        if self.out is not None:
            if os.path.exists(self.out):
                shutil.rmtree(self.out, True)

    @skipIf(
        not os.path.exists(os.path.join(RUNTIME_VARS.CODE_DIR, "templates")),
        "Test template directory 'templates/' missing.",
    )
    def test_run(self):
        with patch("sys.exit", MagicMock):
            out = salt.utils.extend.run(
                "test", "test", "this description", RUNTIME_VARS.CODE_DIR, False
            )
            self.out = out
            year = date.today().strftime("%Y")
            self.assertTrue(os.path.exists(out))
            self.assertFalse(os.path.exists(os.path.join(out, "template.yml")))
            self.assertTrue(os.path.exists(os.path.join(out, "directory")))
            self.assertTrue(os.path.exists(os.path.join(out, "directory", "test.py")))
            with salt.utils.files.fopen(
                os.path.join(out, "directory", "test.py"), "r"
            ) as test_f:
                self.assertEqual(test_f.read(), year)
