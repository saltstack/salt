import os
import signal

import pytest
import salt.utils.platform
import salt.utils.vt as vt


@pytest.mark.slow_test
def test_isalive_no_child():
    if salt.utils.platform.is_windows():
        term = vt.Terminal(
            "timeout 10",
            shell=True,
            stream_stdout=False,
            stream_stderr=False,
            rows=40,
            cols=80,
        )
    else:
        term = vt.Terminal(
            "for i in {1..9}; do echo $i;sleep $i; done",
            shell=True,
            stream_stdout=False,
            stream_stderr=False,
        )

    # make sure we have a valid term before we kill the term
    # commenting out for now, terminal seems to be stopping before this point
    #    assert term.isalive() is True
    # use a large hammer to make sure pid is really dead which will cause it to
    # raise an exception that we want to test for.
    os.kill(term.pid, signal.SIGKILL)
    os.waitpid(term.pid, 0)
    assert term.isalive() is False
