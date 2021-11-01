import os
import signal
import time

import pytest
import salt.utils.platform
import salt.utils.vt as vt


@pytest.mark.slow_test
def test_isalive_no_child():
    if salt.utils.platform.is_windows():
        cmd = "timeout 10"
    else:
        cmd = "for i in {1..9}; do echo $i;sleep $i; done"

    term = vt.Terminal(
        args=[cmd],
        shell=True,
        stream_stdout=False,
        stream_stderr=False,
    )
    time.sleep(1)
    # make sure we have a valid term before we kill the term
    assert term.isalive() is True
    # use a large hammer to make sure pid is really dead which will cause it to
    # raise an exception that wewant to test for.
    os.kill(term.pid, signal.SIGKILL)
    os.waitpid(term.pid, 0)
    assert term.isalive() is False
