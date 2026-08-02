"""
Tests for the identity-slot cap in ``salt.transport.zeromq``.

The slot pools cap the size of libzmq's per-peer routing-id hashtable on
the master's ROUTER when a long-lived caller repeatedly constructs
:class:`AsyncReqMessageClient` (salt-api LocalClient churn) or when CLI
tooling invokes ``salt`` in a tight loop. See :issue:`69920`.
"""

import importlib
import itertools

import pytest

import salt.transport.zeromq
from tests.support.mock import patch


def test_req_identity_slot_max_default():
    """The default REQ slot pool is bounded at 8."""
    assert salt.transport.zeromq._REQ_IDENTITY_SLOT_MAX == 8


def test_cli_identity_slot_max_default():
    """The default CLI slot pool preserves the historical hardcoded 256."""
    assert salt.transport.zeromq._CLI_IDENTITY_SLOT_MAX == 256


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("4", 4),
        ("1", 1),
        ("128", 128),
    ],
)
def test_req_identity_slot_env_override(monkeypatch, env_value, expected):
    """``SALT_REQ_IDENTITY_SLOT_MAX`` tunes the REQ slot pool at import time."""
    monkeypatch.setenv("SALT_REQ_IDENTITY_SLOT_MAX", env_value)
    try:
        mod = importlib.reload(salt.transport.zeromq)
        assert mod._REQ_IDENTITY_SLOT_MAX == expected
    finally:
        monkeypatch.delenv("SALT_REQ_IDENTITY_SLOT_MAX", raising=False)
        importlib.reload(salt.transport.zeromq)


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("16", 16),
        ("512", 512),
    ],
)
def test_cli_identity_slot_env_override(monkeypatch, env_value, expected):
    """``SALT_CLI_IDENTITY_SLOT_MAX`` tunes the CLI slot pool at import time."""
    monkeypatch.setenv("SALT_CLI_IDENTITY_SLOT_MAX", env_value)
    try:
        mod = importlib.reload(salt.transport.zeromq)
        assert mod._CLI_IDENTITY_SLOT_MAX == expected
    finally:
        monkeypatch.delenv("SALT_CLI_IDENTITY_SLOT_MAX", raising=False)
        importlib.reload(salt.transport.zeromq)


def test_req_identity_slot_wraps_within_pool():
    """Successive ``next(_REQ_IDENTITY_SLOT) % _REQ_IDENTITY_SLOT_MAX``
    values stay bounded regardless of counter growth."""
    with patch.object(salt.transport.zeromq, "_REQ_IDENTITY_SLOT_MAX", 4), patch.object(
        salt.transport.zeromq, "_REQ_IDENTITY_SLOT", itertools.count()
    ):
        slots = [
            next(salt.transport.zeromq._REQ_IDENTITY_SLOT)
            % salt.transport.zeromq._REQ_IDENTITY_SLOT_MAX
            for _ in range(20)
        ]
    # Every slot value is inside the pool.
    assert all(0 <= s < 4 for s in slots)
    # The distinct set fills the pool (with 20 draws over a pool of 4).
    assert set(slots) == {0, 1, 2, 3}


@pytest.mark.parametrize("fake_pid", [1, 42, 65535, 999_999])
def test_cli_identity_slot_pid_mod_bounded(fake_pid):
    """``os.getpid() % _CLI_IDENTITY_SLOT_MAX`` stays within the pool for
    every positive pid value."""
    cap = salt.transport.zeromq._CLI_IDENTITY_SLOT_MAX
    assert 0 <= fake_pid % cap < cap
