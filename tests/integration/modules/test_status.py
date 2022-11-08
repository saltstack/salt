import random

import pytest

import salt.utils.platform
from tests.support.case import ModuleCase


@pytest.mark.windows_whitelisted
class StatusModuleTest(ModuleCase):
    """
    Test the status module
    """

    @pytest.mark.skip_on_windows
    @pytest.mark.flaky(max_runs=4)
    def test_status_pid(self):
        """
        status.pid
        """
        status_pid = self.run_function("status.pid", ["salt"])
        grab_pids = status_pid.split()[:10]
        random_pid = random.choice(grab_pids)
        grep_salt = self.run_function("cmd.run", ["pgrep -f salt"])
        self.assertIn(random_pid, grep_salt)

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.slow_test
    def test_status_cpuload(self):
        """
        status.cpuload
        """
        ret = self.run_function("status.cpuload")
        self.assertTrue(isinstance(ret, float))

    @pytest.mark.skip_unless_on_windows
    @pytest.mark.slow_test
    def test_status_saltmem(self):
        """
        status.saltmem
        """
        ret = self.run_function("status.saltmem")
        self.assertTrue(isinstance(ret, int))

    @pytest.mark.slow_test
    def test_status_diskusage(self):
        """
        status.diskusage
        """
        ret = self.run_function("status.diskusage")
        if salt.utils.platform.is_darwin():
            self.assertIn("not yet supported on this platform", ret)
        elif salt.utils.platform.is_windows():
            self.assertTrue(isinstance(ret["percent"], float))
        else:
            self.assertIn("total", str(ret))
            self.assertIn("available", str(ret))

    @pytest.mark.slow_test
    def test_status_procs(self):
        """
        status.procs
        """
        ret = self.run_function("status.procs")
        for x, y in ret.items():
            self.assertIn("cmd", y)

    @pytest.mark.slow_test
    def test_status_uptime(self):
        """
        status.uptime
        """
        ret = self.run_function("status.uptime")

        if salt.utils.platform.is_windows():
            self.assertTrue(isinstance(ret, float))
        else:
            self.assertTrue(isinstance(ret["days"], int))
