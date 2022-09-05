import os

import salt.modules.status as status
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class StatusTestCase(TestCase, LoaderModuleMockMixin):
    """
    test modules.status functions
    """

    def setup_loader_modules(self):
        return {status: {}}

    def _set_up_test_uptime(self):
        """
        Define common mock data for status.uptime tests
        """

        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.now = 1477004312
        m.ut = 1540154.00
        m.idle = 3047777.32
        m.ret = {
            "users": 3,
            "seconds": 1540154,
            "since_t": 1475464158,
            "days": 17,
            "since_iso": "2016-10-03T03:09:18",
            "time": "19:49",
        }

        return m

    def _set_up_test_uptime_sunos(self):
        """
        Define common mock data for cmd.run_all for status.uptime on SunOS
        """

        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = {
            "retcode": 0,
            "stdout": "unix:0:system_misc:boot_time    1475464158",
        }

        return m

    def test_uptime_linux(self):
        """
        Test modules.status.uptime function for Linux
        """
        m = self._set_up_test_uptime()

        with patch.multiple(
            salt.utils.platform,
            is_linux=MagicMock(return_value=True),
            is_sunos=MagicMock(return_value=False),
            is_darwin=MagicMock(return_value=False),
            is_freebsd=MagicMock(return_value=False),
            is_openbsd=MagicMock(return_value=False),
            is_netbsd=MagicMock(return_value=False),
        ), patch("salt.utils.path.which", MagicMock(return_value=True)), patch.dict(
            status.__salt__,
            {"cmd.run": MagicMock(return_value=os.linesep.join(["1", "2", "3"]))},
        ), patch(
            "time.time", MagicMock(return_value=m.now)
        ), patch(
            "os.path.exists", MagicMock(return_value=True)
        ):
            proc_uptime = salt.utils.stringutils.to_str("{} {}".format(m.ut, m.idle))

            with patch("salt.utils.files.fopen", mock_open(read_data=proc_uptime)):
                ret = status.uptime()
                self.assertDictEqual(ret, m.ret)
            with patch("os.path.exists", MagicMock(return_value=False)):
                with self.assertRaises(CommandExecutionError):
                    status.uptime()

    def test_uptime_sunos(self):
        """
        Test modules.status.uptime function for SunOS
        """
        m = self._set_up_test_uptime()
        m2 = self._set_up_test_uptime_sunos()
        with patch.multiple(
            salt.utils.platform,
            is_linux=MagicMock(return_value=False),
            is_sunos=MagicMock(return_value=True),
            is_darwin=MagicMock(return_value=False),
            is_freebsd=MagicMock(return_value=False),
            is_openbsd=MagicMock(return_value=False),
            is_netbsd=MagicMock(return_value=False),
        ), patch("salt.utils.path.which", MagicMock(return_value=True)), patch.dict(
            status.__salt__,
            {
                "cmd.run": MagicMock(return_value=os.linesep.join(["1", "2", "3"])),
                "cmd.run_all": MagicMock(return_value=m2.ret),
            },
        ), patch(
            "time.time", MagicMock(return_value=m.now)
        ):
            ret = status.uptime()
            self.assertDictEqual(ret, m.ret)

    def test_uptime_macos(self):
        """
        Test modules.status.uptime function for macOS
        """
        m = self._set_up_test_uptime()

        kern_boottime = (
            "{{ sec = {0}, usec = {1:0<6} }} Mon Oct 03 03:09:18.23 2016".format(
                *str(m.now - m.ut).split(".")
            )
        )
        with patch.multiple(
            salt.utils.platform,
            is_linux=MagicMock(return_value=False),
            is_sunos=MagicMock(return_value=False),
            is_darwin=MagicMock(return_value=True),
            is_freebsd=MagicMock(return_value=False),
            is_openbsd=MagicMock(return_value=False),
            is_netbsd=MagicMock(return_value=False),
        ), patch("salt.utils.path.which", MagicMock(return_value=True)), patch.dict(
            status.__salt__,
            {
                "cmd.run": MagicMock(return_value=os.linesep.join(["1", "2", "3"])),
                "sysctl.get": MagicMock(return_value=kern_boottime),
            },
        ), patch(
            "time.time", MagicMock(return_value=m.now)
        ):

            ret = status.uptime()
            self.assertDictEqual(ret, m.ret)

            with patch.dict(
                status.__salt__, {"sysctl.get": MagicMock(return_value="")}
            ):
                with self.assertRaises(CommandExecutionError):
                    status.uptime()

    def test_uptime_return_success_not_supported(self):
        """
        Test modules.status.uptime function for other platforms
        """
        with patch.multiple(
            salt.utils.platform,
            is_linux=MagicMock(return_value=False),
            is_sunos=MagicMock(return_value=False),
            is_darwin=MagicMock(return_value=False),
            is_freebsd=MagicMock(return_value=False),
            is_openbsd=MagicMock(return_value=False),
            is_netbsd=MagicMock(return_value=False),
        ):
            exc_mock = MagicMock(side_effect=CommandExecutionError)
            with self.assertRaises(CommandExecutionError):
                with patch.dict(status.__salt__, {"cmd.run": exc_mock}):
                    status.uptime()

    def _set_up_test_cpustats_openbsd(self):
        """
        Define mock data for status.cpustats on OpenBSD
        """

        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = {
            "0": {
                "User": "0.0%",
                "Nice": "0.0%",
                "System": "4.5%",
                "Interrupt": "0.5%",
                "Idle": "95.0%",
            }
        }

        return m

    def test_cpustats_openbsd(self):
        """
        Test modules.status.cpustats function for OpenBSD
        """
        m = self._set_up_test_cpustats_openbsd()

        systat = (
            "\n\n   1 users Load 0.20 0.07 0.05                        salt.localdomain"
            " 09:42:42\nCPU                User           Nice        System    "
            " Interrupt          Idle\n0                  0.0%           0.0%         "
            " 4.5%          0.5%         95.0%\n"
        )

        with patch.multiple(
            salt.utils.platform,
            is_linux=MagicMock(return_value=False),
            is_sunos=MagicMock(return_value=False),
            is_darwin=MagicMock(return_value=False),
            is_freebsd=MagicMock(return_value=False),
            is_openbsd=MagicMock(return_value=True),
            is_netbsd=MagicMock(return_value=False),
        ), patch("salt.utils.path.which", MagicMock(return_value=True)), patch.dict(
            status.__grains__, {"kernel": "OpenBSD"}
        ), patch.dict(
            status.__salt__, {"cmd.run": MagicMock(return_value=systat)}
        ):
            ret = status.cpustats()
            self.assertDictEqual(ret, m.ret)

    def _set_up_test_cpuinfo_bsd(self):
        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = {
            "hw.model": "Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz",
            "hw.ncpu": "4",
        }

        return m

    def test_cpuinfo_freebsd(self):
        m = self._set_up_test_cpuinfo_bsd()
        sysctl = "hw.model:Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu:4"

        with patch.dict(status.__grains__, {"kernel": "FreeBSD"}):
            with patch.dict(
                status.__salt__, {"cmd.run": MagicMock(return_value=sysctl)}
            ):
                ret = status.cpuinfo()
                self.assertDictEqual(ret, m.ret)

    def test_cpuinfo_openbsd(self):
        m = self._set_up_test_cpuinfo_bsd()
        sysctl = "hw.model=Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu=4"

        for bsd in ["NetBSD", "OpenBSD"]:
            with patch.dict(status.__grains__, {"kernel": bsd}):
                with patch.dict(
                    status.__salt__, {"cmd.run": MagicMock(return_value=sysctl)}
                ):
                    ret = status.cpuinfo()
                    self.assertDictEqual(ret, m.ret)

    def _set_up_test_meminfo_openbsd(self):
        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = {
            "active virtual pages": "355M",
            "free list size": "305M",
            "page faults": "845",
            "pages reclaimed": "1",
            "pages paged in": "2",
            "pages paged out": "3",
            "pages freed": "4",
            "pages scanned": "5",
        }

        return m

    def test_meminfo_openbsd(self):
        m = self._set_up_test_meminfo_openbsd()
        vmstat = (
            " procs    memory       page                    disks    traps         "
            " cpu\n r   s   avm     fre  flt  re  pi  po  fr  sr cd0 sd0  int   sys  "
            " cs us sy id\n 2 103  355M    305M  845   1   2   3   4   5   0   1   21  "
            " 682   86  1  1 98"
        )

        with patch.dict(status.__grains__, {"kernel": "OpenBSD"}):
            with patch.dict(
                status.__salt__, {"cmd.run": MagicMock(return_value=vmstat)}
            ):
                ret = status.meminfo()
                self.assertDictEqual(ret, m.ret)

    def _set_up_test_w_linux(self):
        """
        Define mock data for status.w on Linux
        """

        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = [
            {
                "idle": "0s",
                "jcpu": "0.24s",
                "login": "13:42",
                "pcpu": "0.16s",
                "tty": "pts/1",
                "user": "root",
                "what": "nmap -sV 10.2.2.2",
            }
        ]

        return m

    def _set_up_test_w_bsd(self):
        """
        Define mock data for status.w on Linux
        """

        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = [
            {
                "idle": "0",
                "from": "10.2.2.1",
                "login": "1:42PM",
                "tty": "p1",
                "user": "root",
                "what": "nmap -sV 10.2.2.2",
            }
        ]

        return m

    def test_w_linux(self):
        m = self._set_up_test_w_linux()
        w_output = "root   pts/1  13:42    0s  0.24s  0.16s nmap -sV 10.2.2.2"

        with patch.dict(status.__grains__, {"kernel": "Linux"}):
            with patch.dict(
                status.__salt__, {"cmd.run": MagicMock(return_value=w_output)}
            ):
                ret = status.w()
                self.assertListEqual(ret, m.ret)

    def test_w_bsd(self):
        m = self._set_up_test_w_bsd()
        w_output = "root   p1 10.2.2.1    1:42PM  0 nmap -sV 10.2.2.2"

        for bsd in ["Darwin", "FreeBSD", "OpenBSD"]:
            with patch.dict(status.__grains__, {"kernel": bsd}):
                with patch.dict(
                    status.__salt__, {"cmd.run": MagicMock(return_value=w_output)}
                ):
                    ret = status.w()
                    self.assertListEqual(ret, m.ret)

    def _set_up_test_status_pid_linux(self):
        class MockData:
            """
            Store mock data
            """

        m = MockData()
        m.ret = "2701\n7539\n7540\n7542\n7623"
        return m

    def test_status_pid_linux(self):
        m = self._set_up_test_status_pid_linux()
        ps = (
            "UID      PID PPID  C STIME TTY      TIME CMD\nroot     360    2  0 Jun08 ?"
            "    00:00:00   [jbd2/dm-0-8]\nroot     947    2  0 Jun08 ?    00:00:00  "
            " [jbd2/dm-1-8]\nroot     949    2  0 Jun08 ?    00:00:09  "
            " [jbd2/dm-3-8]\nroot     951    2  0 Jun08 ?    00:00:00  "
            " [jbd2/dm-4-8]\nroot    2701    1  0 Jun08 ?    00:00:28   /usr/sbin/httpd"
            " -k start\napache  7539 2701  0 04:40 ?    00:00:04     /usr/sbin/httpd -k"
            " start\napache  7540 2701  0 04:40 ?    00:00:02     /usr/sbin/httpd -k"
            " start\napache  7542 2701  0 04:40 ?    00:01:46     /usr/sbin/httpd -k"
            " start\napache  7623 2701  0 04:40 ?    00:02:41     /usr/sbin/httpd -k"
            " start\nroot    1564    1  0 Jun11 ?    00:07:19   /usr/bin/python3"
            " /usr/bin/salt-minion -d\nroot    6674 1564  0 19:53 ?    00:00:00    "
            " /usr/bin/python3 /usr/bin/salt-call status.pid httpd -l debug"
        )

        with patch.dict(status.__grains__, {"ps": "ps -efHww"}):
            with patch.dict(
                status.__salt__, {"cmd.run_stdout": MagicMock(return_value=ps)}
            ):
                with patch.object(os, "getpid", return_value="6674"):
                    ret = status.pid("httpd")
                    self.assertEqual(ret, m.ret)
