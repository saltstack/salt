# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import os

import pytest

# Import module
import salt.modules.baredoc as baredoc
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS

# Import Salt Testing Libs
from tests.support.unit import TestCase


class BaredocTest(TestCase, LoaderModuleMockMixin):
    """
    Validate baredoc module
    """

    def setup_loader_modules(self):
        return {
            baredoc: {
                "__opts__": {
                    "extension_modules": os.path.join(RUNTIME_VARS.CODE_DIR, "salt"),
                },
                "__grains__": {"saltpath": os.path.join(RUNTIME_VARS.CODE_DIR, "salt")},
            }
        }

    @pytest.mark.slow_test(seconds=5)  # Test takes >1 and <=5 seconds
    def test_baredoc_list_states(self):
        """
        Test baredoc state module listing
        """
        ret = baredoc.list_states(names_only=True)
        assert "value_present" in ret["xml"][0]

    @pytest.mark.slow_test(seconds=5)  # Test takes >1 and <=5 seconds
    def test_baredoc_list_states_args(self):
        """
        Test baredoc state listing with args
        """
        ret = baredoc.list_states()
        assert "value_present" in ret["xml"][0]
        assert "xpath" in ret["xml"][0]["value_present"]

    def test_baredoc_list_states_single(self):
        """
        Test baredoc state listing single state module
        """
        ret = baredoc.list_states("xml")
        assert "value_present" in ret["xml"][0]
        assert "xpath" in ret["xml"][0]["value_present"]

    @pytest.mark.slow_test(seconds=10)  # Test takes >5 and <=10 seconds
    def test_baredoc_list_modules(self):
        """
        test baredoc executiion module listing
        """
        ret = baredoc.list_modules(names_only=True)
        assert "get_value" in ret["xml"][0]

    @pytest.mark.slow_test(seconds=10)  # Test takes >5 and <=10 seconds
    def test_baredoc_list_modules_args(self):
        """
        test baredoc execution module listing with args
        """
        ret = baredoc.list_modules()
        assert "get_value" in ret["xml"][0]
        assert "file" in ret["xml"][0]["get_value"]

    def test_baredoc_list_modules_single_and_alias(self):
        """
        test baredoc single module listing
        """
        ret = baredoc.list_modules("mdata")
        assert "put" in ret["mdata"][2]
        assert "keyname" in ret["mdata"][2]["put"]
