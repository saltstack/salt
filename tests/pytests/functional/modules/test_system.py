import datetime
import logging
import os
import shutil
import signal
import subprocess
import textwrap
import time

import pytest

import salt.utils.files
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.skip_unless_on_linux,
    pytest.mark.slow_test,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def cmdmod(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def grains(modules):
    return modules.grains


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(scope="module")
def service(modules):
    return modules.service


@pytest.fixture(scope="module")
def system(modules):
    return modules.system


@pytest.fixture(scope="function")
def fmt_str():
    return "%Y-%m-%d %H:%M:%S"


@pytest.fixture(scope="function")
def setup_teardown_vars(file, service, system):
    _orig_time = datetime.datetime.utcnow()

    if os.path.isfile("/etc/machine-info"):
        with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
            _machine_info = mach_info.read()
    else:
        _machine_info = False

    try:
        _systemd_timesyncd_available_ = service.available("systemd-timesyncd")
        if _systemd_timesyncd_available_:
            res = service.stop("systemd-timesyncd")
            assert res

        yield _orig_time

    finally:
        _restore_time(system, _orig_time)

        if _machine_info is not False:
            with salt.utils.files.fopen("/etc/machine-info", "w") as mach_info:
                mach_info.write(_machine_info)
        else:
            file.remove("/etc/machine-info")

        if _systemd_timesyncd_available_:
            try:
                res = service.start("systemd-timesyncd")
            except CommandExecutionError:
                # We possibly did too many restarts in too short time
                # Wait 10s (default systemd timeout) and try again
                time.sleep(10)
                res = service.start("systemd-timesyncd")
            assert res


def _set_time(system, new_time, offset=None):
    t = new_time.timetuple()[:6]
    t += (offset,)
    return system.set_system_date_time(*t)


def _restore_time(system, _orig_time):
    result = _set_time(system, _orig_time, "+0000")
    assert result, "Unable to restore time properly"


def _same_times(t1, t2, seconds_diff=30):
    """
    Helper function to check if two datetime objects
    are close enough to the same time.
    """
    return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)


@pytest.fixture(scope="module")
def hwclock_has_compare(cmdmod):
    """
    Some builds of hwclock don't include the `--compare` function
    needed to test hw/sw clock synchronization. Returns false on
    systems where it's not present so that we can skip the
    comparison portion of the test.
    """
    hwclock = shutil.which("hwclock")
    if hwclock is None:
        pytest.skip("The 'hwclock' binary could not be found")
    res = cmdmod.run_all(cmd="hwclock -h")
    _hwclock_has_compare_ = res["retcode"] == 0 and res["stdout"].find("--compare") > 0
    return _hwclock_has_compare_


def _test_hwclock_sync(system, hwclock_has_compare):
    """
    Check that hw and sw clocks are sync'd.
    """
    if not system.has_settable_hwclock():
        return None
    if not hwclock_has_compare:
        return None

    class CompareTimeout(BaseException):
        pass

    def _alrm_handler(sig, frame):
        log.warning("hwclock --compare failed to produce output after 3 seconds")
        raise CompareTimeout

    for _ in range(2):
        orig_handler = signal.signal(signal.SIGALRM, _alrm_handler)
        try:
            signal.alarm(3)
            rpipeFd, wpipeFd = os.pipe()
            log.debug("Comparing hwclock to sys clock")
            with os.fdopen(rpipeFd, "r") as rpipe:
                with os.fdopen(wpipeFd, "w"):
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


def test_get_system_date_time(setup_teardown_vars, system, fmt_str):
    """
    Test we are able to get the correct time
    """
    t1 = datetime.datetime.now()
    res = system.get_system_date_time()
    t2 = datetime.datetime.strptime(res, fmt_str)
    msg = f"Difference in times is too large. Now: {t1} Fake: {t2}"
    assert _same_times(t1, t2, seconds_diff=3), msg


def test_get_system_date_time_utc(setup_teardown_vars, system, fmt_str):
    """
    Test we are able to get the correct time with utc
    """
    t1 = datetime.datetime.utcnow()
    res = system.get_system_date_time("+0000")
    t2 = datetime.datetime.strptime(res, fmt_str)
    msg = f"Difference in times is too large. Now: {t1} Fake: {t2}"
    assert _same_times(t1, t2, seconds_diff=3), msg


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time(setup_teardown_vars, system, hwclock_has_compare):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)
    result = _set_time(system, cmp_time)

    time_now = datetime.datetime.now()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utc(setup_teardown_vars, system, hwclock_has_compare):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    result = _set_time(system, cmp_time, offset="+0000")

    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utcoffset_east(
    setup_teardown_vars, system, hwclock_has_compare
):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    # 25200 seconds = 7 hours
    time_to_set = cmp_time - datetime.timedelta(seconds=25200)
    result = _set_time(system, time_to_set, offset="-0700")
    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date_time_utcoffset_west(
    setup_teardown_vars, system, hwclock_has_compare
):
    """
    Test changing the system clock. We are only able to set it up to a
    resolution of a second so this test may appear to run in negative time.
    """
    cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    # 7200 seconds = 2 hours
    time_to_set = cmp_time + datetime.timedelta(seconds=7200)
    result = _set_time(system, time_to_set, offset="+0200")
    time_now = datetime.datetime.utcnow()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )
    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.flaky(max_runs=4)
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_time(setup_teardown_vars, system, hwclock_has_compare):
    """
    Test setting the system time without adjusting the date.
    """
    cmp_time = datetime.datetime.now().replace(hour=10, minute=5, second=0)

    result = system.set_system_time("10:05:00")

    time_now = datetime.datetime.now()
    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )

    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_on_env("ON_DOCKER", eq="1")
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_system_date(setup_teardown_vars, system, hwclock_has_compare):
    """
    Test setting the system date without adjusting the time.
    """
    cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)

    result = system.set_system_date(cmp_time.strftime("%Y-%m-%d"))

    time_now = datetime.datetime.now()

    msg = "Difference in times is too large. Now: {} Fake: {}".format(
        time_now, cmp_time
    )

    assert result
    assert _same_times(time_now, cmp_time), msg
    _test_hwclock_sync(system, hwclock_has_compare)


@pytest.mark.skip_if_not_root
def test_get_computer_desc(setup_teardown_vars, system, cmdmod):
    """
    Test getting the system hostname
    """
    res = system.get_computer_desc()

    hostname_cmd = salt.utils.path.which("hostnamectl")
    if hostname_cmd:
        desc = cmdmod.run("hostnamectl status --pretty")
        assert res == desc
    else:
        if not os.path.isfile("/etc/machine-info"):
            assert not res
        else:
            with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
                data = mach_info.read()
                assert res in data.decode("string_escape")


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_computer_desc(setup_teardown_vars, system):
    """
    Test setting the computer description
    """
    desc = "test"
    ret = system.set_computer_desc(desc)
    computer_desc = system.get_computer_desc()

    assert ret
    assert desc in computer_desc


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_set_computer_desc_multiline(setup_teardown_vars, system):
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
    ret = system.set_computer_desc(desc)
    computer_desc = salt.utils.stringutils.to_unicode(system.get_computer_desc())

    assert ret
    assert desc in computer_desc


@pytest.mark.skip_if_not_root
def test_has_hwclock(setup_teardown_vars, system, grains, hwclock_has_compare):
    """
    Verify platform has a settable hardware clock, if possible.
    """
    if grains.get("os_family") == "NILinuxRT":
        assert system._has_settable_hwclock()
        assert hwclock_has_compare(system)
