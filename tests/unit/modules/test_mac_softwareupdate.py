import salt.modules.mac_softwareupdate as mac_softwareupdate
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase

# These examples include 'recommended' and 'regular' updates. It's
# believed that only 'recommended' updates will ever have an "action", so
# included are examples of 'recommended' updates that have no action, the
# 'restart' action, and the 'shut down' action.

# This may need to be revised as we gather more example output.
MOJAVE_LIST_OUTPUT = """Software Update Tool

Finding available software
Software Update found the following new or updated software:
   * Command Line Tools (macOS Mojave version 10.14) for Xcode-10.3
    Command Line Tools (macOS Mojave version 10.14) for Xcode (10.3), 199140K [recommended]
   * macOS 10.14.1 Update
    macOS 10.14.1 Update (10.14.1), 199140K [recommended] [restart]
   * BridgeOSUpdateCustomer
    BridgeOSUpdateCustomer (10.14.4.1.1.1555388607), 328394K, [recommended] [shut down]
   - iCal-1.0.2
    iCal, (1.0.2), 6520K"""

CATALINA_LIST_OUTPUT = """Software Update Tool

Finding available software
Software Update found the following new or updated software:
* Label: Command Line Tools beta 5 for Xcode-11.0
    Title: Command Line Tools beta 5 for Xcode, Version: 11.0, Size: 224804K, Recommended: YES,
* Label: macOS Catalina Developer Beta-6
    Title: macOS Catalina Public Beta, Version: 5, Size: 3084292K, Recommended: YES, Action: restart,
* Label: BridgeOSUpdateCustomer
    Title: BridgeOSUpdateCustomer, Version: 10.15.0.1.1.1560926689, Size: 390674K, Recommended: YES, Action: shut down,
- Label: iCal-1.0.2
    Title: iCal, Version: 1.0.2, Size: 6520K,"""


class MacSoftwareUpdatePreCatalinaTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {mac_softwareupdate: {"__grains__": {"osrelease_info": [10, 14, 6]}}}

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_available(self, mock_execute):
        mock_execute.return_value = MOJAVE_LIST_OUTPUT
        result = mac_softwareupdate.list_available()
        expected = {
            "Command Line Tools (macOS Mojave version 10.14) for Xcode-10.3": "10.3",
            "macOS 10.14.1 Update": "10.14.1",
            "BridgeOSUpdateCustomer": "10.14.4.1.1.1555388607",
            "iCal-1.0.2": "1.0.2",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_available_trailing_ws(self, mock_execute):
        """Ensure the regex works with trailing whitespace in labels"""
        # This also tests for no version number returning an empty str.
        # This example's label will not install without the trailing space.
        mock_execute.return_value = (
            "Software Update Tool\n\nFinding available software\nSoftware Update found"
            " the following new or updated software:\n   * macOS Mojave 10.14.6"
            " Supplemental Update- \n    macOS Mojave 10.14.6 Supplemental Update ( ),"
            " 1581834K [recommended] [restart]"
        )
        result = mac_softwareupdate.list_available()
        expected = {"macOS Mojave 10.14.6 Supplemental Update- ": ""}
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_recommended(self, mock_execute):
        mock_execute.return_value = MOJAVE_LIST_OUTPUT
        result = mac_softwareupdate.list_available(recommended=True)
        expected = {
            "Command Line Tools (macOS Mojave version 10.14) for Xcode-10.3": "10.3",
            "macOS 10.14.1 Update": "10.14.1",
            "BridgeOSUpdateCustomer": "10.14.4.1.1.1555388607",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_restart(self, mock_execute):
        mock_execute.return_value = MOJAVE_LIST_OUTPUT
        result = mac_softwareupdate.list_available(restart=True)
        expected = {"macOS 10.14.1 Update": "10.14.1"}
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_shut_down(self, mock_execute):
        mock_execute.return_value = MOJAVE_LIST_OUTPUT
        result = mac_softwareupdate.list_available(shut_down=True)
        expected = {"BridgeOSUpdateCustomer": "10.14.4.1.1.1555388607"}
        self.assertEqual(result, expected)


class MacSoftwareUpdateCatalinaTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {mac_softwareupdate: {"__grains__": {"osrelease_info": [10, 15]}}}

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_available(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available()
        expected = {
            "Command Line Tools beta 5 for Xcode-11.0": "11.0",
            "macOS Catalina Developer Beta-6": "5",
            "BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689",
            "iCal-1.0.2": "1.0.2",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_recommended(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(recommended=True)
        expected = {
            "Command Line Tools beta 5 for Xcode-11.0": "11.0",
            "macOS Catalina Developer Beta-6": "5",
            "BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_restart(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(restart=True)
        expected = {"macOS Catalina Developer Beta-6": "5"}
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_shut_down(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(shut_down=True)
        expected = {"BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689"}
        self.assertEqual(result, expected)


class MacSoftwareUpdateBigSurTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {mac_softwareupdate: {"__grains__": {"osrelease_info": [11, 0]}}}

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_available(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available()
        expected = {
            "Command Line Tools beta 5 for Xcode-11.0": "11.0",
            "macOS Catalina Developer Beta-6": "5",
            "BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689",
            "iCal-1.0.2": "1.0.2",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_recommended(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(recommended=True)
        expected = {
            "Command Line Tools beta 5 for Xcode-11.0": "11.0",
            "macOS Catalina Developer Beta-6": "5",
            "BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689",
        }
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_restart(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(restart=True)
        expected = {"macOS Catalina Developer Beta-6": "5"}
        self.assertEqual(result, expected)

    @patch("salt.utils.mac_utils.execute_return_result")
    def test_list_shut_down(self, mock_execute):
        mock_execute.return_value = CATALINA_LIST_OUTPUT
        result = mac_softwareupdate.list_available(shut_down=True)
        expected = {"BridgeOSUpdateCustomer": "10.15.0.1.1.1560926689"}
        self.assertEqual(result, expected)
