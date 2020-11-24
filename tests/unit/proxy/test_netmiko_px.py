"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import logging

import salt.config
import salt.proxy.netmiko_px as netmiko_proxy
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MockNetmikoConnection:
    def is_alive(self):
        return False

    def send_config_set(self, *args, **kwargs):
        return args, kwargs


class NetmikoProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {netmiko_proxy: {}}

    def test_check_virtual(self):

        """ check netmiko_proxy virtual method - return value """

        with patch.object(netmiko_proxy, "HAS_NETMIKO", True):
            result = netmiko_proxy.__virtual__()
            self.assertIn("netmiko", result)

        expected = (
            False,
            "The netmiko proxy module requires netmiko library to be installed.",
        )
        with patch.object(netmiko_proxy, "HAS_NETMIKO", False):
            result = netmiko_proxy.__virtual__()
            self.assertEqual(expected, result)

    def test_init_skip_connect_on_init_true(self):

        """ check netmiko_proxy init method """

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True

        result = netmiko_proxy.init(opts)
        self.assertIn("netmiko_device", netmiko_proxy.__context__)
        self.assertIn("args", netmiko_proxy.__context__["netmiko_device"])

        self.assertIn("initialized", netmiko_proxy.__context__["netmiko_device"])
        self.assertFalse(netmiko_proxy.__context__["netmiko_device"]["initialized"])

        self.assertIn("up", netmiko_proxy.__context__["netmiko_device"])
        self.assertTrue(netmiko_proxy.__context__["netmiko_device"]["up"])

        self.assertIn("always_alive", netmiko_proxy.__context__["netmiko_device"])

        self.assertNotIn("conneciton", netmiko_proxy.__context__["netmiko_device"])

    def test_init_skip_connect_on_init_false(self):

        """ check netmiko_proxy init method """

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = False

        mock_make_con = MagicMock()
        with patch.object(netmiko_proxy, "make_con", mock_make_con):
            result = netmiko_proxy.init(opts)

        self.assertIn("netmiko_device", netmiko_proxy.__context__)
        self.assertIn("args", netmiko_proxy.__context__["netmiko_device"])

        self.assertIn("initialized", netmiko_proxy.__context__["netmiko_device"])
        self.assertTrue(netmiko_proxy.__context__["netmiko_device"]["initialized"])

        self.assertIn("up", netmiko_proxy.__context__["netmiko_device"])
        self.assertTrue(netmiko_proxy.__context__["netmiko_device"]["up"])

        self.assertIn("always_alive", netmiko_proxy.__context__["netmiko_device"])

        self.assertNotIn("conneciton", netmiko_proxy.__context__["netmiko_device"])

    def test_make_con(self):

        """ check netmiko_proxy make_con method """

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True

        netmiko_proxy.init(opts)

        mock_connection = MockNetmikoConnection

        with patch.object(
            netmiko_proxy, "ConnectHandler", mock_connection, create=True
        ):
            result = netmiko_proxy.make_con()
            self.assertNotEqual(result, None)

    def test_make_con_raise_exception(self):

        """ check netmiko_proxy make_con method """

        def raise_exception(*arg, **kwarg):
            raise Exception("expected")

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True

        netmiko_proxy.init(opts)

        mock_connection = MockNetmikoConnection

        with patch.object(netmiko_proxy, "DEFAULT_CONNECTION_TIMEOUT", 0), patch.object(
            netmiko_proxy, "ConnectHandler", raise_exception, create=True
        ):
            result = None
            try:
                result = netmiko_proxy.make_con(0)
            except Exception:  # pylint: disable=broad-except
                self.assertEqual(result, None)

    def test_ping(self):

        """ check netmiko_proxy ping method """

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True

        netmiko_proxy.init(opts)

        result = netmiko_proxy.ping()
        self.assertEqual(result, True)

    def test_alive(self):

        """ check netmiko_proxy alive method """

        # Always alive False with skip_connect_on_init on True
        # should return alive as True
        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True
        opts["proxy_always_alive"] = False

        netmiko_proxy.init(opts)

        result = netmiko_proxy.alive(opts)
        self.assertTrue(result)

        # Always alive True with skip_connect_on_init on True
        # should return alive as False
        opts["proxy_always_alive"] = True

        netmiko_proxy.init(opts)

        result = netmiko_proxy.alive(opts)
        self.assertFalse(result)

        # Always alive True with skip_connect_on_init on False
        # should return alive as True
        opts["skip_connect_on_init"] = False
        opts["proxy_always_alive"] = True

        mock_make_con = MagicMock()
        with patch.object(netmiko_proxy, "make_con", mock_make_con):
            netmiko_proxy.init(opts)
            result = netmiko_proxy.alive(opts)
            self.assertTrue(result)

    def test_initialized(self):

        """ check netmiko_proxy alive method """

        opts = salt.config.proxy_config(
            RUNTIME_VARS.TMP_PROXY_CONF_DIR + "/proxy", minion_id="proxytest"
        )
        opts["skip_connect_on_init"] = True

        netmiko_proxy.init(opts)

        result = netmiko_proxy.initialized()
        self.assertFalse(result)

        # Always alive True with skip_connect_on_init on False
        # should return alive as True
        opts["skip_connect_on_init"] = False

        mock_make_con = MagicMock()
        with patch.object(netmiko_proxy, "make_con", mock_make_con):
            netmiko_proxy.init(opts)
            result = netmiko_proxy.initialized()
            self.assertTrue(result)
