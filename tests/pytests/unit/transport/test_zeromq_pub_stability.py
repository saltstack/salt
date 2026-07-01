"""
Regression tests for ZMQ PUB-socket heartbeat configuration.

See https://github.com/saltstack/salt/issues/66282 — when a SUB peer dies
without sending FIN (host reboot, kernel panic, firewall block) the master's
PUB socket only reaps that peer once kernel TCP keepalive expires, which is
~2 h 15 min on default Linux.  ZMTP heartbeats (``ZMQ_HEARTBEAT_IVL`` /
``ZMQ_HEARTBEAT_TIMEOUT``) reduce that to seconds, which prevents the
``CLOSE_WAIT`` build-up and per-peer buffer growth that eventually wedges
port 4505.

These tests pin the heartbeat options on the publisher socket.  The fix
adds them via a helper invoked from ``publish_daemon``; the helper is
unit-tested here without bringing up the full daemon.
"""

import logging

import pytest
import zmq

import salt.transport.zeromq

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def zmq_context():
    ctx = zmq.Context()
    try:
        yield ctx
    finally:
        ctx.destroy(linger=0)


def test_pub_socket_has_zmtp_heartbeats_configured(zmq_context):
    """
    ``salt.transport.zeromq._set_zmq_heartbeat`` must enable ZMTP
    heartbeats on the PUB socket so dead subscribers are reaped in
    seconds instead of hours.  Without this, ``netstat`` accumulates
    ``CLOSE_WAIT`` entries on port 4505 and the master eventually stops
    accepting new connections (#66282).
    """
    sock = zmq_context.socket(zmq.PUB)
    try:
        # Default ZMQ behaviour: heartbeats disabled.  Sanity check that
        # the test is actually verifying a non-default configuration.
        assert sock.getsockopt(zmq.HEARTBEAT_IVL) == 0
        assert sock.getsockopt(zmq.HEARTBEAT_TIMEOUT) == -1

        opts = {}
        salt.transport.zeromq._set_zmq_heartbeat(sock, opts)

        ivl = sock.getsockopt(zmq.HEARTBEAT_IVL)
        timeout = sock.getsockopt(zmq.HEARTBEAT_TIMEOUT)
        assert ivl > 0, (
            "PUB socket has ZMTP HEARTBEAT_IVL disabled; dead SUB peers "
            "will not be reaped until kernel TCP keepalive expires "
            "(~2h15m). #66282"
        )
        assert timeout > 0, (
            "PUB socket has ZMTP HEARTBEAT_TIMEOUT unset; dead SUB peers "
            "will not be reaped until kernel TCP keepalive expires. "
            "#66282"
        )
        # The timeout should exceed the interval; otherwise heartbeats
        # would mark live peers as dead.
        assert timeout > ivl
    finally:
        sock.close()


def test_pub_socket_heartbeat_respects_opts(zmq_context):
    """
    Operators must be able to tune the heartbeat interval and timeout
    via ``zmq_heartbeat_ivl`` / ``zmq_heartbeat_timeout`` master config.
    """
    sock = zmq_context.socket(zmq.PUB)
    try:
        opts = {"zmq_heartbeat_ivl": 5000, "zmq_heartbeat_timeout": 15000}
        salt.transport.zeromq._set_zmq_heartbeat(sock, opts)
        assert sock.getsockopt(zmq.HEARTBEAT_IVL) == 5000
        assert sock.getsockopt(zmq.HEARTBEAT_TIMEOUT) == 15000
    finally:
        sock.close()
