import salt.modules.icinga2 as icinga2
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class Icinga2TestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.icinga2
    """

    def setup_loader_modules(self):
        return {icinga2: {}}

    def test_node_setup_without_master_host(self):
        """
        Test if icinga2 command is correctly called when master_host is omitted
        """
        mock = MagicMock(return_value=1)
        with patch("salt.modules.icinga2.get_certs_path", MagicMock(return_value="")):
            with patch.dict(icinga2.__salt__, {"cmd.run_all": mock}):
                icinga2.node_setup(
                    "example.com", "master.example.com", "example_ticket",
                )
                mock.assert_called_with(
                    [
                        "icinga2",
                        "node",
                        "setup",
                        "--ticket",
                        "example_ticket",
                        "--endpoint",
                        "master.example.com",
                        "--zone",
                        "example.com",
                        "--master_host",
                        "master.example.com",
                        "--trustedcert",
                        "trusted-master.crt",
                    ],
                    python_shell=False,
                )

    def test_node_setup_with_all_args(self):
        """
        Test if icinga2 command is correctly called when all arguments are specified
        """
        mock = MagicMock(return_value=1)
        with patch("salt.modules.icinga2.get_certs_path", MagicMock(return_value="")):
            with patch.dict(icinga2.__salt__, {"cmd.run_all": mock}):
                icinga2.node_setup(
                    "example.com", "master.example.com", "example_ticket", "0.0.0.0"
                )
                mock.assert_called_with(
                    [
                        "icinga2",
                        "node",
                        "setup",
                        "--ticket",
                        "example_ticket",
                        "--endpoint",
                        "master.example.com",
                        "--zone",
                        "example.com",
                        "--master_host",
                        "0.0.0.0",
                        "--trustedcert",
                        "trusted-master.crt",
                    ],
                    python_shell=False,
                )
