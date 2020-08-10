import salt.states.icinga2 as icinga2
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class Icinga2TestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.icinga2
    """

    def setup_loader_modules(self):
        return {icinga2: {}}

    def test_node_setup_without_master_host(self):
        """
        Test if icinga2 module is correctly called when master_host is omitted
        """
        mock = MagicMock(
            return_value={"retcode": True, "stdout": "node_setup executed"}
        )
        with patch("salt.states.icinga2.get_certs_path", MagicMock(return_value="")):
            with patch("os.path.isfile", MagicMock(return_value=False)):
                with patch.dict(icinga2.__salt__, {"icinga2.node_setup": mock}):
                    with patch.dict(icinga2.__opts__, {"test": False}):
                        icinga2.node_setup(
                            "example.com", "master.example.com", "example_ticket",
                        )
                        mock.assert_called_with(
                            "example.com",
                            "master.example.com",
                            "example_ticket",
                            "master.example.com",
                        )

    def test_node_setup_with_all_args(self):
        """
        Test if icinga2 module is correctly called when all arguments are specified
        """
        mock = MagicMock(
            return_value={"retcode": True, "stdout": "node_setup executed"}
        )
        with patch("salt.states.icinga2.get_certs_path", MagicMock(return_value="")):
            with patch("os.path.isfile", MagicMock(return_value=False)):
                with patch.dict(icinga2.__salt__, {"icinga2.node_setup": mock}):
                    with patch.dict(icinga2.__opts__, {"test": False}):
                        icinga2.node_setup(
                            "example.com",
                            "master.example.com",
                            "example_ticket",
                            "0.0.0.0",
                        )
                        mock.assert_called_with(
                            "example.com",
                            "master.example.com",
                            "example_ticket",
                            "0.0.0.0",
                        )
