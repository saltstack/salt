# -*- coding: utf-8 -*-
"""
    integration.loader.ext_grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding external grains
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import time

# Import salt libs
import salt.config
import salt.loader
from tests.support.case import ModuleCase

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


class LoaderGrainsTest(ModuleCase):
    """
    Test the loader standard behavior with external grains
    """

    # def setUp(self):
    #    self.opts = minion_config(None)
    #    self.opts['disable_modules'] = ['pillar']
    #    self.opts['grains'] = grains(self.opts)

    def test_grains_overwrite(self):
        # Force a grains sync
        self.run_function("saltutil.sync_grains")
        # To avoid a race condition on Windows, we need to make sure the
        # `test_custom_grain2.py` file is present in the _grains directory
        # before trying to get the grains. This test may execute before the
        # minion has finished syncing down the files it needs.
        module = os.path.join(
            RUNTIME_VARS.TMP,
            "rootdir",
            "cache",
            "files",
            "base",
            "_grains",
            "test_custom_grain2.py",
        )
        tries = 0
        while not os.path.exists(module):
            tries += 1
            if tries > 60:
                break
            time.sleep(1)
        grains = self.run_function("grains.items")

        # Check that custom grains are overwritten
        self.assertEqual({"k2": "v2"}, grains["a_custom"])


@skipIf(True, "needs a way to reload minion after config change")
class LoaderGrainsMergeTest(ModuleCase):
    """
    Test the loader deep merge behavior with external grains
    """

    def setUp(self):
        # XXX: This seems like it should become a unit test instead
        self.opts = salt.config.minion_config(None)
        self.opts["grains_deep_merge"] = True
        self.assertTrue(self.opts["grains_deep_merge"])
        self.opts["disable_modules"] = ["pillar"]
        __grains__ = salt.loader.grains(self.opts)

    def test_grains_merge(self):
        __grain__ = self.run_function("grains.item", ["a_custom"])

        # Check that the grain is present
        self.assertIn("a_custom", __grain__)
        # Check that the grains are merged
        self.assertEqual({"k1": "v1", "k2": "v2"}, __grain__["a_custom"])
