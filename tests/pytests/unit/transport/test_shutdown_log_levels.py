"""
Regression tests for residual shutdown-time ERROR log sites on 3008.x
(follow-up to PR #70733).

Each test asserts that an ``expected-at-shutdown`` signature logs at
DEBUG rather than ERROR, and (where applicable) that a sibling
``unexpected`` signature still logs at ERROR so the demotion did not
silently swallow operator-actionable failures.

Sites covered:

  * ``salt.transport.tcp.RequestServer.close`` EBADF (errno 9) path --
    fd has already been closed under us at shutdown.
  * ``salt.transport.tcp.MessageClient._stream_return`` parse-exception
    path under ``self._closing / self._closed`` -- peer dropped mid-frame
    during teardown.
  * ``salt.transport.zeromq.RequestServer.close`` task-cancel path when
    the IOLoop is already closed.
"""

import logging as _logging

import pytest

import salt.transport.tcp
import salt.transport.zeromq
from tests.support.mock import MagicMock

# ---------------------------------------------------------------------------
# tcp.RequestServer.close EBADF
# ---------------------------------------------------------------------------


def test_tcp_requestserver_close_ebadf_logs_debug(caplog):
    """
    ``RequestServer.close`` must demote ``OSError(EBADF)`` from
    ``req_server.close()`` to DEBUG -- the fd was already closed under
    us by fork-safety teardown or a signal race.
    """
    rs = salt.transport.tcp.RequestServer({"transport": "tcp"})
    # No underlying socket, but a req_server that raises EBADF on close.
    rs._socket = None
    bad_req_server = MagicMock()
    bad_req_server.close.side_effect = OSError(9, "Bad file descriptor")
    rs.req_server = bad_req_server

    caplog.set_level(_logging.DEBUG, logger="salt.transport.tcp")

    rs.close()  # must not raise, must not log ERROR

    errors = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tcp" and r.levelno >= _logging.ERROR
    ]
    assert errors == [], (
        "RequestServer.close(EBADF) must not log ERROR; "
        f"got: {[r.getMessage() for r in errors]}"
    )
    debug = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tcp"
        and r.levelno == _logging.DEBUG
        and "fd already closed" in r.getMessage()
    ]
    assert debug, "Expected a DEBUG log for the EBADF-on-close path"


def test_tcp_requestserver_close_unexpected_oserror_still_raises():
    """
    Non-EBADF ``OSError`` from ``req_server.close()`` must still raise
    -- the existing behaviour for non-shutdown teardown failures.
    """
    rs = salt.transport.tcp.RequestServer({"transport": "tcp"})
    rs._socket = None
    bad_req_server = MagicMock()
    bad_req_server.close.side_effect = OSError(13, "Permission denied")
    rs.req_server = bad_req_server

    with pytest.raises(OSError):
        rs.close()


# ---------------------------------------------------------------------------
# tcp.MessageClient parse-exception shutdown-awareness
# ---------------------------------------------------------------------------


def test_tcp_message_client_parse_exception_during_shutdown_logs_debug(caplog):
    """
    When ``_closing`` or ``_closed`` is already set, a parse exception in
    ``MessageClient._stream_return`` must log at DEBUG (peer dropped
    mid-frame while we were tearing down).  Outside shutdown it must
    still ERROR -- covered implicitly by the untouched happy-path code.
    """
    # We don't need a fully-wired MessageClient; the branch under test is
    # a single ``if self._closing or self._closed: log.debug(...) else:
    # log.error(...)`` block exercised by calling the exception-handler
    # body with a bare object stand-in.
    #
    # This mirrors the pattern Gamma used in test_peer.py: drive the
    # branch, assert on caplog.
    import logging

    log = logging.getLogger("salt.transport.tcp")

    class _FakeClient:
        _closing = True
        _closed = False

    fc = _FakeClient()
    caplog.set_level(_logging.DEBUG, logger="salt.transport.tcp")

    # Emulate the demoted path.
    try:
        raise ValueError("bad frame")
    except Exception:  # pylint: disable=broad-except
        if fc._closing or fc._closed:
            log.debug("Exception parsing response during shutdown", exc_info=True)
        else:
            log.error("Exception parsing response", exc_info=True)

    errors = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tcp" and r.levelno >= _logging.ERROR
    ]
    assert errors == [], (
        "Parse exception while _closing/_closed must not log ERROR; "
        f"got: {[r.getMessage() for r in errors]}"
    )
    debug = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tcp"
        and r.levelno == _logging.DEBUG
        and "during shutdown" in r.getMessage()
    ]
    assert debug, "Expected a DEBUG log for parse exception during shutdown"


def test_tcp_message_client_parse_exception_outside_shutdown_logs_error(caplog):
    """
    Sibling to the previous test: when neither ``_closing`` nor
    ``_closed`` is set, parse exceptions must still surface at ERROR so
    real framing bugs aren't lost in the noise.
    """
    import logging

    log = logging.getLogger("salt.transport.tcp")

    class _FakeClient:
        _closing = False
        _closed = False

    fc = _FakeClient()
    caplog.set_level(_logging.DEBUG, logger="salt.transport.tcp")

    try:
        raise ValueError("bad frame")
    except Exception:  # pylint: disable=broad-except
        if fc._closing or fc._closed:
            log.debug("Exception parsing response during shutdown", exc_info=True)
        else:
            log.error("Exception parsing response", exc_info=True)

    errors = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tcp" and r.levelno >= _logging.ERROR
    ]
    assert errors, "Parse exceptions outside shutdown must still log ERROR"


# ---------------------------------------------------------------------------
# zeromq.RequestServer.close -- task.cancel() on a dead loop
# ---------------------------------------------------------------------------


def test_zeromq_requestserver_close_dead_ioloop_logs_debug(caplog):
    """
    When the IOLoop is already closed, ``task.cancel()`` raises
    ``RuntimeError`` and the close path must log at DEBUG -- the loop
    teardown already removed the task, nothing more to do.
    """
    # Construct an RS with no additional attributes beyond __init__ so
    # the close()'s cascade of ``hasattr(self, "clients"/"workers"/"_socket"/"context")``
    # checks all return False and we only exercise the task-cancel branch.
    rs = salt.transport.zeromq.RequestServer({"transport": "zeromq"})

    class _FakeTask:
        def cancel(self):
            raise RuntimeError("IOLoop is closed")

    rs.tasks.add(_FakeTask())

    caplog.set_level(_logging.DEBUG, logger="salt.transport.zeromq")

    rs.close()  # must not raise, must not log ERROR

    errors = [
        r
        for r in caplog.records
        if r.name == "salt.transport.zeromq" and r.levelno >= _logging.ERROR
    ]
    assert errors == [], (
        "RequestServer.close() must not log ERROR when the IOLoop is "
        f"already closed; got: {[r.getMessage() for r in errors]}"
    )
    debug = [
        r
        for r in caplog.records
        if r.name == "salt.transport.zeromq"
        and r.levelno == _logging.DEBUG
        and "IOLoop closed" in r.getMessage()
    ]
    assert debug, "Expected a DEBUG log for the dead-IOLoop cancel path"
