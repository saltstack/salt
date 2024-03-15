import time
from collections import namedtuple

import psutil
import pytest

import salt.modules.ps
import salt.modules.ps as ps
import salt.utils.data
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, Mock, call, patch

# TestCase Exceptions are tested in tests/unit/modules/test_ps.py


@pytest.fixture
def configure_loader_modules():
    return {ps: {}}


@pytest.fixture
def sample_process():
    status = b"fnord"
    extra_data = {
        "utime": "42",
        "stime": "42",
        "children_utime": "42",
        "children_stime": "42",
        "ttynr": "42",
        "cpu_time": "42",
        "blkio_ticks": "99",
        "ppid": "99",
        "cpu_num": "9999999",
    }
    important_data = {
        "name": b"blerp",
        "status": status,
        "create_time": "393829200",
    }
    important_data.update(extra_data)
    patch_stat_file = patch(
        "psutil._psplatform.Process._parse_stat_file",
        return_value=important_data,
        create=True,
    )
    patch_exe = patch(
        "psutil._psplatform.Process.exe",
        return_value=important_data["name"].decode(),
        create=True,
    )
    patch_oneshot = patch(
        "psutil._psplatform.Process.oneshot",
        return_value={
            # These keys can be found in psutil/_psbsd.py
            1: important_data["status"].decode(),
            # create
            9: float(important_data["create_time"]),
            # user
            14: float(important_data["create_time"]),
            # sys
            15: float(important_data["create_time"]),
            # ch_user
            16: float(important_data["create_time"]),
            # ch_sys -- we don't really care what they are, obviously
            17: float(important_data["create_time"]),
            24: important_data["name"].decode(),
        },
        create=True,
    )
    patch_kinfo = patch(
        "psutil._psplatform.Process._get_kinfo_proc",
        return_value={
            # These keys can be found in psutil/_psosx.py
            9: important_data["status"].decode(),
            8: float(important_data["create_time"]),
            10: important_data["name"].decode(),
        },
        create=True,
    )
    patch_status = patch(
        "psutil._psplatform.Process.status", return_value=status.decode()
    )
    patch_create_time = patch(
        "psutil._psplatform.Process.create_time", return_value=393829200
    )
    with (
        patch_stat_file
    ), patch_status, patch_create_time, patch_exe, patch_oneshot, patch_kinfo:
        proc = psutil.Process(pid=42)
        proc.info = proc.as_dict(("name", "status"))
        yield proc


def test__status_when_process_is_found_with_matching_status_then_proc_info_should_be_returned(
    sample_process,
):
    expected_result = [{"pid": 42, "name": "blerp"}]
    proc = sample_process
    with patch(
        "psutil.process_iter",
        autospec=True,
        return_value=[
            proc
        ],  # MagicMock(info={"status": "fnord", "blerp": "whatever"})],
    ):

        actual_result = salt.modules.ps.status(status="fnord")
        assert actual_result == expected_result


def test__status_when_no_matching_processes_then_no_results_should_be_returned():
    expected_result = []
    with patch(
        "psutil.process_iter",
        autospec=True,
        return_value=[MagicMock(info={"status": "foo", "blerp": "whatever"})],
    ):

        actual_result = salt.modules.ps.status(status="fnord")
        assert actual_result == expected_result


def test__status_when_some_matching_processes_then_only_correct_info_should_be_returned(
    sample_process,
):
    expected_result = [{"name": "blerp", "pid": 42}]
    with patch(
        "psutil.process_iter",
        autospec=True,
        return_value=[
            sample_process,
            MagicMock(info={"status": "foo", "name": "wherever", "pid": 9998}),
            MagicMock(info={"status": "bar", "name": "whenever", "pid": 9997}),
        ],
    ):

        actual_result = salt.modules.ps.status(status="fnord")
        assert actual_result == expected_result


STUB_CPU_TIMES = namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4)
STUB_CPU_TIMES_PERCPU = [
    namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4),
    namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4),
    namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4),
    namedtuple("cputimes", "user nice system idle")(1, 2, 3, 4),
]
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
STUB_NETWORK_IO_PERNIC = {
    "lo": STUB_NETWORK_IO,
    "eth0": STUB_NETWORK_IO,
    "eth1": STUB_NETWORK_IO,
}
STUB_DISK_IO = namedtuple(
    "iostat", "read_count, write_count, read_bytes, write_bytes, read_time, write_time"
)(1000, 2000, 500, 600, 2000, 3000)
STUB_DISK_IO_PERDISK = {
    "nvme0n1": STUB_DISK_IO,
    "nvme0n1p1": STUB_DISK_IO,
    "nvme0n1p2": STUB_DISK_IO,
    "nvme0n1p3": STUB_DISK_IO,
}


@pytest.fixture
def stub_memory_usage():
    return namedtuple(
        "vmem",
        "total available percent used free active inactive buffers cached shared",
    )(
        15722012672,
        9329594368,
        40.7,
        5137018880,
        4678086656,
        6991405056,
        2078953472,
        1156378624,
        4750528512,
        898908160,
    )


@pytest.fixture(scope="module")
def stub_user():
    return namedtuple("user", "name, terminal, host, started")(
        "bdobbs", "ttys000", "localhost", 0.0
    )


STUB_PID_LIST = [0, 1, 2, 3]

try:
    import utmp  # pylint: disable=W0611

    HAS_UTMP = True
except ImportError:
    HAS_UTMP = False
# pylint: enable=import-error,unused-import


def _get_proc_name(proc):
    return proc.name()


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
        cpu_times=None,
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

        if salt.utils.platform.is_windows():
            scputimes = namedtuple(
                "scputimes", ["user", "system", "children_user", "children_system"]
            )
            dummy_cpu_times = scputimes(7713.79, 1278.44, 17114.2, 2023.36)
        else:
            scputimes = namedtuple(
                "scputimes",
                ["user", "system", "children_user", "children_system", "iowait"],
            )
            dummy_cpu_times = scputimes(7713.79, 1278.44, 17114.2, 2023.36, 0.0)
        self._cpu_times = cpu_times if cpu_times is not None else dummy_cpu_times

    def __enter__(self):
        pass

    def __exit__(self):
        pass

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

    def cpu_times(self):
        return self._cpu_times


@pytest.fixture
def mocked_proc():
    mocked_proc = MagicMock("psutil.Process")
    mocked_proc.name = Mock(return_value="test_mock_proc")
    mocked_proc.pid = Mock(return_value=9999999999)
    mocked_proc.cmdline = Mock(
        return_value=["test_mock_proc", "--arg", "--kwarg=value"]
    )

    with patch("psutil.Process.send_signal"), patch(
        "psutil.process_iter",
        MagicMock(return_value=[mocked_proc]),
    ):
        yield mocked_proc


def test__get_proc_cmdline():
    cmdline = ["echo", "питон"]
    ret = ps._get_proc_cmdline(DummyProcess(cmdline=cmdline))
    assert ret == cmdline, ret

    with patch.object(DummyProcess, "cmdline") as mock_cmdline:
        mock_cmdline.side_effect = psutil.NoSuchProcess(DummyProcess(cmdline=cmdline))
        ret = ps._get_proc_cmdline(DummyProcess(cmdline=cmdline))
        assert ret == []

    with patch.object(DummyProcess, "cmdline") as mock_cmdline:
        mock_cmdline.side_effect = psutil.AccessDenied(DummyProcess(cmdline=cmdline))
        ret = ps._get_proc_cmdline(DummyProcess(cmdline=cmdline))
        assert ret == []


def test__get_proc_create_time():
    cmdline = ["echo", "питон"]
    create_time = 1694729500.1093624
    ret = ps._get_proc_create_time(
        DummyProcess(cmdline=cmdline, create_time=create_time)
    )
    assert ret == create_time

    with patch.object(DummyProcess, "create_time") as mock_create_time:
        mock_create_time.side_effect = psutil.NoSuchProcess(
            DummyProcess(cmdline=cmdline, create_time=create_time)
        )
        ret = ps._get_proc_create_time(
            DummyProcess(cmdline=cmdline, create_time=create_time)
        )
        assert ret is None

    with patch.object(DummyProcess, "create_time") as mock_create_time:
        mock_create_time.side_effect = psutil.AccessDenied(
            DummyProcess(cmdline=cmdline, create_time=create_time)
        )
        ret = ps._get_proc_create_time(
            DummyProcess(cmdline=cmdline, create_time=create_time)
        )
        assert ret is None


def test__get_proc_name():
    cmdline = ["echo", "питон"]
    proc_name = "proc_name"
    ret = ps._get_proc_name(DummyProcess(cmdline=cmdline, name=proc_name))
    assert ret == proc_name

    with patch.object(DummyProcess, "name") as mock_name:
        mock_name.side_effect = psutil.NoSuchProcess(
            DummyProcess(cmdline=cmdline, name=proc_name)
        )
        ret = ps._get_proc_name(DummyProcess(cmdline=cmdline, name=proc_name))
        assert ret == []

    with patch.object(DummyProcess, "name") as mock_name:
        mock_name.side_effect = psutil.AccessDenied(
            DummyProcess(cmdline=cmdline, name=proc_name)
        )
        ret = ps._get_proc_name(DummyProcess(cmdline=cmdline, name=proc_name))
        assert ret == []


def test__get_proc_status():
    cmdline = ["echo", "питон"]
    proc_status = "sleeping"
    ret = ps._get_proc_status(DummyProcess(cmdline=cmdline, status=proc_status))
    assert ret == proc_status

    with patch.object(DummyProcess, "status") as mock_status:
        mock_status.side_effect = psutil.NoSuchProcess(
            DummyProcess(cmdline=cmdline, status=proc_status)
        )
        ret = ps._get_proc_status(DummyProcess(cmdline=cmdline, status=proc_status))
        assert ret is None

    with patch.object(DummyProcess, "status") as mock_status:
        mock_status.side_effect = psutil.AccessDenied(
            DummyProcess(cmdline=cmdline, status=proc_status)
        )
        ret = ps._get_proc_status(DummyProcess(cmdline=cmdline, status=proc_status))
        assert ret is None


def test__get_proc_username():
    cmdline = ["echo", "питон"]
    proc_username = "root"
    ret = ps._get_proc_username(DummyProcess(cmdline=cmdline, username=proc_username))
    assert ret == proc_username

    with patch.object(DummyProcess, "username") as mock_username:
        mock_username.side_effect = psutil.NoSuchProcess(
            DummyProcess(cmdline=cmdline, username=proc_username)
        )
        ret = ps._get_proc_username(
            DummyProcess(cmdline=cmdline, username=proc_username)
        )
        assert ret is None

    with patch.object(DummyProcess, "username") as mock_username:
        mock_username.side_effect = psutil.AccessDenied(
            DummyProcess(cmdline=cmdline, username=proc_username)
        )
        ret = ps._get_proc_username(
            DummyProcess(cmdline=cmdline, username=proc_username)
        )
        assert ret is None


def test_get_pid_list():
    with patch("psutil.pids", MagicMock(return_value=STUB_PID_LIST)):
        assert STUB_PID_LIST == ps.get_pid_list()


def test_kill_pid():
    cmdline = ["echo", "питон"]
    top_proc = DummyProcess(cmdline=cmdline)

    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = psutil.NoSuchProcess(top_proc)
        ret = ps.kill_pid(0, signal=999)
        assert not ret

    with patch("psutil.Process") as send_signal_mock:
        ps.kill_pid(0, signal=999)
        assert send_signal_mock.call_args == call(0)


def test_pkill(mocked_proc):
    mocked_proc.send_signal = MagicMock()
    test_signal = 1234
    ps.pkill(_get_proc_name(mocked_proc), signal=test_signal)
    assert mocked_proc.send_signal.call_args == call(test_signal)

    mocked_proc.send_signal = MagicMock(side_effect=psutil.NoSuchProcess(mocked_proc))
    ret = ps.pkill(_get_proc_name(mocked_proc), signal=test_signal)
    assert ret is None

    mocked_proc.username = MagicMock(return_value="root")
    with patch.object(ps, "_get_proc_username", return_value=None):
        ret = ps.pkill(_get_proc_name(mocked_proc), signal=test_signal, user="root")
    assert ret is None

    mocked_proc.username = MagicMock(return_value="root")
    ret = ps.pkill(_get_proc_name(mocked_proc), signal=test_signal, user="root")
    assert mocked_proc.send_signal.call_args == call(test_signal)


def test_pgrep(mocked_proc):
    with patch(
        "psutil.process_iter",
        MagicMock(return_value=[mocked_proc]),
    ):
        assert mocked_proc.pid in (ps.pgrep(_get_proc_name(mocked_proc)) or [])

        assert mocked_proc.pid in (
            ps.pgrep(_get_proc_name(mocked_proc), full=True) or []
        )


def test_pgrep_regex(mocked_proc):
    with patch(
        "psutil.process_iter",
        MagicMock(return_value=[mocked_proc]),
    ):
        assert mocked_proc.pid in (
            ps.pgrep("t.st_[a-z]+_proc", pattern_is_regex=True) or []
        )


def test_cpu_percent():
    with patch("psutil.cpu_percent", MagicMock(return_value=1)):
        assert ps.cpu_percent() == 1

    with patch("psutil.cpu_percent", MagicMock(return_value=(1, 1, 1, 1))):
        assert ps.cpu_percent(per_cpu=True) == [1, 1, 1, 1]

    with patch("psutil.cpu_percent", MagicMock(return_value=1)):
        assert ps.cpu_percent(per_cpu=False) == 1


def test_cpu_times():
    with patch("psutil.cpu_times", MagicMock(return_value=STUB_CPU_TIMES)):
        assert {"idle": 4, "nice": 2, "system": 3, "user": 1} == ps.cpu_times()

    with patch(
        "psutil.cpu_times",
        MagicMock(return_value=STUB_CPU_TIMES_PERCPU),
    ):
        assert [
            {"idle": 4, "nice": 2, "system": 3, "user": 1},
            {"idle": 4, "nice": 2, "system": 3, "user": 1},
            {"idle": 4, "nice": 2, "system": 3, "user": 1},
            {"idle": 4, "nice": 2, "system": 3, "user": 1},
        ] == ps.cpu_times(per_cpu=True)


def test_virtual_memory():
    with patch(
        "psutil.virtual_memory",
        MagicMock(return_value=STUB_VIRT_MEM),
    ):
        assert {
            "used": 500,
            "total": 1000,
            "available": 500,
            "percent": 50,
            "free": 500,
        } == ps.virtual_memory()


def test_swap_memory():
    with patch(
        "psutil.swap_memory",
        MagicMock(return_value=STUB_SWAP_MEM),
    ):
        assert {
            "used": 500,
            "total": 1000,
            "percent": 50,
            "free": 500,
            "sin": 0,
            "sout": 0,
        } == ps.swap_memory()


def test_disk_partitions():
    with patch(
        "psutil.disk_partitions",
        MagicMock(return_value=[STUB_DISK_PARTITION]),
    ):
        assert {
            "device": "/dev/disk0s2",
            "mountpoint": "/",
            "opts": "rw,local,rootfs,dovolfs,journaled,multilabel",
            "fstype": "hfs",
        } == ps.disk_partitions()[0]


def test_disk_usage():
    with patch(
        "psutil.disk_usage",
        MagicMock(return_value=STUB_DISK_USAGE),
    ):
        assert {
            "used": 500,
            "total": 1000,
            "percent": 50,
            "free": 500,
        } == ps.disk_usage("DUMMY_PATH")


def test_disk_partition_usage():
    with patch(
        "psutil.disk_partitions",
        MagicMock(return_value=[STUB_DISK_PARTITION]),
    ):
        with patch(
            "psutil.disk_usage",
            MagicMock(return_value=STUB_DISK_USAGE),
        ):
            result = ps.disk_partition_usage()[0]
            assert {
                "device": "/dev/disk0s2",
                "mountpoint": "/",
                "fstype": "hfs",
                "opts": "rw,local,rootfs,dovolfs,journaled,multilabel",
                "total": 1000,
                "used": 500,
                "free": 500,
                "percent": 50,
            } == result


def test_network_io_counters():
    with patch(
        "psutil.net_io_counters",
        MagicMock(return_value=STUB_NETWORK_IO),
    ):
        assert {
            "packets_sent": 500,
            "packets_recv": 600,
            "bytes_recv": 2000,
            "dropout": 4,
            "bytes_sent": 1000,
            "errout": 2,
            "errin": 1,
            "dropin": 3,
        } == ps.network_io_counters()

    with patch(
        "psutil.net_io_counters",
        MagicMock(return_value=STUB_NETWORK_IO_PERNIC),
    ):
        assert {
            "packets_sent": 500,
            "packets_recv": 600,
            "bytes_recv": 2000,
            "dropout": 4,
            "bytes_sent": 1000,
            "errout": 2,
            "errin": 1,
            "dropin": 3,
        } == ps.network_io_counters(interface="eth0")

        assert not ps.network_io_counters(interface="eth2")


def test_disk_io_counters():
    with patch(
        "psutil.disk_io_counters",
        MagicMock(return_value=STUB_DISK_IO),
    ):
        assert {
            "read_time": 2000,
            "write_bytes": 600,
            "read_bytes": 500,
            "write_time": 3000,
            "read_count": 1000,
            "write_count": 2000,
        } == ps.disk_io_counters()

    with patch(
        "psutil.disk_io_counters",
        MagicMock(return_value=STUB_DISK_IO_PERDISK),
    ):
        assert {
            "read_time": 2000,
            "write_bytes": 600,
            "read_bytes": 500,
            "write_time": 3000,
            "read_count": 1000,
            "write_count": 2000,
        } == ps.disk_io_counters(device="nvme0n1p1")

        assert not ps.disk_io_counters(device="nvme0n1p4")


def test_get_users(stub_user):
    with patch("psutil.users", MagicMock(return_value=[stub_user])):
        assert {
            "terminal": "ttys000",
            "started": 0.0,
            "host": "localhost",
            "name": "bdobbs",
        } == ps.get_users()[0]


def test_top():
    """
    See the following issue:

    https://github.com/saltstack/salt/issues/56942
    """
    # Limiting to one process because the test suite might be running as
    # PID 1 under docker and there may only *be* one process running.
    result = ps.top(num_processes=1, interval=0)
    assert len(result) == 1

    cmdline = ["echo", "питон"]
    top_proc = DummyProcess(cmdline=cmdline)

    with patch("psutil.pids", return_value=[1]):
        with patch("psutil.Process") as mock_process:
            mock_process.side_effect = psutil.NoSuchProcess(top_proc)
            ret = ps.top(num_processes=1, interval=0)
            assert ret == []

    if salt.utils.platform.is_windows():
        scputimes = namedtuple(
            "scputimes", ["user", "system", "children_user", "children_system"]
        )
        zombie_cpu_times = scputimes(0, 0, 0, 0)

        smem_info = namedtuple(
            "pmem",
            [
                "rss",
                "vms",
                "num_page_faults",
                "peak_wset",
                "wset",
                "peak_paged_pool",
                "paged_pool",
                "peak_nonpaged_pool",
                "nonpaged_pool28144",
                "pagefile",
                "peak_pagefile",
                "private",
            ],
        )
        zombie_mem_info = smem_info(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    else:
        scputimes = namedtuple(
            "scputimes",
            ["user", "system", "children_user", "children_system", "iowait"],
        )
        zombie_cpu_times = scputimes(0, 0, 0, 0, 0)

        smem_info = namedtuple(
            "pmem", ["rss", "vms", "shared", "text", "lib", "data", "dirty"]
        )
        zombie_mem_info = smem_info(0, 0, 0, 0, 0, 0, 0)

    with patch("psutil.pids", return_value=[1]):
        with patch("psutil.Process", return_value=top_proc):
            with patch.object(top_proc, "cpu_times") as mock_cpu_times:
                with patch.object(
                    top_proc, "memory_info", return_value=zombie_mem_info, create=True
                ):
                    mock_cpu_times.side_effect = [
                        psutil.ZombieProcess(top_proc),
                        zombie_cpu_times,
                        zombie_cpu_times,
                    ]
                    ret = ps.top(num_processes=1, interval=0)

                    if salt.utils.platform.is_windows():
                        expected_mem = {
                            "rss": 0,
                            "vms": 0,
                            "num_page_faults": 0,
                            "peak_wset": 0,
                            "wset": 0,
                            "peak_paged_pool": 0,
                            "paged_pool": 0,
                            "peak_nonpaged_pool": 0,
                            "nonpaged_pool28144": 0,
                            "pagefile": 0,
                            "peak_pagefile": 0,
                            "private": 0,
                        }

                        expected_cpu = {
                            "user": 0,
                            "system": 0,
                            "children_user": 0,
                            "children_system": 0,
                        }

                    else:
                        expected_mem = {
                            "rss": 0,
                            "vms": 0,
                            "shared": 0,
                            "text": 0,
                            "lib": 0,
                            "data": 0,
                            "dirty": 0,
                        }

                        expected_cpu = {
                            "user": 0,
                            "system": 0,
                            "children_user": 0,
                            "children_system": 0,
                            "iowait": 0,
                        }

                    assert ret[0]["mem"] == expected_mem
                    assert ret[0]["cpu"] == expected_cpu

    with patch("psutil.pids", return_value=[1]):
        with patch("psutil.Process", return_value=top_proc):
            with patch.object(top_proc, "cpu_times") as mock_cpu_times:
                mock_cpu_times.side_effect = [
                    top_proc._cpu_times,
                    psutil.NoSuchProcess(top_proc),
                ]
                ret = ps.top(num_processes=1, interval=0)
                assert ret == []

    with patch("psutil.pids", return_value=[1]):
        with patch("psutil.Process", return_value=top_proc):
            with patch.object(top_proc, "cpu_times") as mock_cpu_times:
                with patch.object(
                    top_proc, "memory_info", create=True
                ) as mock_memory_info:
                    mock_memory_info.side_effect = psutil.NoSuchProcess(top_proc)
                    mock_cpu_times.side_effect = [
                        psutil.ZombieProcess(top_proc),
                        zombie_cpu_times,
                        zombie_cpu_times,
                    ]
                    ret = ps.top(num_processes=1, interval=0)
                    assert ret == []


def test_top_zombie_process():
    # Get 3 pids that are currently running on the system
    pids = psutil.pids()[:3]
    # Get a process instance for each of the pids
    processes = [psutil.Process(pid) for pid in pids]

    # Patch the middle process to raise ZombieProcess when .cpu_times is called
    def raise_exception():
        raise psutil.ZombieProcess(processes[1].pid)

    processes[1].cpu_times = raise_exception

    # Make sure psutil.pids only returns the above 3 pids
    with patch("psutil.pids", return_value=pids):
        # Make sure we use our process list from above
        with patch("psutil.Process", side_effect=processes):
            result = ps.top(num_processes=1, interval=0)
            assert len(result) == 1


def test_status_when_no_status_is_provided_then_raise_invocation_error():
    with pytest.raises(SaltInvocationError):
        actual_result = salt.modules.ps.status(status="")


@pytest.mark.parametrize(
    "exc_type",
    (
        psutil.AccessDenied(pid="9999", name="whatever"),
        psutil.NoSuchProcess(pid="42"),
    ),
)
def test_status_when_access_denied_from_psutil_it_should_CommandExecutionError(
    exc_type,
):
    with patch(
        "psutil.process_iter",
        autospec=True,
        side_effect=exc_type,
    ):
        with pytest.raises(
            salt.exceptions.CommandExecutionError,
            match="Psutil did not return a list of processes",
        ):
            actual_result = salt.modules.ps.status(status="fnord")


def test_status_when_no_filter_is_provided_then_raise_invocation_error():
    with pytest.raises(SaltInvocationError) as invoc_issue:
        actual_result = salt.modules.ps.status(status="")


def test_status_when_access_denied_from_psutil_then_raise_exception():
    with patch(
        "psutil.process_iter",
        autospec=True,
        return_value=psutil.AccessDenied(pid="9999", name="whatever"),
    ):
        with pytest.raises(Exception) as general_issue:
            actual_result = salt.modules.ps.status(status="fnord")


## This is commented out pending discussion on https://github.com/saltstack/salt/commit/2e5c3162ef87cca8a2c7b12ade7c7e1b32028f0a
# @skipIf(not HAS_UTMP, "The utmp module must be installed to run test_get_users_utmp()")
# @patch('psutil.get_users', new=MagicMock(return_value=None))  # This will force the function to use utmp
# def test_get_users_utmp():
#     pass


def test_psaux():
    """
    Testing psaux function in the ps module
    """

    cmd_run_mock = """
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0 171584 15740 ?        Ss   Aug09   4:18 /usr/lib/systemd/systemd --system --deserialize=83
root           2  0.0  0.0      0     0 ?        S    Aug09   0:02 [kthreadd]
root     2710129  0.0  0.0  18000  7428 pts/4    S+   Aug21   0:33 sudo -E salt-master -l debug
root     2710131  0.0  0.0  18000  1196 pts/6    Ss   Aug21   0:00 sudo -E salt-master -l debug
"""

    with patch.dict(ps.__salt__, {"cmd.run": MagicMock(return_value=cmd_run_mock)}):
        expected = [
            "salt-master",
            [
                "root     2710129  0.0  0.0  18000  7428 pts/4    S+   Aug21   0:33 sudo -E salt-master -l debug",
                "root     2710131  0.0  0.0  18000  1196 pts/6    Ss   Aug21   0:00 sudo -E salt-master -l debug",
            ],
            "2 occurrence(s).",
        ]
        ret = ps.psaux("salt-master")
        assert ret == expected

        expected = ["salt-minion", [], "0 occurrence(s)."]
        ret = ps.psaux("salt-minion")
        assert ret == expected


@pytest.mark.skip_on_windows(reason="ss not available in Windows")
def test_ss():
    """
    Testing ss function in the ps module
    """

    cmd_run_mock = """
tcp   LISTEN     0      128                                                                               0.0.0.0:22                                            0.0.0.0:*        ino:31907 sk:364b cgroup:/system.slice/sshd.service <->

tcp   LISTEN     0      128                                                                                  [::]:22                                               [::]:*        ino:31916 sk:36c4 cgroup:/system.slice/sshd.service v6only:1 <->
"""

    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/sbin/ss")
    ), patch.dict(ps.__salt__, {"cmd.run": MagicMock(return_value=cmd_run_mock)}):
        expected = [
            "sshd",
            [
                "tcp   LISTEN     0      128                                                                               0.0.0.0:22                                            0.0.0.0:*        ino:31907 sk:364b cgroup:/system.slice/sshd.service <->",
                "tcp   LISTEN     0      128                                                                                  [::]:22                                               [::]:*        ino:31916 sk:36c4 cgroup:/system.slice/sshd.service v6only:1 <->",
            ],
        ]
        ret = ps.ss("sshd")
        assert ret == expected

        expected = ["apache2", []]
        ret = ps.ss("apache2")
        assert ret == expected


def test_netstat():
    """
    Testing netstat function in the ps module
    """

    cmd_run_mock = """
Active Internet connections (servers and established)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN      668/sshd: /usr/sbin
tcp6       0      0 :::22                   :::*                    LISTEN      668/sshd: /usr/sbin
"""

    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/netstat")):
        with patch.dict(ps.__salt__, {"cmd.run": MagicMock(return_value=cmd_run_mock)}):
            expected = [
                "sshd",
                [
                    "tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN      668/sshd: /usr/sbin",
                    "tcp6       0      0 :::22                   :::*                    LISTEN      668/sshd: /usr/sbin",
                ],
            ]
            ret = ps.netstat("sshd")
            assert ret == expected

            expected = ["apache2", []]
            ret = ps.netstat("apache2")
            assert ret == expected


def test_lsof():
    """
    Testing lsof function in the ps module
    """

    sshd_cmd_run_mock = """
COMMAND  PID USER   FD   TYPE             DEVICE SIZE/OFF    NODE NAME
sshd    1743 root  cwd    DIR              254,0     4096       2 /
sshd    1743 root  rtd    DIR              254,0     4096       2 /
sshd    1743 root  txt    REG              254,0   925000 7533685 /usr/bin/sshd (deleted)
sshd    1743 root  DEL    REG              254,0          7481413 /usr/lib/libc.so.6
sshd    1743 root  DEL    REG              254,0          7477716 /usr/lib/libcrypto.so.3
sshd    1743 root  mem    REG              254,0    26520 7482162 /usr/lib/libcap-ng.so.0.0.0
sshd    1743 root  DEL    REG              254,0          7512187 /usr/lib/libresolv.so.2
sshd    1743 root  mem    REG              254,0    22400 7481786 /usr/lib/libkeyutils.so.1.10
sshd    1743 root  mem    REG              254,0    55352 7480841 /usr/lib/libkrb5support.so.0.1
sshd    1743 root  mem    REG              254,0    18304 7475778 /usr/lib/libcom_err.so.2.1
sshd    1743 root  mem    REG              254,0   182128 7477432 /usr/lib/libk5crypto.so.3.1
sshd    1743 root  DEL    REG              254,0          7485543 /usr/lib/libaudit.so.1.0.0
sshd    1743 root  DEL    REG              254,0          7485432 /usr/lib/libz.so.1.2.13
sshd    1743 root  mem    REG              254,0   882552 7480814 /usr/lib/libkrb5.so.3.3
sshd    1743 root  mem    REG              254,0   344160 7475833 /usr/lib/libgssapi_krb5.so.2.2
sshd    1743 root  mem    REG              254,0    67536 7482132 /usr/lib/libpam.so.0.85.1
sshd    1743 root  mem    REG              254,0   165832 7481746 /usr/lib/libcrypt.so.2.0.0
sshd    1743 root  DEL    REG              254,0          7480993 /usr/lib/ld-linux-x86-64.so.2
sshd    1743 root    0r   CHR                1,3      0t0       4 /dev/null
sshd    1743 root    1u  unix 0x0000000000000000      0t0   32930 type=STREAM (CONNECTED)
sshd    1743 root    2u  unix 0x0000000000000000      0t0   32930 type=STREAM (CONNECTED)
sshd    1743 root    3u  IPv4              31907      0t0     TCP *:ssh (LISTEN)
sshd    1743 root    4u  IPv6              31916      0t0     TCP *:ssh (LISTEN)
"""

    apache2_cmd_run_mock = ""

    with patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/netstat")):
        with patch.dict(
            ps.__salt__, {"cmd.run": MagicMock(return_value=sshd_cmd_run_mock)}
        ):
            expected = [
                "sshd",
                "\nCOMMAND  PID USER   FD   TYPE             DEVICE SIZE/OFF    NODE NAME\nsshd    1743 root  cwd    DIR              254,0     4096       2 /\nsshd    1743 root  rtd    DIR              254,0     4096       2 /\nsshd    1743 root  txt    REG              254,0   925000 7533685 /usr/bin/sshd (deleted)\nsshd    1743 root  DEL    REG              254,0          7481413 /usr/lib/libc.so.6\nsshd    1743 root  DEL    REG              254,0          7477716 /usr/lib/libcrypto.so.3\nsshd    1743 root  mem    REG              254,0    26520 7482162 /usr/lib/libcap-ng.so.0.0.0\nsshd    1743 root  DEL    REG              254,0          7512187 /usr/lib/libresolv.so.2\nsshd    1743 root  mem    REG              254,0    22400 7481786 /usr/lib/libkeyutils.so.1.10\nsshd    1743 root  mem    REG              254,0    55352 7480841 /usr/lib/libkrb5support.so.0.1\nsshd    1743 root  mem    REG              254,0    18304 7475778 /usr/lib/libcom_err.so.2.1\nsshd    1743 root  mem    REG              254,0   182128 7477432 /usr/lib/libk5crypto.so.3.1\nsshd    1743 root  DEL    REG              254,0          7485543 /usr/lib/libaudit.so.1.0.0\nsshd    1743 root  DEL    REG              254,0          7485432 /usr/lib/libz.so.1.2.13\nsshd    1743 root  mem    REG              254,0   882552 7480814 /usr/lib/libkrb5.so.3.3\nsshd    1743 root  mem    REG              254,0   344160 7475833 /usr/lib/libgssapi_krb5.so.2.2\nsshd    1743 root  mem    REG              254,0    67536 7482132 /usr/lib/libpam.so.0.85.1\nsshd    1743 root  mem    REG              254,0   165832 7481746 /usr/lib/libcrypt.so.2.0.0\nsshd    1743 root  DEL    REG              254,0          7480993 /usr/lib/ld-linux-x86-64.so.2\nsshd    1743 root    0r   CHR                1,3      0t0       4 /dev/null\nsshd    1743 root    1u  unix 0x0000000000000000      0t0   32930 type=STREAM (CONNECTED)\nsshd    1743 root    2u  unix 0x0000000000000000      0t0   32930 type=STREAM (CONNECTED)\nsshd    1743 root    3u  IPv4              31907      0t0     TCP *:ssh (LISTEN)\nsshd    1743 root    4u  IPv6              31916      0t0     TCP *:ssh (LISTEN)\n",
            ]
            ret = ps.lsof("sshd")
            assert ret == expected

        with patch.dict(
            ps.__salt__, {"cmd.run": MagicMock(return_value=apache2_cmd_run_mock)}
        ):
            expected = ["apache2", ""]
            ret = ps.lsof("apache2")
            assert ret == expected


def test_boot_time():
    """
    Testing boot_time function in the ps module
    """

    with patch("psutil.boot_time", MagicMock(return_value=1691593290.0)):
        expected = 1691593290
        ret = ps.boot_time()
        assert ret == expected

        expected = "08/09/2023"
        ret = ps.boot_time(time_format="%m/%d/%Y")
        assert ret == expected

    with patch("psutil.boot_time") as mock_boot_time:
        mock_boot_time.side_effect = [AttributeError(), 1691593290.0]
        expected = 1691593290
        ret = ps.boot_time()
        assert ret == expected


def test_num_cpus():
    """
    Testing num_cpus function in the ps module
    """

    with patch("psutil.cpu_count") as mock_cpu_count:
        mock_cpu_count.side_effect = AttributeError()
        with patch("psutil.NUM_CPUS", create=True, new=5):
            ret = ps.num_cpus()
            assert ret == 5

    with patch("psutil.cpu_count") as mock_cpu_count:
        mock_cpu_count.return_value = 5
        ret = ps.num_cpus()
        assert ret == 5


def test_total_physical_memory(stub_memory_usage):
    """
    Testing total_physical_memory function in the ps module
    """
    with patch("psutil.virtual_memory") as mock_total_physical_memory:
        mock_total_physical_memory.side_effect = AttributeError()
        with patch(
            "psutil.TOTAL_PHYMEM",
            create=True,
            new=stub_memory_usage.total,
        ):
            ret = ps.total_physical_memory()
            assert ret == 15722012672

    with patch("psutil.virtual_memory") as mock_total_physical_memory:
        mock_total_physical_memory.return_value = stub_memory_usage
        ret = ps.total_physical_memory()
        assert ret == 15722012672


def test_proc_info():
    """
    Testing proc_info function in the ps module
    """
    status = b"fnord"
    extra_data = {
        "utime": "42",
        "stime": "42",
        "children_utime": "42",
        "children_stime": "42",
        "ttynr": "42",
        "cpu_time": "42",
        "blkio_ticks": "99",
        "ppid": "99",
        "cpu_num": "9999999",
    }
    important_data = {
        "name": b"blerp",
        "status": status,
        "create_time": "393829200",
        "username": "root",
    }
    important_data.update(extra_data)
    status_file = b"Name:\tblerp\nUmask:\t0000\nState:\tI (idle)\nTgid:\t99\nNgid:\t0\nPid:\t99\nPPid:\t2\nTracerPid:\t0\nUid:\t0\t0\t0\t0\nGid:\t0\t0\t0\t0\nFDSize:\t64\nGroups:\t \nNStgid:\t99\nNSpid:\t99\nNSpgid:\t0\nNSsid:\t0\nThreads:\t1\nSigQ:\t3/256078\nSigPnd:\t0000000000000000\nShdPnd:\t0000000000000000\nSigBlk:\t0000000000000000\nSigIgn:\tffffffffffffffff\nSigCgt:\t0000000000000000\nCapInh:\t0000000000000000\nCapPrm:\t000001ffffffffff\nCapEff:\t000001ffffffffff\nCapBnd:\t000001ffffffffff\nCapAmb:\t0000000000000000\nNoNewPrivs:\t0\nSeccomp:\t0\nSeccomp_filters:\t0\nSpeculation_Store_Bypass:\tthread vulnerable\nSpeculationIndirectBranch:\tconditional enabled\nCpus_allowed:\tfff\nCpus_allowed_list:\t0-11\nMems_allowed:\t00000001\nMems_allowed_list:\t0\nvoluntary_ctxt_switches:\t2\nnonvoluntary_ctxt_switches:\t0\n"

    patch_stat_file = patch(
        "psutil._psplatform.Process._parse_stat_file",
        return_value=important_data,
        create=True,
    )
    patch_exe = patch(
        "psutil._psplatform.Process.exe",
        return_value=important_data["name"].decode(),
        create=True,
    )
    patch_oneshot = patch(
        "psutil._psplatform.Process.oneshot",
        return_value={
            # These keys can be found in psutil/_psbsd.py
            1: important_data["status"].decode(),
            # create
            9: float(important_data["create_time"]),
            # user
            14: float(important_data["create_time"]),
            # sys
            15: float(important_data["create_time"]),
            # ch_user
            16: float(important_data["create_time"]),
            # ch_sys -- we don't really care what they are, obviously
            17: float(important_data["create_time"]),
            24: important_data["name"].decode(),
        },
        create=True,
    )
    patch_kinfo = patch(
        "psutil._psplatform.Process._get_kinfo_proc",
        return_value={
            # These keys can be found in psutil/_psosx.py
            9: important_data["status"].decode(),
            8: float(important_data["create_time"]),
            10: important_data["name"].decode(),
        },
        create=True,
    )
    patch_status = patch(
        "psutil._psplatform.Process.status", return_value=status.decode()
    )
    patch_create_time = patch(
        "psutil._psplatform.Process.create_time", return_value=393829200
    )
    with (
        patch_stat_file
    ), patch_status, patch_create_time, patch_exe, patch_oneshot, patch_kinfo:
        if salt.utils.platform.is_windows():
            with patch("psutil._pswindows.cext") as mock__psutil_windows:
                with patch("psutil._pswindows.Process.ppid", return_value=99):
                    mock__psutil_windows.proc_username.return_value = (
                        "NT Authority",
                        "System",
                    )

                    expected = {"ppid": 99, "username": r"NT Authority\System"}
                    actual_result = salt.modules.ps.proc_info(
                        pid=99, attrs=["username", "ppid"]
                    )
                    assert actual_result == expected

                    expected = {"pid": 99, "name": "blerp"}
                    actual_result = salt.modules.ps.proc_info(
                        pid=99, attrs=["pid", "name"]
                    )
                    assert actual_result == expected
        else:
            patch_read_status_file = patch(
                "psutil._psplatform.Process._read_status_file", return_value=status_file
            )
            with patch_read_status_file:
                expected = {"ppid": 99, "username": "root"}
                actual_result = salt.modules.ps.proc_info(
                    pid=99, attrs=["username", "ppid"]
                )
                assert actual_result == expected

                expected = {"pid": 99, "name": "blerp"}
                actual_result = salt.modules.ps.proc_info(pid=99, attrs=["pid", "name"])
                assert actual_result == expected


def test_proc_info_access_denied():
    """
    Testing proc_info function in the ps module
    when an AccessDenied exception occurs
    """
    cmdline = ["echo", "питон"]
    dummy_proc = DummyProcess(cmdline=cmdline)
    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = psutil.AccessDenied(dummy_proc)
        with pytest.raises(CommandExecutionError):
            salt.modules.ps.proc_info(pid=99, attrs=["username", "ppid"])


def test_proc_info_no_such_process():
    """
    Testing proc_info function in the ps module
    when an NoSuchProcess exception occurs
    """
    cmdline = ["echo", "питон"]
    dummy_proc = DummyProcess(cmdline=cmdline)
    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = psutil.NoSuchProcess(dummy_proc)
        with pytest.raises(CommandExecutionError):
            salt.modules.ps.proc_info(pid=99, attrs=["username", "ppid"])


def test_proc_info_attribute_error():
    """
    Testing proc_info function in the ps module
    when an AttributeError exception occurs
    """
    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = AttributeError()
        with pytest.raises(CommandExecutionError):
            salt.modules.ps.proc_info(pid=99, attrs=["username", "ppid"])


def test__virtual__no_psutil():
    """
    Test __virtual__ function
    """
    with patch.object(ps, "HAS_PSUTIL", False):
        expected = (
            False,
            "The ps module cannot be loaded: python module psutil not installed.",
        )
        result = ps.__virtual__()
    assert result == expected
