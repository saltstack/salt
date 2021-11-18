import os
import signal

import pytest
import salt.utils.vt as vt


@pytest.mark.skip_on_windows(reason="salt.utils.vt.Terminal doesn't have _spawn.")
def test_isalive_no_child():
    term = vt.Terminal(
        "for i in {1..9}; do echo $i;sleep $i; done",
        shell=True,
        stream_stdout=False,
        stream_stderr=False,
    )

    # make sure we have a valid term before we kill the term
    # commenting out for now, terminal seems to be stopping before this point
    assert term.exitstatus is None
    assert term.isalive() is True
    # use a large hammer to make sure pid is really dead which will cause it to
    # raise an exception that we want to test for.
    os.kill(term.pid, signal.SIGKILL)
    os.waitpid(term.pid, 0)
    assert term.exitstatus == 0
    assert term.isalive() is False
