# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class DataModuleTest(ModuleCase):
    """
    Validate the data module
    """

    def setUp(self):
        self.run_function("data.clear")
        self.addCleanup(self.run_function, "data.clear")

    @skipIf(True, "SLOWTEST skip")
    def test_load_dump(self):
        """
        data.load
        data.dump
        """
        self.assertTrue(self.run_function("data.dump", ['{"foo": "bar"}']))
        self.assertEqual(self.run_function("data.load"), {"foo": "bar"})

    @skipIf(True, "SLOWTEST skip")
    def test_get_update(self):
        """
        data.get
        data.update
        """
        self.assertTrue(self.run_function("data.update", ["spam", "eggs"]))
        self.assertEqual(self.run_function("data.get", ["spam"]), "eggs")

        self.assertTrue(self.run_function("data.update", ["unladen", "swallow"]))
        self.assertEqual(
            self.run_function("data.get", [["spam", "unladen"]]), ["eggs", "swallow"]
        )

    @skipIf(True, "SLOWTEST skip")
    def test_cas_update(self):
        """
        data.update
        data.cas
        data.get
        """
        self.assertTrue(self.run_function("data.update", ["spam", "eggs"]))
        self.assertTrue(self.run_function("data.cas", ["spam", "green", "eggs"]))
        self.assertEqual(self.run_function("data.get", ["spam"]), "green")
