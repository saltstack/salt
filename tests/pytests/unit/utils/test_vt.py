
import os
import signal
import pytests

import salt.utils.vt as vt


def test_isalive_no_child():
    term = vt.Terminal("echo 'Alive'", shell=True, stream_stdout=False, stream_stderr=False)
    buffer_o = buffer_e = ""
    assert term.isalive() == True
    os.kill(term.pid,signal.SIGKILL)
    os.waitpid(term.pid,0)
    assert term.isalive() == False
