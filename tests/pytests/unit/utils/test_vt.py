import logging
import os
import signal

import pytest

import salt.utils.vt as vt
from tests.support.mock import patch


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


@pytest.mark.skip_on_windows(reason="setwinsize/getwinsize are POSIX-only.")
def test_setwinsize_passes_termios_constant_unchanged():
    """
    Regression test for #69705.

    ``setwinsize`` used to sign-flip the macOS value of ``TIOCSWINSZ``
    (``2148037735``) to a negative int (``-2146929561``) as a workaround
    for an old CPython signed-cast quirk. Python 3.14 rejects negative
    ``request`` arguments to ``fcntl.ioctl`` outright, which broke
    ``salt-ssh`` on the 3008.x macOS onedir because ``setwinsize`` runs
    inside the ``preexec_fn`` of every spawned pty child.

    The fix is to pass ``termios.TIOCSWINSZ`` through untouched. This
    test simulates the macOS constant and asserts the value handed to
    ``fcntl.ioctl`` matches ``termios.TIOCSWINSZ`` exactly (and is not
    negative).
    """
    mac_tiocswinsz = 2148037735
    captured = []

    def fake_ioctl(fd, req, packed):
        captured.append(req)
        return b"\x00" * 8

    with patch.object(
        vt.termios, "TIOCSWINSZ", mac_tiocswinsz, create=True
    ), patch.object(vt.fcntl, "ioctl", side_effect=fake_ioctl):
        vt.setwinsize(0, 24, 80)

    assert captured, "fcntl.ioctl was not called"
    assert captured[0] == mac_tiocswinsz, (
        f"setwinsize passed {captured[0]!r} to fcntl.ioctl; expected "
        f"{mac_tiocswinsz!r} (termios.TIOCSWINSZ, unchanged). Python 3.14 "
        "rejects negative ioctl request values."
    )
    assert captured[0] > 0, "ioctl request must not be negative on Python 3.14+"


@pytest.mark.skip_on_windows(reason="setwinsize/getwinsize are POSIX-only.")
def test_getwinsize_passes_termios_constant_unchanged():
    """
    Regression test for #69705 (``getwinsize`` companion).

    ``getwinsize`` had a similar hard-coded negative fallback for
    ``TIOCGWINSZ``. Make sure the ``termios`` constant is passed to
    ``fcntl.ioctl`` unchanged, so no negative value can reach the kernel
    on Python 3.14+.
    """
    import struct as _struct
    import termios as _termios

    captured = []

    def fake_ioctl(fd, req, packed):
        captured.append(req)
        return _struct.pack(b"HHHH", 24, 80, 0, 0)

    with patch.object(vt.fcntl, "ioctl", side_effect=fake_ioctl):
        vt.getwinsize(0)

    assert captured, "fcntl.ioctl was not called"
    assert captured[0] == _termios.TIOCGWINSZ, (
        f"getwinsize passed {captured[0]!r} to fcntl.ioctl; expected "
        f"{_termios.TIOCGWINSZ!r} (termios.TIOCGWINSZ, unchanged)."
    )
    assert captured[0] > 0, "ioctl request must not be negative on Python 3.14+"


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
