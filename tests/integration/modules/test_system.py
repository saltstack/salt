import datetime
import logging
import os
import signal
import subprocess
import textwrap
import time

import pytest
import salt.states.file
import salt.utils.files
import salt.utils.path
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@pytest.mark.skip_unless_on_linux
class SystemModuleTest(ModuleCase):
    """
    Validate the date/time functions in the system module
    """

    _hwclock_has_compare_ = None
    _systemd_timesyncd_available_ = None

    @classmethod
    def setUpClass(cls):
        cls.fmt_str = "%Y-%m-%d %H:%M:%S"
        cls._orig_time = None
        cls._machine_info = True

    @classmethod
    def tearDownClass(cls):
        for name in ("fmt_str", "_orig_time", "_machine_info"):
            delattr(cls, name)

    def setUp(self):
        super().setUp()
        if self._systemd_timesyncd_available_ is None:
            SystemModuleTest._systemd_timesyncd_available_ = self.run_function(
                "service.available", ["systemd-timesyncd"]
            )
        if self._systemd_timesyncd_available_:
            self.run_function("service.stop", ["systemd-timesyncd"])

    def tearDown(self):
        if self._orig_time is not None:
            self._restore_time()
        self._orig_time = None
        if self._machine_info is not True:
            self._restore_machine_info()
        self._machine_info = True
        if self._systemd_timesyncd_available_:
            self.run_function("service.start", ["systemd-timesyncd"])

    def _save_time(self):
        self._orig_time = datetime.datetime.utcnow()

    def _set_time(self, new_time, offset=None):
        t = new_time.timetuple()[:6]
        t += (offset,)
        return self.run_function("system.set_system_date_time", t)

    def _restore_time(self):
        result = self._set_time(self._orig_time, "+0000")
        self.assertTrue(result, msg="Unable to restore time properly")

    def _same_times(self, t1, t2, seconds_diff=30):
        """
        Helper function to check if two datetime objects
        are close enough to the same time.
        """
        return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)

    def _hwclock_has_compare(self):
        """
        Some builds of hwclock don't include the `--compare` function
        needed to test hw/sw clock synchronization. Returns false on
        systems where it's not present so that we can skip the
        comparison portion of the test.
        """
        if self._hwclock_has_compare_ is None:
            res = self.run_function("cmd.run_all", cmd="hwclock -h")
            SystemModuleTest._hwclock_has_compare_ = (
                res["retcode"] == 0 and res["stdout"].find("--compare") > 0
            )
        return self._hwclock_has_compare_

    def _test_hwclock_sync(self):
        """
        Check that hw and sw clocks are sync'd.
        """
        if not self.run_function("system.has_settable_hwclock"):
            return None
        if not self._hwclock_has_compare():
            return None

        class CompareTimeout(BaseException):
            pass

        def _alrm_handler(sig, frame):
            log.warning("hwclock --compare failed to produce output after 3 seconds")
            raise CompareTimeout

        for _ in range(2):
            try:
                orig_handler = signal.signal(signal.SIGALRM, _alrm_handler)
                signal.alarm(3)
                rpipeFd, wpipeFd = os.pipe()
                log.debug("Comparing hwclock to sys clock")
                with os.fdopen(rpipeFd, "r") as rpipe:
                    with os.fdopen(wpipeFd, "w") as wpipe:
                        with salt.utils.files.fopen(os.devnull, "r") as nulFd:
                            p = subprocess.Popen(
                                args=["hwclock", "--compare"],
                                stdin=nulFd,
                                stdout=wpipeFd,
                                stderr=subprocess.PIPE,
                            )
                            p.communicate()

                            # read header
                            rpipe.readline()

                            # read first time comparison
                            timeCompStr = rpipe.readline()

                            # stop
                            p.terminate()

                            timeComp = timeCompStr.split()
                            hwTime = float(timeComp[0])
                            swTime = float(timeComp[1])
                            diff = abs(hwTime - swTime)

                            self.assertTrue(
                                diff <= 2.0,
                                msg=("hwclock difference too big: " + str(timeCompStr)),
                            )
                            break
            except CompareTimeout:
                p.terminate()
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, orig_handler)
        else:
            log.error("Failed to check hwclock sync")

    def _save_machine_info(self):
        if os.path.isfile("/etc/machine-info"):
            with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
                self._machine_info = mach_info.read()
        else:
            self._machine_info = False

    def _restore_machine_info(self):
        if self._machine_info is not False:
            with salt.utils.files.fopen("/etc/machine-info", "w") as mach_info:
                mach_info.write(self._machine_info)
        else:
            self.run_function("file.remove", ["/etc/machine-info"])

    @pytest.mark.slow_test
    def test_get_system_date_time(self):
        """
        Test we are able to get the correct time
        """
        t1 = datetime.datetime.now()
        res = self.run_function("system.get_system_date_time")
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = "Difference in times is too large. Now: {} Fake: {}".format(t1, t2)
        self.assertTrue(self._same_times(t1, t2, seconds_diff=2), msg=msg)

    @pytest.mark.slow_test
    def test_get_system_date_time_utc(self):
        """
        Test we are able to get the correct time with utc
        """
        t1 = datetime.datetime.utcnow()
        res = self.run_function("system.get_system_date_time", utc_offset="+0000")
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = "Difference in times is too large. Now: {} Fake: {}".format(t1, t2)
        self.assertTrue(self._same_times(t1, t2, seconds_diff=2), msg=msg)

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_date_time(self):
        """
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        """
        self._save_time()
        cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)
        result = self._set_time(cmp_time)
        time_now = datetime.datetime.now()

        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )
        self.assertTrue(result and self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_date_time_utc(self):
        """
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        """
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        result = self._set_time(cmp_time, offset="+0000")
        time_now = datetime.datetime.utcnow()

        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_date_time_utcoffset_east(self):
        """
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        """
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        # 25200 seconds = 7 hours
        time_to_set = cmp_time - datetime.timedelta(seconds=25200)
        result = self._set_time(time_to_set, offset="-0700")
        time_now = datetime.datetime.utcnow()

        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_date_time_utcoffset_west(self):
        """
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        """
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        # 7200 seconds = 2 hours
        time_to_set = cmp_time + datetime.timedelta(seconds=7200)
        result = self._set_time(time_to_set, offset="+0200")
        time_now = datetime.datetime.utcnow()

        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.flaky(max_runs=4)
    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_time(self):
        """
        Test setting the system time without adjusting the date.
        """
        cmp_time = datetime.datetime.now().replace(hour=10, minute=5, second=0)
        self._save_time()

        result = self.run_function("system.set_system_time", ["10:05:00"])

        time_now = datetime.datetime.now()
        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )

        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_system_date(self):
        """
        Test setting the system date without adjusting the time.
        """
        cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)

        self._save_time()
        result = self.run_function(
            "system.set_system_date", [cmp_time.strftime("%Y-%m-%d")]
        )

        time_now = datetime.datetime.now()
        msg = "Difference in times is too large. Now: {} Fake: {}".format(
            time_now, cmp_time
        )

        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_get_computer_desc(self):
        """
        Test getting the system hostname
        """
        res = self.run_function("system.get_computer_desc")

        hostname_cmd = salt.utils.path.which("hostnamectl")
        if hostname_cmd:
            desc = self.run_function("cmd.run", ["hostnamectl status --pretty"])
            self.assertEqual(res, desc)
        else:
            if not os.path.isfile("/etc/machine-info"):
                self.assertFalse(res)
            else:
                with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
                    data = mach_info.read()
                    self.assertIn(res, data.decode("string_escape"))

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_computer_desc(self):
        """
        Test setting the computer description
        """
        self._save_machine_info()
        desc = "test"
        ret = self.run_function("system.set_computer_desc", [desc])
        computer_desc = self.run_function("system.get_computer_desc")

        self.assertTrue(ret)
        self.assertIn(desc, computer_desc)

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_set_computer_desc_multiline(self):
        """
        Test setting the computer description with a multiline string with tabs
        and double-quotes.
        """
        self._save_machine_info()
        desc = textwrap.dedent(
            '''\
            'First Line
            \tSecond Line: 'single-quoted string'
            \t\tThird Line: "double-quoted string with unicode: питон"'''
        )
        ret = self.run_function("system.set_computer_desc", [desc])
        # self.run_function returns the serialized return, we need to convert
        # back to unicode to compare to desc. in the assertIn below.
        computer_desc = salt.utils.stringutils.to_unicode(
            self.run_function("system.get_computer_desc")
        )

        self.assertTrue(ret)
        self.assertIn(desc, computer_desc)

    @pytest.mark.skip_if_not_root
    @pytest.mark.slow_test
    def test_has_hwclock(self):
        """
        Verify platform has a settable hardware clock, if possible.
        """
        if self.run_function("grains.get", ["os_family"]) == "NILinuxRT":
            self.assertTrue(self.run_function("system._has_settable_hwclock"))
            self.assertTrue(self._hwclock_has_compare())


@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
class WinSystemModuleTest(ModuleCase):
    """
    Validate the date/time functions in the win_system module
    """

    @pytest.mark.slow_test
    def test_get_computer_name(self):
        """
        Test getting the computer name
        """
        ret = self.run_function("system.get_computer_name")

        self.assertTrue(isinstance(ret, str))
        import socket

        name = socket.gethostname()
        self.assertEqual(name, ret)

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_computer_desc(self):
        """
        Test setting the computer description
        """
        current_desc = self.run_function("system.get_computer_desc")
        desc = "test description"
        try:
            set_desc = self.run_function("system.set_computer_desc", [desc])
            self.assertTrue(set_desc)

            get_desc = self.run_function("system.get_computer_desc")
            self.assertEqual(set_desc["Computer Description"], get_desc)
        finally:
            self.run_function("system.set_computer_desc", [current_desc])

    @skipIf(True, "WAR ROOM 7/29/2019, unit test?")
    def test_get_system_time(self):
        """
        Test getting the system time
        """
        time_now = datetime.datetime.now()
        # We have to do some datetime fu to account for the possibility that the
        # system time will be obtained just before the minutes increment
        ret = self.run_function("system.get_system_time", timeout=300)
        # Split out time and AM/PM
        sys_time, meridian = ret.split(" ")
        h, m, s = sys_time.split(":")
        # Get the current time
        # Use the system time to generate a datetime object for the system time
        # with the same date
        time_sys = time_now.replace(hour=int(h), minute=int(m), second=int(s))
        # get_system_time returns a non 24 hour time
        # Lets make it 24 hour time
        if meridian == "PM":
            time_sys = time_sys + datetime.timedelta(hours=12)
        diff = time_sys - time_now
        # Timeouts are set to 300 seconds. We're adding a 30 second buffer
        self.assertTrue(diff.seconds < 330)

    @pytest.mark.slow_test
    def test_get_system_date(self):
        """
        Test getting system date
        """
        ret = self.run_function("system.get_system_date")
        date = datetime.datetime.now().strftime("%m/%d/%Y")
        self.assertEqual(date, ret)


@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
class WinSystemModuleTimeSettingTest(ModuleCase):
    """
    Validate the date/time functions in the win_system module

    .. note::

        In order for these tests to pass, time sync must be disabled for the VM
        in the hyper-visor
    """

    @classmethod
    def setUpClass(cls):
        if subprocess.call("sc config w32time start= disabled > nul", shell=True) != 0:
            log.error("Failed to disable w32time service")
        if subprocess.call("sc stop w32time", shell=True) != 0:
            log.error("Failed to stop w32time service")

    @classmethod
    def tearDownClass(cls):
        if subprocess.call("sc config w32time start= auto > nul", shell=True) != 0:
            log.error("Failed to enable w32time service")
        if subprocess.call("sc start w32time", shell=True) != 0:
            log.error("Failed to start w32time service")
        if subprocess.call("w32tm /resync", shell=True) != 0:
            log.error("Re-syncing time failed")

    @skipIf(True, "WAR ROOM 7/18/2019, unit test?")
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_system_time(self):
        """
        Test setting the system time
        """
        # If the test fails, the hypervisor may be maintaining time sync
        test_time = "10:55"
        self.run_function("system.set_system_time", [test_time + " AM"])
        time.sleep(0.25)
        new_time = datetime.datetime.now().strftime("%H:%M")
        self.assertEqual(new_time, test_time)

    @skipIf(True, "WAR ROOM 7/18/2019, unit test?")
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_system_date(self):
        """
        Test setting system date
        """
        # If the test fails, the hypervisor may be maintaining time sync
        self.run_function("system.set_system_date", ["03/25/2018"])
        new_date = datetime.datetime.now().strftime("%Y/%m/%d")
        self.assertEqual(new_date, "2018/03/25")
