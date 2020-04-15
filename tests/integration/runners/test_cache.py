# -*- coding: utf-8 -*-
"""
Tests for the salt-run command
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Testing libs
from tests.support.case import ShellCase

log = logging.getLogger(__name__)


class ManageTest(ShellCase):
    """
    Test the manage runner
    """

    def test_cache(self):
        """
        Store, list, fetch, then flush data
        """
        # Store the data
        ret = self.run_run_plus(
            "cache.store",
            bank="cachetest/runner",
            key="test_cache",
            data="The time has come the walrus said",
        )
        # Make sure we can see the new key
        ret = self.run_run_plus("cache.list", bank="cachetest/runner")
        self.assertIn("test_cache", ret["return"])
        # Make sure we can see the new data
        ret = self.run_run_plus(
            "cache.fetch", bank="cachetest/runner", key="test_cache"
        )
        self.assertIn("The time has come the walrus said", ret["return"])
        # Make sure we can delete the data
        ret = self.run_run_plus(
            "cache.flush", bank="cachetest/runner", key="test_cache"
        )
        ret = self.run_run_plus("cache.list", bank="cachetest/runner")
        self.assertNotIn("test_cache", ret["return"])

    def test_cache_invalid(self):
        """
        Store, list, fetch, then flush data
        """
        # Store the data
        ret = self.run_run_plus("cache.store",)
        # Make sure we can see the new key
        expected = "Passed invalid arguments:"
        self.assertIn(expected, ret["return"])

    def test_grains(self):
        """
        Test cache.grains
        """
        # Store the data
        ret = self.run_run_plus("cache.grains", tgt="minion")

        self.assertIn("minion", ret["return"])

    def test_pillar(self):
        """
        Test cache.pillar
        """
        # Store the data
        ret = self.run_run_plus("cache.pillar", tgt="minion")

        assert "minion" in ret["return"]
        assert "sub_minion" not in ret["return"]

    def test_pillar_no_tgt(self):
        """
        Test cache.pillar when no tgt is
        supplied. This should return pillar
        data for all minions
        """
        # Store the data
        ret = self.run_run_plus("cache.pillar",)

        assert all(x in ret["return"] for x in ["minion", "sub_minion"])

    def test_pillar_minion_noexist(self):
        """
        Test cache.pillar when the target does not exist
        """
        ret = self.run_run_plus("cache.pillar", tgt="doesnotexist")

        assert "minion" not in ret["return"]
        assert "sub_minion" not in ret["return"]

    def test_pillar_minion_tgt_type_pillar(self):
        """
        Test cache.pillar when the target exists
        and tgt_type is pillar
        """
        ret = self.run_run_plus("cache.pillar", tgt="monty:python", tgt_type="pillar",)

        assert all(x in ret["return"] for x in ["minion", "sub_minion"])

    def test_mine(self):
        """
        Test cache.mine
        """
        # Store the data
        ret = self.run_run_plus("cache.mine", tgt="minion")

        self.assertIn("minion", ret["return"])
