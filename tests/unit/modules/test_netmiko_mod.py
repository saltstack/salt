import salt.modules.netmiko_mod as netmiko_mod
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class MockNetmikoConnection:
    def is_alive(self):
        return False

    def send_config_set(self, *args, **kwargs):
        return args, kwargs


def mock_netmiko_args():
    return {"user": "salt", "password": "password"}


def mock_prepare_connection(**kwargs):
    return MockNetmikoConnection(), kwargs


def mock_file_apply_template_on_contents(*args):
    return args[0]


class NetmikoTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            netmiko_mod: {
                "__salt__": {
                    "file.apply_template_on_contents": mock_file_apply_template_on_contents
                },
                "__proxy__": {
                    "netmiko.conn": MockNetmikoConnection,
                    "netmiko.args": mock_netmiko_args,
                },
                "_prepare_connection": mock_prepare_connection,
            }
        }

    def test_send_config(self):
        """
        Test netmiko.send_config function
        """
        _, ret = netmiko_mod.send_config(config_commands=["ls", "echo hello world"])
        self.assertEqual(ret.get("config_commands"), ["ls", "echo hello world"])
        self.assertEqual(ret.get("user"), "salt")
        self.assertEqual(ret.get("password"), "password")
