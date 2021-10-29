import os
import signal

import salt.utils.vt as vt


def test_isalive_no_child():
    term = vt.Terminal(
        "echo 'Alive'", shell=True, stream_stdout=False, stream_stderr=False
    )
    buffer_o = buffer_e = ""
    assert term.isalive() is True
    # use a large hammer to make sure pid is really dead which will cause it to
    # raise an exception that wewant to test for.
    os.kill(term.pid, signal.SIGKILL)
    os.waitpid(term.pid, 0)
    assert term.isalive() is False
