"""
ZMQ-specific functions
"""

import errno
import logging

import salt.utils.versions
from salt.exceptions import SaltReqTimeoutError, SaltSystemExit
from salt.utils.network import ip_bracket as _new_ip_bracket

log = logging.getLogger(__name__)

try:
    import zmq
except ImportError:
    zmq = None
    log.debug("ZMQ module is not found")

ZMQDefaultLoop = None
ZMQ_VERSION_INFO = (-1, -1, -1)
LIBZMQ_VERSION_INFO = (-1, -1, -1)

try:
    if zmq:
        ZMQ_VERSION_INFO = tuple(int(v_el) for v_el in zmq.__version__.split("."))
        LIBZMQ_VERSION_INFO = tuple(int(v_el) for v_el in zmq.zmq_version().split("."))
except Exception:  # pylint: disable=broad-except
    log.exception("Error while getting LibZMQ/PyZMQ library version")


def _errno_values(*names):
    values = set()
    for name in names:
        value = getattr(errno, name, None)
        if value is not None:
            values.add(value)
    return values


_RETRYABLE_OS_ERRNOS = frozenset(
    _errno_values(
        "EAGAIN",
        "EINTR",
        "ECONNABORTED",
        "ECONNRESET",
        "ECONNREFUSED",
        "ETIMEDOUT",
        "EHOSTUNREACH",
        "ENETUNREACH",
        "ENOTCONN",
    )
)


def _retryable_zmq_errnos():
    if zmq is None:
        return frozenset()
    errnos = set()
    for name in (
        "EAGAIN",
        "EINTR",
        "ECONNABORTED",
        "ECONNRESET",
        "ECONNREFUSED",
        "ETIMEDOUT",
        "EHOSTUNREACH",
        "ENETUNREACH",
        "ENOTCONN",
        "EFSM",
        "ETERM",
        "ENOTSOCK",
    ):
        value = getattr(zmq, name, None)
        if value is not None:
            errnos.add(value)
    return frozenset(errnos)


_RETRYABLE_ZMQ_ERRNOS = _retryable_zmq_errnos()


def _iter_exception_chain(exc, max_depth=16):
    """
    Iterate an exception and its cause/context chain.
    """
    current = exc
    seen = set()
    depth = 0
    while current is not None and depth < max_depth:
        exc_id = id(current)
        if exc_id in seen:
            break
        seen.add(exc_id)
        yield current
        depth += 1
        current = current.__cause__ or current.__context__


def _is_tornado_future_callbacks_race(exc):
    """
    Detect the Tornado 4 Future callback race observed as:
    ``TypeError: 'NoneType' object is not iterable``.
    """
    if not isinstance(exc, TypeError):
        return False
    message = str(exc)
    return "NoneType" in message and "iterable" in message


def is_retryable_connection_error(exc):
    """
    Return ``True`` when ``exc`` looks like a transient transport failure.
    """
    if exc is None:
        return False
    for candidate in _iter_exception_chain(exc):
        if isinstance(candidate, SaltReqTimeoutError):
            return True
        if isinstance(candidate, TimeoutError):
            return True
        if _is_tornado_future_callbacks_race(candidate):
            return True
        if isinstance(candidate, OSError) and candidate.errno in _RETRYABLE_OS_ERRNOS:
            return True
        if zmq is not None and isinstance(candidate, zmq.ZMQError):
            if getattr(candidate, "errno", None) in _RETRYABLE_ZMQ_ERRNOS:
                return True
    return False


def format_connection_error(exc):
    """
    Return a concise string for connection-related exception logging.
    """
    if exc is None:
        return "unknown transport exception"
    if _is_tornado_future_callbacks_race(exc):
        return (
            "Transient tornado future callback race "
            "('NoneType' callbacks list while setting exception)"
        )
    return str(exc)


def check_ipc_path_max_len(uri):
    """
    The socket path is limited to 107 characters on Solaris and
    Linux, and 103 characters on BSD-based systems.
    """

    if zmq is None:
        return
    ipc_path_max_len = getattr(zmq, "IPC_PATH_MAX_LEN", 103)
    if ipc_path_max_len and len(uri) > ipc_path_max_len:
        raise SaltSystemExit(
            "The socket path is longer than allowed by OS. "
            "'{}' is longer than {} characters. "
            "Either try to reduce the length of this setting's "
            "path or switch to TCP; in the configuration file, "
            'set "ipc_mode: tcp".'.format(uri, ipc_path_max_len)
        )


def ip_bracket(addr):
    "This function has been moved to salt.utils.network.ip_bracket"

    salt.utils.versions.warn_until(
        3008,
        "The 'utils.zeromq.ip_bracket' has been moved to 'utils.network.ip_bracket'. "
        "Please use 'utils.network.ip_bracket' because 'utils.zeromq.ip_bracket' "
        "will be removed in future releases.",
    )
    return _new_ip_bracket(addr)
