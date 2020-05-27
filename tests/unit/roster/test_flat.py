# -*- coding: utf-8 -*-
"""
unit tests for flat roster
"""
from __future__ import absolute_import

import os

import salt.loader
import salt.roster.flat as flat
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class FlatTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for flat roster
    """

    def setup_loader_modules(self):
        self.opts = salt.config.master_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
        )
        utils = salt.loader.utils(self.opts, whitelist=["roster_matcher"])
        return {flat: {"__utils__": utils, "__opts__": self.opts}}

    def test_targets(self):
        roster = {"foo": {"host": "example.org"}}

        mock_salt_config = MagicMock()
        with patch(
            "salt.roster.flat.get_roster_file", MagicMock(return_value="")
        ), patch("salt.loader.render", MagicMock(),), patch(
            "salt.config", mock_salt_config
        ), patch(
            "salt.config.apply_sdb", MagicMock(return_value=roster["foo"])
        ), patch(
            "salt.roster.flat.compile_template", MagicMock(return_value=roster)
        ):

            ret = flat.targets("foo")

            mock_salt_config.apply_sdb.assert_any_call(self.opts, roster["foo"])

            self.assertTrue("foo" in ret)
            self.assertTrue("host" in ret["foo"])
            self.assertTrue(ret["foo"]["host"] == "example.org")
