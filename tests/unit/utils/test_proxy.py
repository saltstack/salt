# -*- coding: utf-8 -*-
"""
    Unit tests for salt.utils.proxy
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.proxy
from tests.support.mock import patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class ProxyUtilsTestCase(TestCase):
    def test_is_proxytype(self):
        opts = {
            "proxy": {
                "proxytype": "esxi",
                "host": "esxi.domain.com",
                "username": "username",
                "passwords": ["password1"],
            }
        }

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            ret = salt.utils.proxy.is_proxytype(opts, "esxi")
            self.assertTrue(ret)
