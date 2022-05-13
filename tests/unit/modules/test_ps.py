"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""


import time
from collections import namedtuple

import salt.modules.ps as ps
import salt.utils.data
import salt.utils.psutil_compat as psutil
from tests.support.mock import MagicMock, Mock, call, patch
from tests.support.unit import TestCase, skipIf

HAS_PSUTIL_VERSION = False


PSUTIL2 = psutil.version_info >= (2, 0)

STUB_CPU_TIMES = namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4)
STUB_VIRT_MEM = namedtuple("vmem", "total available percent used free")(
    1000, 500, 50, 500, 500
)
STUB_SWAP_MEM = namedtuple("swap", "total used free percent sin sout")(
    1000, 500, 500, 50, 0, 0
)
STUB_PHY_MEM_USAGE = namedtuple("usage", "total used free percent")(1000, 500, 500, 50)
STUB_DISK_PARTITION = namedtuple("partition", "device mountpoint fstype, opts")(
    "/dev/disk0s2", "/", "hfs", "rw,local,rootfs,dovolfs,journaled,multilabel"
)
STUB_DISK_USAGE = namedtuple("usage", "total used free percent")(1000, 500, 500, 50)
STUB_NETWORK_IO = namedtuple(
    "iostat",
    "bytes_sent, bytes_recv, packets_sent, packets_recv, errin errout dropin dropout",
)(1000, 2000, 500, 600, 1, 2, 3, 4)
STUB_DISK_IO = namedtuple(
    "iostat", "read_count, write_count, read_bytes, write_bytes, read_time, write_time"
)(1000, 2000, 500, 600, 2000, 3000)
STUB_USER = namedtuple("user", "name, terminal, host, started")(
    "bdobbs", "ttys000", "localhost", 0.0
)
if psutil.version_info >= (0, 6, 0):
    HAS_PSUTIL_VERSION = True

STUB_PID_LIST = [0, 1, 2, 3]

try:
    import utmp  # pylint: disable=W0611

    HAS_UTMP = True
except ImportError:
    HAS_UTMP = False
# pylint: enable=import-error,unused-import


def _get_proc_name(proc):
    return proc.name() if PSUTIL2 else proc.name


def _get_proc_pid(proc):
    return proc.pid


class DummyProcess:
    """
    Dummy class to emulate psutil.Process. This ensures that _any_ string
    values used for any of the options passed in are converted to str types on
    both Python 2 and Python 3.
    """

    def __init__(
        self,
        cmdline=None,
        create_time=None,
        name=None,
        status=None,
        username=None,
        pid=None,
    ):
        self._cmdline = salt.utils.data.decode(
            cmdline if cmdline is not None else [], to_str=True
        )
        self._create_time = salt.utils.data.decode(
            create_time if create_time is not None else time.time(), to_str=True
        )
        self._name = salt.utils.data.decode(
            name if name is not None else [], to_str=True
        )
        self._status = salt.utils.data.decode(status, to_str=True)
        self._username = salt.utils.data.decode(username, to_str=True)
        self._pid = salt.utils.data.decode(
            pid if pid is not None else 12345, to_str=True
        )

    def cmdline(self):
        return self._cmdline

    def create_time(self):
        return self._create_time

    def name(self):
        return self._name

    def status(self):
        return self._status

    def username(self):
        return self._username

    def pid(self):
        return self._pid


class PsTestCase(TestCase):
    def setUp(self):
        self.mocked_proc = mocked_proc = MagicMock("salt.utils.psutil_compat.Process")
        if PSUTIL2:
            self.mocked_proc.name = Mock(return_value="test_mock_proc")
            self.mocked_proc.pid = Mock(return_value=9999999999)
        else:
            self.mocked_proc.name = "test_mock_proc"
            self.mocked_proc.pid = 9999999999

    @skipIf(not ps.PSUTIL2, "Only run for psutil 2.x")
    def test__get_proc_cmdline(self):
        cmdline = ["echo", "питон"]
        ret = ps._get_proc_cmdline(DummyProcess(cmdline=cmdline))
        assert ret == cmdline, ret

    def test_get_pid_list(self):
        with patch(
            "salt.utils.psutil_compat.pids", MagicMock(return_value=STUB_PID_LIST)
        ):
            self.assertListEqual(STUB_PID_LIST, ps.get_pid_list())

    def test_kill_pid(self):
        with patch("salt.utils.psutil_compat.Process") as send_signal_mock:
            ps.kill_pid(0, signal=999)
            self.assertEqual(send_signal_mock.call_args, call(0))

    def test_pkill(self):
        with patch("salt.utils.psutil_compat.Process.send_signal"), patch(
            "salt.utils.psutil_compat.process_iter",
            MagicMock(return_value=[self.mocked_proc]),
        ):
            self.mocked_proc.send_signal = MagicMock()
            test_signal = 1234
            ps.pkill(_get_proc_name(self.mocked_proc), signal=test_signal)
            self.assertEqual(self.mocked_proc.send_signal.call_args, call(test_signal))

    def test_pgrep(self):
        with patch(
            "salt.utils.psutil_compat.process_iter",
            MagicMock(return_value=[self.mocked_proc]),
        ):
            self.assertIn(
                _get_proc_pid(self.mocked_proc),
                ps.pgrep(_get_proc_name(self.mocked_proc)),
            )

    def test_pgrep_regex(self):
        with patch(
            "salt.utils.psutil_compat.process_iter",
            MagicMock(return_value=[self.mocked_proc]),
        ):
            self.assertIn(
                _get_proc_pid(self.mocked_proc),
                ps.pgrep("t.st_[a-z]+_proc", pattern_is_regex=True),
            )

    def test_cpu_percent(self):
        with patch("salt.utils.psutil_compat.cpu_percent", MagicMock(return_value=1)):
            self.assertEqual(ps.cpu_percent(), 1)

    def test_cpu_times(self):
        with patch(
            "salt.utils.psutil_compat.cpu_times", MagicMock(return_value=STUB_CPU_TIMES)
        ):
            self.assertDictEqual(
                {"idle": 4, "nice": 2, "system": 3, "user": 1}, ps.cpu_times()
            )

    @skipIf(
        HAS_PSUTIL_VERSION is False, "psutil 0.6.0 or greater is required for this test"
    )
    def test_virtual_memory(self):
        with patch(
            "salt.utils.psutil_compat.virtual_memory",
            MagicMock(return_value=STUB_VIRT_MEM),
        ):
            self.assertDictEqual(
                {
                    "used": 500,
                    "total": 1000,
                    "available": 500,
                    "percent": 50,
                    "free": 500,
                },
                ps.virtual_memory(),
            )

    @skipIf(
        HAS_PSUTIL_VERSION is False, "psutil 0.6.0 or greater is required for this test"
    )
    def test_swap_memory(self):
        with patch(
            "salt.utils.psutil_compat.swap_memory",
            MagicMock(return_value=STUB_SWAP_MEM),
        ):
            self.assertDictEqual(
                {
                    "used": 500,
                    "total": 1000,
                    "percent": 50,
                    "free": 500,
                    "sin": 0,
                    "sout": 0,
                },
                ps.swap_memory(),
            )

    def test_disk_partitions(self):
        with patch(
            "salt.utils.psutil_compat.disk_partitions",
            MagicMock(return_value=[STUB_DISK_PARTITION]),
        ):
            self.assertDictEqual(
                {
                    "device": "/dev/disk0s2",
                    "mountpoint": "/",
                    "opts": "rw,local,rootfs,dovolfs,journaled,multilabel",
                    "fstype": "hfs",
                },
                ps.disk_partitions()[0],
            )

    def test_disk_usage(self):
        with patch(
            "salt.utils.psutil_compat.disk_usage",
            MagicMock(return_value=STUB_DISK_USAGE),
        ):
            self.assertDictEqual(
                {"used": 500, "total": 1000, "percent": 50, "free": 500},
                ps.disk_usage("DUMMY_PATH"),
            )

    def test_disk_partition_usage(self):
        with patch(
            "salt.utils.psutil_compat.disk_partitions",
            MagicMock(return_value=[STUB_DISK_PARTITION]),
        ):
            self.assertDictEqual(
                {
                    "device": "/dev/disk0s2",
                    "mountpoint": "/",
                    "opts": "rw,local,rootfs,dovolfs,journaled,multilabel",
                    "fstype": "hfs",
                },
                ps.disk_partitions()[0],
            )

    def test_network_io_counters(self):
        with patch(
            "salt.utils.psutil_compat.net_io_counters",
            MagicMock(return_value=STUB_NETWORK_IO),
        ):
            self.assertDictEqual(
                {
                    "packets_sent": 500,
                    "packets_recv": 600,
                    "bytes_recv": 2000,
                    "dropout": 4,
                    "bytes_sent": 1000,
                    "errout": 2,
                    "errin": 1,
                    "dropin": 3,
                },
                ps.network_io_counters(),
            )

    def test_disk_io_counters(self):
        with patch(
            "salt.utils.psutil_compat.disk_io_counters",
            MagicMock(return_value=STUB_DISK_IO),
        ):
            self.assertDictEqual(
                {
                    "read_time": 2000,
                    "write_bytes": 600,
                    "read_bytes": 500,
                    "write_time": 3000,
                    "read_count": 1000,
                    "write_count": 2000,
                },
                ps.disk_io_counters(),
            )

    def test_get_users(self):
        with patch(
            "salt.utils.psutil_compat.users", MagicMock(return_value=[STUB_USER])
        ):
            self.assertDictEqual(
                {
                    "terminal": "ttys000",
                    "started": 0.0,
                    "host": "localhost",
                    "name": "bdobbs",
                },
                ps.get_users()[0],
            )

    def test_top(self):
        """
        See the following issue:

        https://github.com/saltstack/salt/issues/56942
        """
        # Limiting to one process because the test suite might be running as
        # PID 1 under docker and there may only *be* one process running.
        result = ps.top(num_processes=1, interval=0)
        assert len(result) == 1

    def test_top_zombie_process(self):
        # Get 3 pids that are currently running on the system
        pids = psutil.pids()[:3]
        # Get a process instance for each of the pids
        processes = [psutil.Process(pid) for pid in pids]

        # Patch the middle process to raise ZombieProcess when .cpu_times is called
        def raise_exception():
            raise psutil.ZombieProcess(processes[1].pid)

        processes[1].cpu_times = raise_exception

        # Make sure psutil.pids only returns the above 3 pids
        with patch("salt.utils.psutil_compat.pids", return_value=pids):
            # Make sure we use our process list from above
            with patch("salt.utils.psutil_compat.Process", side_effect=processes):
                result = ps.top(num_processes=1, interval=0)
                assert len(result) == 1

    ## This is commented out pending discussion on https://github.com/saltstack/salt/commit/2e5c3162ef87cca8a2c7b12ade7c7e1b32028f0a
    # @skipIf(not HAS_UTMP, "The utmp module must be installed to run test_get_users_utmp()")
    # @patch('salt.utils.psutil_compat.get_users', new=MagicMock(return_value=None))  # This will force the function to use utmp
    # def test_get_users_utmp(self):
    #     pass
