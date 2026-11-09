"""
Tests for :py:func:`salt.utils.process.signal_safe_log`

See https://github.com/saltstack/salt/issues/67735
"""

import io
import logging

import pytest

import salt.utils.process


@pytest.fixture
def stream():
    return io.StringIO()


@pytest.fixture
def handler(stream):
    root = logging.getLogger()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)


@pytest.fixture
def logger():
    return logging.getLogger("tests.signal_safe_log")


def test_signal_safe_log_logs_when_no_write_in_progress(handler, stream, logger):
    salt.utils.process.signal_safe_log(logger, logging.INFO, "hello %s", "world")
    assert "hello world" in stream.getvalue()


def test_signal_safe_log_drops_message_when_write_in_progress(handler, stream, logger):
    """
    A signal handler interrupting the main thread while it holds a handler's
    lock (i.e. mid-write) must not log, otherwise the nested write to stderr
    raises "reentrant call inside <_io.BufferedWriter>".
    """
    with handler.lock:
        salt.utils.process.signal_safe_log(logger, logging.INFO, "should be dropped")
    assert stream.getvalue() == ""
    # Once the lock is released, logging works again
    salt.utils.process.signal_safe_log(logger, logging.INFO, "logged afterwards")
    assert "logged afterwards" in stream.getvalue()


def test_signal_safe_log_ignores_handlers_without_a_lock(handler, stream, logger):
    handler.lock = None
    salt.utils.process.signal_safe_log(logger, logging.INFO, "no lock")
    assert "no lock" in stream.getvalue()
