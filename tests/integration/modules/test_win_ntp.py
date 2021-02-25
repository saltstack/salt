import pytest
from tests.support.case import ModuleCase


@pytest.mark.flaky(max_runs=4)
@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
class NTPTest(ModuleCase):
    """
    Validate windows ntp module
    """

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_ntp_set_servers(self):
        """
        test ntp get and set servers
        """
        ntp_srv = "pool.ntp.org"
        set_srv = self.run_function("ntp.set_servers", [ntp_srv])
        self.assertTrue(set_srv)

        get_srv = self.run_function("ntp.get_servers")
        self.assertEqual(ntp_srv, get_srv[0])
