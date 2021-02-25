import pytest
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
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
