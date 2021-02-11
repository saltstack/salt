import pytest
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows tests only")
@pytest.mark.windows_whitelisted
class AutoRunsModuleTest(ModuleCase):
    """
    Test the autoruns module
    """

    @pytest.mark.slow_test
    def test_win_autoruns_list(self):
        """
        test win_autoruns.list module
        """
        ret = self.run_function("autoruns.list")
        self.assertIn("HKLM", str(ret))
        self.assertTrue(isinstance(ret, dict))
