# pylint: disable=W0223,W0231,W0221
import logging

import salt.modules.netmiko_mod as netmiko_mod
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MockNetmikoConnection:
    def __init__(self, *args, **kwargs):
        self.user = kwargs["username"]
        self.password = kwargs["password"]

    def is_alive(self):
        return False

    def send_config_set(self, *args, **kwargs):
        return args, kwargs


def mock_netmiko_args():
    return {"username": "salt", "password": "password"}


def mock_netmiko_conn():
    return MockNetmikoConnection(**mock_netmiko_args())


def mock_file_apply_template_on_contents(*args):
    return args[0]


def mock_prepare_connection(**kwargs):
    return MockNetmikoConnection(**kwargs), {}


class NetmikoTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            netmiko_mod: {
                "__salt__": {
                    "file.apply_template_on_contents": mock_file_apply_template_on_contents,
                },
                "__proxy__": {
                    "netmiko.conn": mock_netmiko_conn,
                    "netmiko.args": mock_netmiko_args,
                },
                "_prepare_connection": mock_prepare_connection,
            }
        }

    def test_send_config(self):
        """
        Test netmiko.send_config function
        """
        _, ret = netmiko_mod.send_config(
            config_commands=["ls", "echo hello world"],
            config_mode_command="config config-sess",
        )
        self.assertEqual(ret.get("config_commands"), ["ls", "echo hello world"])
        self.assertEqual(ret.get("config_mode_command"), "config config-sess")

        with patch.dict(
            netmiko_mod.__proxy__, {"netmiko.conn": MagicMock(return_value=None)}
        ):
            _, ret = netmiko_mod.send_config(
                config_commands=["ls", "echo hello world"],
                config_mode_command="config config-sess",
            )
            self.assertEqual(ret.get("config_commands"), ["ls", "echo hello world"])
            self.assertEqual(ret.get("config_mode_command"), "config config-sess")

    def test_virtual(self):
        _expected = (
            False,
            "The netmiko execution module requires netmiko library to be installed.",
        )
        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(netmiko_mod.__opts__, {"proxy": {"proxytype": "netmiko"}}):
                with patch.object(netmiko_mod, "HAS_NETMIKO", False):
                    ret = netmiko_mod.__virtual__()
                    self.assertTrue(ret)

        _expected = (
            False,
            "The netmiko execution module requires netmiko library to be installed.",
        )
        with patch("salt.utils.platform.is_proxy", return_value=False, autospec=True):
            with patch.dict(netmiko_mod.__opts__, {"proxy": {"proxytype": "esxi"}}):
                with patch.object(netmiko_mod, "HAS_NETMIKO", False):
                    ret = netmiko_mod.__virtual__()
                    self.assertTrue(ret)

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(netmiko_mod.__opts__, {"proxy": {"proxytype": "netmiko"}}):
                with patch.object(netmiko_mod, "HAS_NETMIKO", True):
                    ret = netmiko_mod.__virtual__()
                    self.assertTrue(ret)
                    self.assertEqual(ret, "netmiko")

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(netmiko_mod.__opts__, {"proxy": {"proxytype": "esxi"}}):
                with patch.object(netmiko_mod, "HAS_NETMIKO", True):
                    ret = netmiko_mod.__virtual__()
                    self.assertTrue(ret)
                    self.assertEqual(ret, "netmiko")

        with patch("salt.utils.platform.is_proxy", return_value=False, autospec=True):
            with patch.object(netmiko_mod, "HAS_NETMIKO", True):
                ret = netmiko_mod.__virtual__()
                self.assertEqual(ret, "netmiko")

        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(netmiko_mod.__opts__, {"proxy": {"proxytype": "napalm"}}):
                with patch.object(netmiko_mod, "HAS_NETMIKO", True):
                    ret = netmiko_mod.__virtual__()
                    self.assertTrue(ret)
                    self.assertEqual(ret, "netmiko")

        _expected = (False, "Unsupported proxy minion type.")
        with patch("salt.utils.platform.is_proxy", return_value=True, autospec=True):
            with patch.dict(
                netmiko_mod.__opts__, {"proxy": {"proxytype": "deltaproxy"}}
            ):
                with patch.object(netmiko_mod, "HAS_NETMIKO", True):
                    ret = netmiko_mod.__virtual__()
                    self.assertEqual(ret, _expected)
