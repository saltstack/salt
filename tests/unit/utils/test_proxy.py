"""
    Unit tests for salt.utils.proxy
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
"""


import salt.utils.proxy
from tests.support.mock import patch
from tests.support.unit import TestCase


class ProxyUtilsTestCase(TestCase):
    def test_is_proxytype_true(self):
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

    def test_is_proxytype_false(self):
        opts = {
            "proxy": {
                "proxytype": "esxi",
                "host": "esxi.domain.com",
                "username": "username",
                "passwords": ["password1"],
            }
        }

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            ret = salt.utils.proxy.is_proxytype(opts, "docker")
            self.assertFalse(ret)

    def test_is_proxytype_not_proxy(self):
        opts = {}

        with patch("salt.utils.platform.is_proxy", return_value=False, autospec=True):
            ret = salt.utils.proxy.is_proxytype(opts, "docker")
            self.assertFalse(ret)
