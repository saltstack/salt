"""
Encapsulate the different transports available to Salt.
"""

import logging
import warnings

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

__all__ = (
    "TRANSPORTS",
    "ipc_publish_client",
    "ipc_publish_server",
    "publish_client",
    "publish_server",
    "request_client",
    "request_server",
)
