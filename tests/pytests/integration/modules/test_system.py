import datetime
import logging
import os
import signal
import subprocess
import textwrap

import pytest

import salt.states.file
import salt.utils.files
import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="Skip system functions on Windows"),
]


@pytest.fixture(scope="function")
def fmt_str():
    return "%Y-%m-%d %H:%M:%S"


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    _orig_time = datetime.datetime.utcnow()

    if os.path.isfile("/etc/machine-info"):
        with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
            _machine_info = mach_info.read()
    else:
        _machine_info = False

    try:
        _systemd_timesyncd_available_ = salt_call_cli.run(
            "service.available", ["systemd-timesyncd"]
        )
        if _systemd_timesyncd_available_.data:
            res = salt_call_cli.run("service.stop", "systemd-timesyncd")

        yield _orig_time

    finally:
        _restore_time(salt_call_cli, _orig_time)

        if _machine_info is not False:
            with salt.utils.files.fopen("/etc/machine-info", "w") as mach_info:
                mach_info.write(_machine_info)
        else:
            salt_call_cli.run("file.remove", ["/etc/machine-info"])

        if _systemd_timesyncd_available_.data:
            data = salt_call_cli.run("service.start", "systemd-timesyncd")


def _set_time(salt_call_cli, new_time, offset=None):
    t = new_time.timetuple()[:6]
    t += (offset,)
    return salt_call_cli.run("system.set_system_date_time", *t)


def _restore_time(salt_call_cli, _orig_time):
    result = _set_time(salt_call_cli, _orig_time, "'+0000'")
    assert result, "Unable to restore time properly"


def _same_times(t1, t2, seconds_diff=30):
    """
    Helper function to check if two datetime objects
    are close enough to the same time.
    """
    return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)


def _hwclock_has_compare(salt_call_cli):
    """
    Some builds of hwclock don't include the `--compare` function
    needed to test hw/sw clock synchronization. Returns false on
    systems where it's not present so that we can skip the
    comparison portion of the test.
    """
    res = salt_call_cli.run("cmd.run_all", cmd="hwclock -h")
    _hwclock_has_compare_ = (
        res.data["retcode"] == 0 and res.data["stdout"].find("--compare") > 0
    )
    return _hwclock_has_compare_


def _test_hwclock_sync(salt_call_cli):
    """
    Check that hw and sw clocks are sync'd.
    """
    if not salt_call_cli.run("system.has_settable_hwclock"):
        return None
    if not _hwclock_has_compare(salt_call_cli):
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

                        assert diff <= 2.0, "hwclock difference too big: " + str(
                            timeCompStr
                        )
                        break
        except CompareTimeout:
            p.terminate()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, orig_handler)
    else:
        log.error("Failed to check hwclock sync")


def test_get_system_date_time(setup_teardown_vars, salt_call_cli, fmt_str):
    """
    Test we are able to get the correct time
    """
    t1 = datetime.datetime.now()
    res = salt_call_cli.run("system.get_system_date_time")
    t2 = datetime.datetime.strptime(res.data, fmt_str)
    msg = "Difference in times is too large. Now: {} Fake: {}".format(t1, t2)
    assert _same_times(t1, t2, seconds_diff=3)


def test_get_system_date_time_utc(setup_teardown_vars, salt_call_cli, fmt_str):
    """
    Test we are able to get the correct time with utc
    """
    t1 = datetime.datetime.utcnow()
    res = salt_call_cli.run("system.get_system_date_time", "'+0000'")
    t2 = datetime.datetime.strptime(res.data, fmt_str)
    msg = "Difference in times is too large. Now: {} Fake: {}".format(t1, t2)
    assert _same_times(t1, t2, seconds_diff=3)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time(setup_teardown_vars, salt_call_cli):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)
    result = _set_time(salt_call_cli, cmp_time)

    time_now = datetime.datetime.now()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utc(setup_teardown_vars, salt_call_cli):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    result = _set_time(salt_call_cli, cmp_time, offset="'+0000'")
    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utcoffset_east(setup_teardown_vars, salt_call_cli):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    # 25200 seconds = 7 hours
    time_to_set = cmp_time - datetime.timedelta(seconds=25200)
    result = _set_time(salt_call_cli, time_to_set, offset="'-0700'")
    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utcoffset_west(setup_teardown_vars, salt_call_cli):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    # 7200 seconds = 2 hours
    time_to_set = cmp_time + datetime.timedelta(seconds=7200)
    result = _set_time(salt_call_cli, time_to_set, offset="'+0200'")
    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.flaky(max_runs=4)
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_time(setup_teardown_vars, salt_call_cli):
    """
    Test setting the system time without adjusting the date.
    """
    cmp_time = datetime.datetime.now().replace(hour=10, minute=5, second=0)

    result = salt_call_cli.run("system.set_system_time", "'10:05:00'")

    time_now = datetime.datetime.now()
    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )

    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date(setup_teardown_vars, salt_call_cli):
    """
    Test setting the system date without adjusting the time.
    """
    cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)

    result = salt_call_cli.run("system.set_system_date", cmp_time.strftime("%Y-%m-%d"))

    time_now = datetime.datetime.now()
    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )

    assert result
    assert _same_times(time_now, cmp_time)
    _test_hwclock_sync(salt_call_cli)


@pytest.mark.skip_if_not_root
def test_get_computer_desc(setup_teardown_vars, salt_call_cli):
    """
    Test getting the system hostname
    """
    res = salt_call_cli.run("system.get_computer_desc")

    hostname_cmd = salt.utils.path.which("hostnamectl")
    if hostname_cmd:
        desc = salt_call_cli.run("cmd.run", ["hostnamectl status --pretty"])
        assert res.data == desc.data
    else:
        if not os.path.isfile("/etc/machine-info"):
            assert not res.data
        else:
            with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
                data = mach_info.read()
                assert res.data in data.decode("string_escape")


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_computer_desc(setup_teardown_vars, salt_call_cli):
    """
    Test setting the computer description
    """
    desc = "test"
    ret = salt_call_cli.run("system.set_computer_desc", desc)
    computer_desc = salt_call_cli.run("system.get_computer_desc")

    assert ret.data
    assert desc in computer_desc.data


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_computer_desc_multiline(setup_teardown_vars, salt_call_cli):
    """
    Test setting the computer description with a multiline string with tabs
    and double-quotes.
    """
    desc = textwrap.dedent(
        '''\
        'First Line
        \tSecond Line: 'single-quoted string'
        \t\tThird Line: "double-quoted string with unicode: питон"'''
    )
    ret = salt_call_cli.run("system.set_computer_desc", desc)
    computer_desc = salt.utils.stringutils.to_unicode(
        salt_call_cli.run("system.get_computer_desc").data
    )

    assert ret.data
    assert desc in computer_desc


@pytest.mark.skip_if_not_root
def test_has_hwclock(setup_teardown_vars, salt_call_cli):
    """
    Verify platform has a settable hardware clock, if possible.
    """
    if salt_call_cli.run("grains.get", ["os_family"]) == "NILinuxRT":
        assert salt_call_cli.run("system._has_settable_hwclock")
        assert _hwclock_has_compare(salt_call_cli)
