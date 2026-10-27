"""
Regression tests for saltstack/salt#69824 -- a wedged event-bus pull
side must not deadlock the publisher forever.

``_TCPPubServerPublisher.send`` accepts a ``timeout`` in seconds. When
the underlying stream write does not complete within it, the send
raises ``TimeoutError`` to the caller instead of waiting forever.
``PublishServer.publish`` forwards the timeout so both the sync
(``SyncWrapper``) and async call paths behave the same way.
"""

import asyncio
import os

import pytest
import tornado.concurrent

import salt.transport.tcp
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.core_test,
]


class _WedgedStream:
    """Stream stand-in whose write never completes (wedged pull side)."""

    def closed(self):
        return False

    def write(self, data):
        return tornado.concurrent.Future()  # never resolves


class _InstantStream:
    """Stream stand-in whose write completes immediately."""

    def closed(self):
        return False

    def write(self, data):
        future = tornado.concurrent.Future()
        future.set_result(None)
        return future


def _publisher(stream):
    pub = object.__new__(salt.transport.tcp._TCPPubServerPublisher)
    pub.stream = stream
    pub._closing = True  # keep __del__ quiet for the stub
    pub._creator_pid = os.getpid()
    return pub


async def test_send_with_timeout_raises_timeout_error_on_wedged_write():
    pub = _publisher(_WedgedStream())
    with pytest.raises(TimeoutError):
        # The outer wait_for only bounds the test harness; the inner
        # send timeout is the behavior under test.
        await asyncio.wait_for(pub.send(b"payload", timeout=0.1), timeout=10)


async def test_send_without_timeout_completes():
    pub = _publisher(_InstantStream())
    assert await pub.send(b"payload") is None


def test_publish_server_publish_forwards_timeout():
    server = object.__new__(salt.transport.tcp.PublishServer)
    server.opts = {}
    server.pub_sock = MagicMock()
    asyncio.run(server.publish(b"payload", timeout=7))
    server.pub_sock.send.assert_called_once_with(b"payload", timeout=7)
