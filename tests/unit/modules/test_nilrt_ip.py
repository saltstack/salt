# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.nilrt_ip as nilrt_ip

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class NilrtIPTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.nilrt_ip module
    """

    def setup_loader_modules(self):
        return {nilrt_ip: {"__grains__": {"lsb_distrib_id": "not_nilrt"}}}

    def test_change_state_down_state(self):
        """
        Tests _change_state when not connected
        and new state is down
        """
        with patch("salt.modules.nilrt_ip._interface_to_service", return_value=True):
            with patch("salt.modules.nilrt_ip._connected", return_value=False):
                assert nilrt_ip._change_state("test_interface", "down")

    def test_change_state_up_state(self):
        """
        Tests _change_state when connected
        and new state is up
        """
        with patch("salt.modules.nilrt_ip._interface_to_service", return_value=True):
            with patch("salt.modules.nilrt_ip._connected", return_value=True):
                assert nilrt_ip._change_state("test_interface", "up")
