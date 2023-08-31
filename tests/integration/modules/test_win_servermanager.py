import pytest

from tests.support.case import ModuleCase


@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
class WinServermanagerTest(ModuleCase):
    """
    Test for salt.modules.win_servermanager
    """

    @pytest.mark.slow_test
    def test_list_available(self):
        """
        Test list available features to install
        """
        cmd = self.run_function("win_servermanager.list_available")
        self.assertIn("DNS", cmd)
        self.assertIn("NetworkController", cmd)
        self.assertIn("RemoteAccess", cmd)
