import logging
import os
import signal

import pytest

import salt.utils.vt as vt


@pytest.mark.skip_on_windows(reason="salt.utils.vt.Terminal doesn't have _spawn.")
def test_isalive_no_child():
    term = vt.Terminal(
        "sleep 100",
        shell=True,
        stream_stdout=False,
        stream_stderr=False,
    )

    # make sure we have a valid term before we kill the term
    # commenting out for now, terminal seems to be stopping before this point
    aliveness = term.isalive()
    assert term.exitstatus is None
    assert aliveness is True
    # use a large hammer to make sure pid is really dead which will cause it to
    # raise an exception that we want to test for.
    os.kill(term.pid, signal.SIGKILL)
    os.waitpid(term.pid, 0)
    aliveness = term.isalive()
    assert term.exitstatus == 0
    assert aliveness is False


@pytest.mark.parametrize("test_cmd", ["echo", "ls"])
@pytest.mark.skip_on_windows()
def test_log_sanitize(test_cmd, caplog):
    """
    test when log_sanitize is passed in
    we do not see the password in either
    standard out or standard error logs
    """
    password = "123456"
    cmd = [test_cmd, password]
    term = vt.Terminal(
        cmd,
        log_stdout=True,
        log_stderr=True,
        log_stdout_level="debug",
        log_stderr_level="debug",
        log_sanitize=password,
        stream_stdout=False,
        stream_stderr=False,
    )
    with caplog.at_level(logging.DEBUG):
        term.recv()
    assert password not in caplog.text
    assert "******" in caplog.text
