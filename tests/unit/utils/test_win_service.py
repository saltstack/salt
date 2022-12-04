import pytest

from tests.support.unit import TestCase

try:
    import salt.utils.win_service as win_service
except Exception as exc:  # pylint: disable=broad-except
    win_service = exc


class WinServiceImportTestCase(TestCase):
    def test_import(self):
        """
        Simply importing should not raise an error, especially on Linux
        """
        if isinstance(win_service, Exception):
            raise Exception(
                "Importing win_system caused traceback: {}".format(win_service)
            )


@pytest.mark.skip_unless_on_windows
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
            "sid",
        ]
        for field_name in field_names:
            self.assertIn(field_name, info)

        # Make sure it returns a valid Display Name
        self.assertEqual(info["DisplayName"], "Print Spooler")
