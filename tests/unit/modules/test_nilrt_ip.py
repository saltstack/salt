import salt.modules.nilrt_ip as nilrt_ip
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock, patch
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

    def test_set_static_all_with_dns(self):
        """
        Tests set_static_all with dns provided
        """
        save_config_mock = MagicMock(return_value=None)
        with patch.dict(nilrt_ip.__grains__, {"lsb_distrib_id": "nilrt"}):
            with patch.object(
                nilrt_ip, "_get_adapter_mode_info", MagicMock(return_value="TCPIP")
            ):
                with patch.object(nilrt_ip, "_save_config", save_config_mock):
                    with patch.object(
                        nilrt_ip, "_restart", MagicMock(return_value=None)
                    ):
                        self.assertEqual(
                            True,
                            nilrt_ip.set_static_all(
                                "eth0",
                                "192.168.10.4",
                                "255.255.255.0",
                                "192.168.10.1",
                                "8.8.4.4 8.8.8.8",
                            ),
                        )
                        mock_call = mock.call("eth0", "DNS_Address", "8.8.4.4")
                        self.assertEqual(True, mock_call in save_config_mock.mock_calls)

    def test_set_static_all_no_dns(self):
        """
        Tests set_static_all with no dns provided
        """
        save_config_mock = MagicMock(return_value=None)
        with patch.dict(nilrt_ip.__grains__, {"lsb_distrib_id": "nilrt"}):
            with patch.object(
                nilrt_ip, "_get_adapter_mode_info", MagicMock(return_value="TCPIP")
            ):
                with patch.object(nilrt_ip, "_save_config", save_config_mock):
                    with patch.object(
                        nilrt_ip, "_restart", MagicMock(return_value=None)
                    ):
                        self.assertEqual(
                            True,
                            nilrt_ip.set_static_all(
                                "eth0", "192.168.10.4", "255.255.255.0", "192.168.10.1"
                            ),
                        )
                        self.assertEqual(
                            None,
                            next(
                                (
                                    call
                                    for call in save_config_mock.mock_calls
                                    if "DNS_Address" in call.args
                                ),
                                None,
                            ),
                        )
