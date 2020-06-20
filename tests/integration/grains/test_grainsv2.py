# -*- coding: utf-8 -*-
"""
Test grainsv2
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import pytest

# Import salt libs
import salt.config
import salt.loader
import salt.utils.platform

# Import salt testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import requires_system_grains
from tests.support.mixins import LoaderModuleMockMixin


@pytest.mark.windows_whitelisted
class TestGrainsv2(ModuleCase, LoaderModuleMockMixin):
    """
    Compare grains from idem with grains from salt
    """

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.opts["enable_grainsv2"] = False
        return {salt.loader: {"__opts__": opts}}

    @classmethod
    def setUpClass(cls):
        cls.hub = salt.loader.create_hub()
        cls.grainsv2 = salt.loader.grainsv2(hub=cls.hub)

    @classmethod
    def tearDownClass(cls):
        del cls.grainsv2
        del cls.hub

    @requires_system_grains
    def test_keys(self, grains):
        """
        Test that all the grains from salt are now available in grainsv2
        """
        missing_keys = set(grains.keys()) - set(self.grainsv2.keys())
        assert not missing_keys, "Grainsv2 is missing grains: {}".format(
            ", ".join(sorted(missing_keys))
        )

    def compare_values(self, v1, v2):
        if isinstance(v1, dict) and isinstance(v2, dict):
            keys = set(v1.keys())
            keys.update(set(v2.keys()))
            for key in keys:
                with self.subTest(key=key):
                    self.compare_values(v1.get(key), v2.get(key))
            return
        # Loosely match grain values by casting iterables as sets
        if isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            try:
                v1 = set(v1)
                v2 = set(v2)
            except TypeError:
                pass
        try:
            self.assertEqual(v1, v2)
        except AssertionError as e:
            self.skipTest(reason=e)

    @requires_system_grains
    def test_values(self, grains):
        """
        Test that all the grains from salt have generally the same value as in grainsv2
        Warn for each one that is different but do not fail
        """
        for grain in sorted(grains.keys()):
            with self.subTest(grain=grain):
                self.compare_values(grains[grain], self.grainsv2.get(grain))
