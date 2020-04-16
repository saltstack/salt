# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    integration.loader.ext_modules
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding external overrides
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import time

from tests.support.case import ModuleCase

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS


class LoaderOverridesTest(ModuleCase):
    def setUp(self):
        self.run_function("saltutil.sync_modules")

    def test_overridden_internal(self):
        # To avoid a race condition on Windows, we need to make sure the
        # `override_test.py` file is present in the _modules directory before
        # trying to list all functions. This test may execute before the
        # minion has finished syncing down the files it needs.
        module = os.path.join(
            RUNTIME_VARS.TMP,
            "rootdir",
            "cache",
            "files",
            "base",
            "_modules",
            "override_test.py",
        )
        tries = 0
        while not os.path.exists(module):
            tries += 1
            if tries > 60:
                break
            time.sleep(1)

        funcs = self.run_function("sys.list_functions")

        # We placed a test module under _modules.
        # The previous functions should also still exist.
        self.assertIn("test.ping", funcs)

        # A non existing function should, of course, not exist
        self.assertNotIn("brain.left_hemisphere", funcs)

        # There should be a new function for the test module, recho
        self.assertIn("test.recho", funcs)

        text = "foo bar baz quo qux"
        self.assertEqual(
            self.run_function("test.echo", arg=[text])[::-1],
            self.run_function("test.recho", arg=[text]),
        )
