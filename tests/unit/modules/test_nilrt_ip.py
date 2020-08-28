import salt.modules.nilrt_ip as nilrt_ip
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import pyiface
except ImportError:
    pyiface = None


@skipIf(not pyiface, "The python pyiface package is not installed")
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
        iface_mock = MagicMock()
        iface_mock.name = "test_interface"
        with patch("pyiface.getIfaces", return_value=[iface_mock]):
            with patch(
                "salt.modules.nilrt_ip._change_dhcp_config", return_value=True
            ) as change_dhcp_config_mock:
                assert nilrt_ip._change_state("test_interface", "down")
                assert change_dhcp_config_mock.called_with("test_interface", False)

    def test_change_state_up_state(self):
        """
        Tests _change_state when connected
        and new state is up
        """
        iface_mock = MagicMock()
        iface_mock.name = "test_interface"
        with patch("pyiface.getIfaces", return_value=[iface_mock]):
            with patch(
                "salt.modules.nilrt_ip._change_dhcp_config", return_value=True
            ) as change_dhcp_config_mock:
                assert nilrt_ip._change_state("test_interface", "up")
                assert change_dhcp_config_mock.called_with("test_interface")
