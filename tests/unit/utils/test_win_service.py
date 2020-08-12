# Import Python Libs
import os

# Import Salt Libs
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.mock import patch, MagicMock
from tests.support.unit import TestCase, skipIf

try:
    import salt.utils.win_service as win_service
    from salt.exceptions import CommandExecutionError
except Exception as exc:  # pylint: disable=broad-except
    win_service = exc

# Import 3rd Party Libs
try:
    import pywintypes
    import win32service
    WINAPI = True
except ImportError:
    WINAPI = False


class WinServiceImportTestCase(TestCase):

    def test_import(self):
        """
        Simply importing should not raise an error, especially on Linux
        """
        if isinstance(win_service, Exception):
            raise Exception(
                "Importing win_system caused traceback: {0}".format(win_service)
            )


@skipIf(not salt.utils.platform.is_windows(), "Only test on Windows systems")
@skipIf(not WINAPI, "Missing PyWin32 libraries")
class WinServiceTestCase(TestCase):
    """
    Test cases for salt.utils.win_service
    """

    def test_info(self):
        """
        Test service.info
        """
        # Get info about the spooler service
        info = win_service.info("spooler")

        # Make sure it returns these fields
        field_names = [
            "BinaryPath",
            "ControlsAccepted",
            "Dependencies",
            "Description",
            "DisplayName",
            "ErrorControl",
            "LoadOrderGroup",
            "ServiceAccount",
            "ServiceType",
            "StartType",
            "StartTypeDelayed",
            "Status",
            "Status_CheckPoint",
            "Status_ExitCode",
            "Status_ServiceCode",
            "Status_WaitHint",
            "TagID",
            "sid"
        ]
        for field_name in field_names:
            self.assertIn(field_name, info)

        # Make sure it returns a valid Display Name
        self.assertEqual(info["DisplayName"], "Print Spooler")
