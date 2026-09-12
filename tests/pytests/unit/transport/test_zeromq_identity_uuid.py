"""
Unit tests for the per-instance UUID ZMQ IDENTITY assigned to daemon
``AsyncReqMessageClient`` sockets.

The daemon (minion / syndic) branch of ``_init_socket`` gives each
``AsyncReqMessageClient`` a fresh ``uuid.uuid4().hex`` slot as its ZMQ
IDENTITY so the master ROUTER's routing-id entry maps 1:1 to a client
whose lifecycle Salt itself owns.  Fork inheritance of the earlier
process-wide counter (root cause of #69753) is impossible by
construction -- each child draws a fresh UUID.
"""

import os
import re

import pytest

import salt.transport.zeromq
from tests.support.mock import MagicMock

DAEMON_IDENTITY_RE = re.compile(r"^salt-req/(?:minion|syndic)/[^/]+/\d+/[0-9a-f]{32}$")


@pytest.fixture
def _mock_socket_setsockopt_capture():
    """Yield a list that captures every setsockopt(IDENTITY, ...) call."""
    captured = []

    def _fake_setsockopt(opt, value):
        # Only capture the IDENTITY call; other options (LINGER, IPV6...) are
        # noise for these tests.
        import zmq

        if opt == zmq.IDENTITY:
            captured.append(value)

    fake_socket = MagicMock()
    fake_socket.setsockopt.side_effect = _fake_setsockopt

    yield captured, fake_socket


def _make_client_and_capture_identity(minion_opts, role="minion"):
    """Instantiate one AsyncReqMessageClient with the socket mocked out.

    Returns the identity string (utf-8 decoded) that was passed to
    ``setsockopt(zmq.IDENTITY, ...)``.
    """
    import zmq

    opts = dict(minion_opts)
    opts["__role"] = role
    opts["id"] = "test-daemon"

    captured = []

    def _fake_setsockopt(opt, value):
        if opt == zmq.IDENTITY:
            captured.append(value)

    fake_socket = MagicMock()
    fake_socket.setsockopt.side_effect = _fake_setsockopt
    fake_context = MagicMock()
    fake_context.socket.return_value = fake_socket

    client = salt.transport.zeromq.AsyncReqMessageClient(opts, "tcp://127.0.0.1:4506")
    # Bypass the real ZMQ context that ``connect`` would open.
    client.context = fake_context
    client._init_socket()

    assert captured, "expected setsockopt(zmq.IDENTITY, ...) to be called"
    return captured[-1].decode("utf-8")


def test_daemon_identity_is_uuid_per_instance(minion_opts):
    """
    Two consecutive AsyncReqMessageClient instances (same role, same
    minion id, same pid) must produce IDENTITY strings whose final path
    component (the uuid slot) differs.
    """
    ident_a = _make_client_and_capture_identity(minion_opts)
    ident_b = _make_client_and_capture_identity(minion_opts)

    slot_a = ident_a.rsplit("/", 1)[-1]
    slot_b = ident_b.rsplit("/", 1)[-1]

    assert slot_a != slot_b, (ident_a, ident_b)
    # Both slots must be 32-char lowercase hex (uuid4().hex).
    assert re.fullmatch(r"[0-9a-f]{32}", slot_a), slot_a
    assert re.fullmatch(r"[0-9a-f]{32}", slot_b), slot_b


@pytest.mark.parametrize("role", ["minion", "syndic"])
def test_daemon_identity_format(minion_opts, role):
    """
    The IDENTITY must match ``salt-req/<role>/<minion_id>/<pid>/<uuid>``
    with a 32-char lowercase-hex uuid tail.
    """
    ident = _make_client_and_capture_identity(minion_opts, role=role)

    assert DAEMON_IDENTITY_RE.match(ident), ident

    parts = ident.split("/")
    assert parts[0] == "salt-req"
    assert parts[1] == role
    assert parts[2] == "test-daemon"
    assert parts[3] == str(os.getpid())


def test_cli_identity_slot_unchanged():
    """
    The CLI-mode process-lifetime slot (``_CLI_IDENTITY_SLOT``) is
    orthogonal to the daemon UUID change and must still be present as a
    module-level 24-bit integer, cached at import time.  Guards against
    accidental deletion while removing the (now-gone) daemon-side slot
    counter.
    """
    slot = salt.transport.zeromq._CLI_IDENTITY_SLOT
    assert isinstance(slot, int)
    assert 0 <= slot < 2**24
    # Cached at import time: two accesses return the same value.
    assert slot == salt.transport.zeromq._CLI_IDENTITY_SLOT


def test_slot_counter_infrastructure_removed():
    """
    The old process-wide ``_REQ_IDENTITY_SLOT`` counter and its
    associated environment-variable cap must be gone -- the per-instance
    UUID design replaces both.
    """
    assert not hasattr(salt.transport.zeromq, "_REQ_IDENTITY_SLOT")
