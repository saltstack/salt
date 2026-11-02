"""
    Test cases for salt.modules.status
"""

import asyncio
import os

import pytest

import salt.modules.status as status
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mock import AsyncMock, MagicMock, Mock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {status: {}}


@pytest.fixture
def master_ping(monkeypatch):
    opts = {
        "id": "ping-test",
        "master": "current-master",
        "master_ip": "192.0.2.1",
        "auth_timeout": 0.1,
    }
    channel = MagicMock()
    channel.loops = []
    channel.closed = False

    async def send(*args, **kwargs):
        channel.loops.append(asyncio.get_running_loop())
        return channel.reply

    async def enter():
        return channel

    async def exit_(*args):
        await asyncio.sleep(0)
        channel.closed = True

    channel.send = AsyncMock(side_effect=send)
    channel.__aenter__ = AsyncMock(side_effect=enter)
    channel.__aexit__ = AsyncMock(side_effect=exit_)
    factory = MagicMock(return_value=channel)
    event = MagicMock()
    event.__enter__.return_value = event
    event_factory = MagicMock(return_value=event)
    resolver = MagicMock(return_value={"master_ip": "127.0.0.1"})
    monkeypatch.setattr(status, "__opts__", opts)
    monkeypatch.setattr(salt.minion, "prep_ip_port", MagicMock(return_value={}))
    monkeypatch.setattr(salt.minion, "resolve_dns", resolver)
    monkeypatch.setattr(salt.channel.client.AsyncReqChannel, "factory", factory)
    monkeypatch.setattr(salt.utils.event, "get_event", event_factory)

    async def fire_event(*args, **kwargs):
        assert channel.closed
        assert channel.loops == [asyncio.get_running_loop()] * len(channel.loops)
        return True

    event.fire_event_async = AsyncMock(side_effect=fire_event)
    return opts, channel, factory, event, resolver


@pytest.mark.parametrize("reply", [True, False, None])
async def test_ping_master_waits_for_request_and_cleanup_before_firing_failback(
    master_ping, reply
):
    opts, channel, factory, event, _ = master_ping
    channel.reply = reply
    assert await status.ping_master("preferred-master") is True
    channel.send.assert_awaited_once_with({"cmd": "ping"}, tries=0, timeout=0.1)
    assert channel.closed
    event.fire_event_async.assert_awaited_once_with(
        {"master": "preferred-master"}, salt.minion.master_event(type="failback")
    )
    assert factory.call_args.args[0]["master"] == "preferred-master"
    assert factory.call_args.args[0]["master_ip"] == "127.0.0.1"
    assert factory.call_args.kwargs == {"crypt": "clear"}
    assert opts["master"] == "current-master"
    assert opts["master_ip"] == "192.0.2.1"


@pytest.mark.parametrize("master", [None, ""])
async def test_ping_master_invalid_master_does_not_create_a_channel(
    master_ping, master
):
    _, _, factory, event, _ = master_ping
    assert await status.ping_master(master) is False
    factory.assert_not_called()
    event.fire_event_async.assert_not_awaited()


async def test_ping_master_dns_failure_does_not_create_a_channel(master_ping):
    _, _, factory, event, resolver = master_ping
    resolver.side_effect = OSError("cannot resolve master")
    assert await status.ping_master("preferred-master") is False
    factory.assert_not_called()
    event.fire_event_async.assert_not_awaited()


async def test_ping_master_request_failure_closes_channel_without_failback(master_ping):
    _, channel, _, event, _ = master_ping
    channel.send.side_effect = OSError("master unavailable")
    assert await status.ping_master("preferred-master") is False
    assert channel.closed
    event.fire_event_async.assert_not_awaited()


async def test_ping_master_request_deadline_includes_connecting_and_closes_channel(
    master_ping,
):
    _, channel, _, event, _ = master_ping
    cancelled = []

    async def send(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    channel.send.side_effect = send
    assert await status.ping_master("preferred-master") is False
    assert cancelled == [True]
    assert channel.closed
    event.fire_event_async.assert_not_awaited()


async def test_ping_master_uses_callers_loop_across_requests(master_ping):
    _, channel, _, _, _ = master_ping
    for _ in range(3):
        assert await status.ping_master("preferred-master") is True
    assert len(channel.loops) == 3
    assert len({id(loop) for loop in channel.loops}) == 1


async def test_ping_master_cancellation_closes_channel_without_failback(master_ping):
    _, channel, _, event, _ = master_ping
    started = asyncio.Event()

    async def send(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    channel.send.side_effect = send
    task = asyncio.create_task(status.ping_master("preferred-master"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert channel.closed
    event.fire_event_async.assert_not_awaited()


async def test_ping_master_awaits_request_without_blocking_callers_loop(master_ping):
    _, channel, _, event, _ = master_ping
    started = asyncio.Event()
    release = asyncio.Event()

    async def send(*args, **kwargs):
        started.set()
        await release.wait()
        return True

    channel.send.side_effect = send
    task = asyncio.create_task(status.ping_master("preferred-master"))
    try:
        await started.wait()
        assert not task.done()
        release.set()
        assert await task is True
        assert channel.closed
        event.fire_event_async.assert_awaited_once()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_boot_time_aix():
    mock = Mock()

    mock.return_value = {"stdout": "7-20:46:46", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 679606

    mock.return_value = {"stdout": "20:46:46", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 74806

    mock.return_value = {"stdout": "   01:32:37", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 5557

    mock.return_value = {"stdout": "00:12", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 12

    mock.return_value = {"stdout": "foo", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            status._get_boot_time_aix()

    mock.return_value = {"stdout": "", "retcode": 1}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            status._get_boot_time_aix()


def test_custom():
    mock = MagicMock()
    mock2 = MagicMock()

    mock.return_value = {
        "days": 2,
        "seconds": 249719,
        "since_iso": "2023-02-27T06:19:01.590002",
        "since_t": 1677478741,
        "time": "21:21",
        "users": 2,
    }
    # test pass correct info with correct config
    mock2.return_value = {"status.uptime.custom": ["days"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {"days": 2}

    # test pass correct info with incorrect config
    mock2.return_value = {"status.fail.custom": ["days"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {}

    # test incorrect info with correct config
    mock2.return_value = {"status.uptime.custom": ["day"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {"day": "UNKNOWN"}


def _set_up_test_uptime():
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


def _set_up_test_uptime_sunos():
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


def test_uptime_linux():
    """
    Test modules.status.uptime function for Linux
    """
    m = _set_up_test_uptime()

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
        proc_uptime = salt.utils.stringutils.to_str(f"{m.ut} {m.idle}")

        with patch("salt.utils.files.fopen", mock_open(read_data=proc_uptime)):
            ret = status.uptime()
            assert ret == m.ret
        with patch("os.path.exists", MagicMock(return_value=False)):
            with pytest.raises(CommandExecutionError):
                status.uptime()


def test_uptime_sunos():
    """
    Test modules.status.uptime function for SunOS
    """
    m = _set_up_test_uptime()
    m2 = _set_up_test_uptime_sunos()
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
        assert ret == m.ret


def test_uptime_macos():
    """
    Test modules.status.uptime function for macOS
    """
    m = _set_up_test_uptime()

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
        assert ret == m.ret

        with patch.dict(status.__salt__, {"sysctl.get": MagicMock(return_value="")}):
            with pytest.raises(CommandExecutionError):
                status.uptime()


def test_uptime_return_success_not_supported():
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
        with pytest.raises(CommandExecutionError):
            with patch.dict(status.__salt__, {"cmd.run": exc_mock}):
                status.uptime()


def _set_up_test_cpustats_openbsd():
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


def test_cpustats_openbsd():
    """
    Test modules.status.cpustats function for OpenBSD
    """
    m = _set_up_test_cpustats_openbsd()

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
        assert ret == m.ret


def _set_up_test_cpuinfo_bsd():
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


def test_cpuinfo_freebsd():
    m = _set_up_test_cpuinfo_bsd()
    sysctl = "hw.model:Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu:4"

    with patch.dict(status.__grains__, {"kernel": "FreeBSD"}):
        with patch.dict(status.__salt__, {"cmd.run": MagicMock(return_value=sysctl)}):
            ret = status.cpuinfo()
            assert ret == m.ret


def test_cpuinfo_openbsd():
    m = _set_up_test_cpuinfo_bsd()
    sysctl = "hw.model=Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu=4"

    for bsd in ["NetBSD", "OpenBSD"]:
        with patch.dict(status.__grains__, {"kernel": bsd}):
            with patch.dict(
                status.__salt__, {"cmd.run": MagicMock(return_value=sysctl)}
            ):
                ret = status.cpuinfo()
                assert ret == m.ret


def _set_up_test_meminfo_openbsd():
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


def test_meminfo_openbsd():
    m = _set_up_test_meminfo_openbsd()
    vmstat = (
        " procs    memory       page                    disks    traps         "
        " cpu\n r   s   avm     fre  flt  re  pi  po  fr  sr cd0 sd0  int   sys  "
        " cs us sy id\n 2 103  355M    305M  845   1   2   3   4   5   0   1   21  "
        " 682   86  1  1 98"
    )

    with patch.dict(status.__grains__, {"kernel": "OpenBSD"}):
        with patch.dict(status.__salt__, {"cmd.run": MagicMock(return_value=vmstat)}):
            ret = status.meminfo()
            assert ret == m.ret


def _set_up_test_w_linux():
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


def _set_up_test_w_bsd():
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


def test_w_linux():
    m = _set_up_test_w_linux()
    w_output = "root   pts/1  13:42    0s  0.24s  0.16s nmap -sV 10.2.2.2"

    with patch.dict(status.__grains__, {"kernel": "Linux"}):
        with patch.dict(status.__salt__, {"cmd.run": MagicMock(return_value=w_output)}):
            ret = status.w()
            assert ret == m.ret


def test_w_bsd():
    m = _set_up_test_w_bsd()
    w_output = "root   p1 10.2.2.1    1:42PM  0 nmap -sV 10.2.2.2"

    for bsd in ["Darwin", "FreeBSD", "OpenBSD"]:
        with patch.dict(status.__grains__, {"kernel": bsd}):
            with patch.dict(
                status.__salt__, {"cmd.run": MagicMock(return_value=w_output)}
            ):
                ret = status.w()
                assert ret == m.ret


def _set_up_test_status_pid_linux():
    class MockData:
        """
        Store mock data
        """

    m = MockData()
    m.ret = "2701\n7539\n7540\n7542\n7623"
    return m


def test_status_diskusage_not_exist():
    with patch("os.path.exists", return_value=False):
        assert status.diskusage("/foo/bar/not-existing/") == {}


@pytest.mark.skip_on_windows(reason="This module is not available on Windows")
def test_status_diskusage_valid_output():
    class MockData:
        f_bsize = 8
        f_bavail = 10
        f_blocks = 50

    with patch("os.path.exists", return_value=True), patch(
        "os.statvfs", return_value=MockData()
    ):
        assert status.diskusage("/foo/bar/existing/") == {
            "/foo/bar/existing/": {"available": 80, "total": 400}
        }


@pytest.mark.skip_on_windows(reason="This module is not available on Windows")
def test_status_diskusage_exception_raised():
    with patch("os.path.exists", return_value=True), patch(
        "os.statvfs", side_effect=OSError()
    ), patch("salt.modules.status.log") as log_mock:
        assert status.diskusage("/foo/bar/exception/") == {
            "/foo/bar/exception/": {"available": None, "total": None}
        }
        assert log_mock.warning.called


def test_status_pid_linux():
    m = _set_up_test_status_pid_linux()
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
                assert ret == m.ret
