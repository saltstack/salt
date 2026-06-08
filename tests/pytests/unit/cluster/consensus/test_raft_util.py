"""Tests for ``salt.cluster.consensus.raft.util`` helpers."""

import pytest

from salt.cluster.consensus.raft import (
    CounterStateMachine,
    gettimeout,
    load_class,
    log_generator,
)


def test_log_generator_default_alphanumeric():
    s = log_generator(12)
    assert len(s) == 12
    assert s.isalnum()


def test_log_generator_custom_alphabet():
    s = log_generator(20, chars="ab")
    assert len(s) == 20
    assert set(s) <= {"a", "b"}


def test_gettimeout_milliseconds_are_seconds():
    for _ in range(40):
        t = gettimeout(150, 300)
        assert 0.15 <= t <= 0.30


def test_load_class_counter_state_machine():
    cls = load_class("salt.cluster.consensus.raft.log.CounterStateMachine")
    assert cls is CounterStateMachine
    assert cls() is not None


def test_load_class_via_package_export():
    cls = load_class("salt.cluster.consensus.raft.CounterStateMachine")
    assert cls is CounterStateMachine


def test_load_class_invalid_module():
    with pytest.raises(ImportError, match="Failed to load class"):
        load_class("definitely_not_a_real_module_zzz.SomeClass")


def test_load_class_invalid_attribute():
    with pytest.raises(ImportError, match="Failed to load class"):
        load_class("salt.cluster.consensus.raft.log.NotARealClassName")


# ---------------------------------------------------------------------------
# Coverage gaps: is_socket_closed, log_exceptions_async, log_exceptions
# ---------------------------------------------------------------------------


class TestIsSocketClosed:
    def _make_socket(self):
        import socket

        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def test_returns_false_for_open_nonblocking_socket(self):
        """A bound-but-not-connected socket raises BlockingIOError → open."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Not connected → recv raises BlockingIOError (EAGAIN)
            result = is_socket_closed(sock)
            assert result is False
        finally:
            sock.close()

    def test_returns_true_on_empty_data(self):
        """Empty recv data (EOF) → socket is closed."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.return_value = b""
        assert is_socket_closed(mock_sock) is True

    def test_returns_true_on_connection_reset(self):
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.side_effect = ConnectionResetError
        assert is_socket_closed(mock_sock) is True

    def test_returns_false_on_os_error_107(self):
        """OSError errno 107 (not connected) → socket not closed."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        err = OSError("endpoint not connected")
        err.errno = 107
        mock_sock.recv.side_effect = err
        assert is_socket_closed(mock_sock) is False

    def test_returns_true_on_os_error_9(self):
        """OSError errno 9 (bad fd) → socket is closed."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        err = OSError("bad file descriptor")
        err.errno = 9
        mock_sock.recv.side_effect = err
        assert is_socket_closed(mock_sock) is True

    def test_returns_false_on_unknown_os_error(self):
        """Unknown OSError → logged and returns False."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        err = OSError("some other error")
        err.errno = 42
        mock_sock.recv.side_effect = err
        assert is_socket_closed(mock_sock) is False

    def test_returns_false_on_generic_exception(self):
        """Any unexpected exception → logged and returns False."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.side_effect = ValueError("unexpected")
        assert is_socket_closed(mock_sock) is False


class TestLogExceptionsAsync:
    def test_passes_through_return_value(self):
        import asyncio

        from salt.cluster.consensus.raft.util import log_exceptions_async

        @log_exceptions_async
        async def add(x, y):
            return x + y

        result = asyncio.run(add(2, 3))
        assert result == 5

    def test_reraises_and_logs_exception(self):
        import asyncio

        import pytest

        from salt.cluster.consensus.raft.util import log_exceptions_async

        @log_exceptions_async
        async def boom():
            raise ValueError("async error")

        with pytest.raises(ValueError, match="async error"):
            asyncio.run(boom())

    def test_preserves_function_name(self):
        from salt.cluster.consensus.raft.util import log_exceptions_async

        @log_exceptions_async
        async def my_func():
            pass

        assert my_func.__name__ == "my_func"


class TestLogExceptions:
    def test_passes_through_return_value(self):
        from salt.cluster.consensus.raft.util import log_exceptions

        @log_exceptions
        def multiply(x, y):
            return x * y

        assert multiply(3, 4) == 12

    def test_reraises_and_logs_exception(self):
        import pytest

        from salt.cluster.consensus.raft.util import log_exceptions

        @log_exceptions
        def boom():
            raise RuntimeError("sync error")

        with pytest.raises(RuntimeError, match="sync error"):
            boom()

    def test_preserves_function_name(self):
        from salt.cluster.consensus.raft.util import log_exceptions

        @log_exceptions
        def my_func():
            pass

        assert my_func.__name__ == "my_func"


class TestIsSocketClosedRemainingPaths:
    def test_returns_false_when_data_received(self):
        """Non-empty recv means the socket is open (not closed)."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.return_value = b"some data"
        assert is_socket_closed(mock_sock) is False


class TestIsSocketClosedBlockingIoError:
    def test_blocking_io_error_returns_false(self):
        """BlockingIOError → socket open → returns False."""
        import socket

        from salt.cluster.consensus.raft.util import is_socket_closed
        from tests.support.mock import MagicMock

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.side_effect = BlockingIOError
        assert is_socket_closed(mock_sock) is False
