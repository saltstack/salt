"""
Small helpers for the Raft package (random election jitter, optional socket
checks, dynamic class loading).
"""

import functools
import logging
import random
import socket
import string

log = logging.getLogger(__name__)


def log_generator(size=6, chars=string.ascii_uppercase + string.digits):
    """Generate a random string of specified size."""
    return "".join(random.choice(chars) for _ in range(size))


def gettimeout(_min, _max):
    """Return a random timeout in seconds within the specified millisecond range."""
    return random.randint(_min, _max) * 0.001


def is_socket_closed(sock: socket.socket) -> bool:
    """Check non-blockingly if a TCP socket has been closed by the peer."""
    try:
        # this will try to read bytes without blocking and also without removing them from buffer (peek only)
        data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            log.warning("Empty data")
            return True
    except BlockingIOError:
        return False  # socket is open and reading from it would block
    except ConnectionResetError:
        log.warning("Connection reset")
        return True  # socket was closed for some other reason
    except OSError as exc:
        if exc.errno == 107:  # Transport endpoint is not connected
            log.warning("Endpoint not connected")
            return False
        elif exc.errno == 9:  # Bad File Descriptor
            log.warning("Bad file descripor")
            return True
        log.exception("unexpected exception when checking if a socket is closed")
        return False
    except Exception:  # pylint: disable=broad-except
        log.exception("unexpected exception when checking if a socket is closed")
        return False
    return False


def log_exceptions_async(func):
    """Log unhandled exceptions in asynchronous functions as a decorator."""

    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            log.exception("Unhandled exception in %r", func)
            raise

    return wrapped


def log_exceptions(func):
    """Log unhandled exceptions in synchronous functions as a decorator."""

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            log.exception("Unhandled exception in %r", func)
            raise

    return wrapped


def load_class(path):
    """
    Dynamically load a class from a string path.

    Example: ``salt.cluster.consensus.raft.log.CounterStateMachine``.
    """
    import importlib

    try:
        module_path, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as e:
        raise ImportError(f"Failed to load class from {path}: {e}")
