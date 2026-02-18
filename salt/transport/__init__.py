"""
Encapsulate the different transports available to Salt.
"""

import asyncio
import logging
import warnings

import salt.utils.zeromq
from salt.transport.base import (
    TRANSPORTS,
    ipc_publish_client,
    ipc_publish_server,
    publish_client,
    publish_server,
    request_client,
    request_server,
)

log = logging.getLogger(__name__)

# Suppress warnings when running with a very old pyzmq. This can be removed
# after we drop support for Ubuntu 16.04 and Debian 9
warnings.filterwarnings(
    "ignore", message="IOLoop.current expected instance.*", category=RuntimeWarning
)


def is_retryable_connection_error(exc):
    """
    Return ``True`` when transport setup failed due to a transient error.
    """
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return salt.utils.zeromq.is_retryable_connection_error(exc)


def format_connection_error(exc):
    """
    Return a short, consistent error string for transport failures.
    """
    if isinstance(exc, asyncio.TimeoutError):
        return "transport timeout while connecting to master"
    return salt.utils.zeromq.format_connection_error(exc)


__all__ = (
    "TRANSPORTS",
    "format_connection_error",
    "ipc_publish_client",
    "ipc_publish_server",
    "is_retryable_connection_error",
    "publish_client",
    "publish_server",
    "request_client",
    "request_server",
)
