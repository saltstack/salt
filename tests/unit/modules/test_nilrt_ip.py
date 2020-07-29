# Import python libs

# Import Salt Libs
import salt.modules.nilrt_ip as nilrt_ip

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

NO_PYCONNMAN = False
NO_DBUS = False
try:
    import pyconnman  # pylint: disable=W0611
except ImportError:
    NO_PYCONNMAN = True

try:
    import dbus  # pylint: disable=W0611
except ImportError:
    NO_DBUS = True


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

    @skipIf(NO_PYCONNMAN, "Install pyconnman before running NilrtIP unit tests.")
    @skipIf(NO_DBUS, "Install dbus before running NilrtIP unit tests.")
    def test_get_service_info(self):
        """
        Tests key ipv6 exists in response of _get_service_info when expecting
        IPv6 information
        """

        def side_effect(prop):
            """
            Return expected properties to get _get_service_info to return
            IPv6 information
            """
            if prop == "State":
                return "ready"
            elif prop == "IPv6":
                return {"Prefix": "stub"}
            return {"Interface": None, "Address": None, "Method": None}

        with patch("pyconnman.ConnService") as mock:
            instance = mock.return_value
            instance.get_property = MagicMock(side_effect=side_effect)
            assert "ipv6" in nilrt_ip._get_service_info("service").keys()
