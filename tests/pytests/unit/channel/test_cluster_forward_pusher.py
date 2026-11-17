"""
Unit tests for ``MasterPubServerChannel.publish_payload``'s per-peer
forward-pusher failure handling.

Background
----------
Under a sustained cluster-peer disconnect the handler used to emit one
``WARNING`` + one ``io_loop.call_later(2.0, send_aes_key_event)`` *per
forwarded event*.  At ~10 events/sec per down peer that is ~20
warnings/sec and ~20 scheduled AES-key announcements/sec per peer,
which also saturated the local IPC bus and surfaced as a
tornado-internal ``[WARNING ] error on read: [Errno 22] Invalid
argument`` flood (369k lines per ~5 h resiliency-cluster5 run on each
of three masters, filling /var/lib/docker).

The fix:

1. Names the non-``cluster/peer``-tag fan-out task with
   ``pusher.pull_host`` so ``task.get_name()`` yields a real peer name
   (previously ``Task-NNNN`` -- silently skipping the pub_sock reset).
2. Debounces the WARNING + ``call_later`` per peer on a
   ``PEER_RESET_COOLDOWN`` second window.  The ``pub_sock`` reset
   itself still runs every failure (idempotent, no behaviour change on
   healthy clusters).

These tests lock in the debounce and the task naming.
"""

import asyncio

import tornado.iostream

import salt.channel.server
import salt.payload
import salt.utils.event
import salt.utils.stringutils
from tests.support.mock import MagicMock

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class _FakeIoLoop:
    """Minimal io_loop stand-in that captures ``call_later`` invocations."""

    def __init__(self):
        self.calls = []  # list of (delay, callback)

    def call_later(self, delay, callback, *args, **kwargs):
        self.calls.append((delay, callback))


class _FakePusher:
    """Stand-in for ``salt.transport.tcp.PublishServer`` used as a pusher."""

    def __init__(self, host, raises=True):
        self.pull_host = host
        self.pull_port = 4520
        self.pub_sock = MagicMock()
        self._raises = raises
        self.publish_calls = 0

    async def publish(self, payload):
        self.publish_calls += 1
        if self._raises:
            raise tornado.iostream.StreamClosedError()


def _make_channel(pushers, master_id="salt-master-1"):
    chan = salt.channel.server.MasterPubServerChannel.__new__(
        salt.channel.server.MasterPubServerChannel
    )
    chan.opts = {
        "id": master_id,
        "cluster_id": "test-cluster",
        "cluster_peers": [p.pull_host for p in pushers],
        "cluster_pool_port": 4520,
        "sign_pub_messages": False,
        "publish_signing_algorithm": "PKCS1v15-SHA224",
        "cluster_encryption_algorithm": "OAEP-SHA1",
    }
    chan.cluster_peers = list(chan.opts["cluster_peers"])
    chan.pushers = pushers
    chan.transport = MagicMock()

    async def _noop_publish_payload(*args, **kwargs):
        return None

    chan.transport.publish_payload = _noop_publish_payload
    chan.io_loop = _FakeIoLoop()
    chan._peer_reset_times = {}
    return chan


def _build_load(tag):
    """Encode the ``tag<TAGEND>msgpack-body`` wire form ``publish_payload`` expects."""
    tagend = salt.utils.stringutils.to_bytes(salt.utils.event.TAGEND)
    return (
        salt.utils.stringutils.to_bytes(tag)
        + tagend
        + salt.payload.dumps({"body": "x"})
    )


async def _publish(chan, tag):
    """
    Drive ``publish_payload`` end-to-end for one event.

    The tag selects whether the broadcast loop uses the named
    cluster-peer path or the unnamed fan-out path (the one the fix
    renames + debounces).
    """
    load = _build_load(tag)
    await chan.publish_payload(load, raw_payload=load)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_task_is_named_with_peer_host(monkeypatch):
    """
    The fan-out task for non-``cluster/peer`` tags must be named with
    ``pusher.pull_host`` so the ``StreamClosedError`` handler can resolve
    the failed peer back to a real pusher entry.
    """
    pusher = _FakePusher("peer-a", raises=True)
    chan = _make_channel([pusher])

    captured = {}

    real_create_task = asyncio.create_task

    def _spy_create_task(coro, *, name=None):
        task = real_create_task(coro, name=name)
        # Record only tasks whose coroutine targets ``_FakePusher.publish``.
        qualname = getattr(getattr(coro, "cr_code", None), "co_qualname", "")
        if "_FakePusher.publish" in qualname:
            captured.setdefault("peer_task_names", []).append(name)
        return task

    monkeypatch.setattr(asyncio, "create_task", _spy_create_task)

    # Patch ``_get_crypticle`` -> noop to avoid touching master keys.
    crypticle = MagicMock()
    crypticle.dumps = lambda x: b"\xc0"  # msgpack nil
    monkeypatch.setattr(
        salt.channel.server, "_get_crypticle", lambda *a, **kw: crypticle
    )
    monkeypatch.setattr(
        salt.master.SMaster,
        "secrets",
        {"aes": MagicMock(value=b"fakekey")},
        raising=False,
    )

    asyncio.run(_publish(chan, tag="salt/job/12345/new"))

    assert captured.get("peer_task_names") == [
        "peer-a"
    ], f"expected task to be named 'peer-a', got {captured.get('peer_task_names')!r}"


def test_warning_and_reschedule_debounced_within_cooldown(monkeypatch):
    """
    Two failures to the same peer within the cool-off window emit
    exactly one WARNING + one ``call_later``; the second is suppressed.
    The ``pub_sock`` reset runs on both.
    """
    pusher = _FakePusher("peer-a", raises=True)
    chan = _make_channel([pusher])

    crypticle = MagicMock()
    crypticle.dumps = lambda x: b"\xc0"
    monkeypatch.setattr(
        salt.channel.server, "_get_crypticle", lambda *a, **kw: crypticle
    )
    monkeypatch.setattr(
        salt.master.SMaster,
        "secrets",
        {"aes": MagicMock(value=b"fakekey")},
        raising=False,
    )

    # Pin time.monotonic so the two failures land inside the cool-off.
    fake_t = [1000.0]
    monkeypatch.setattr(salt.channel.server.time, "monotonic", lambda: fake_t[0])

    warnings = []
    monkeypatch.setattr(
        salt.channel.server.log, "warning", lambda *a, **k: warnings.append(a)
    )

    asyncio.run(_publish(chan, tag="salt/job/1/new"))
    fake_t[0] += 0.5  # well inside PEER_RESET_COOLDOWN
    asyncio.run(_publish(chan, tag="salt/job/2/new"))

    # Exactly one WARNING and one ``call_later``.
    assert len(warnings) == 1, f"expected 1 WARNING, got {len(warnings)}: {warnings}"
    assert (
        len(chan.io_loop.calls) == 1
    ), f"expected 1 call_later, got {len(chan.io_loop.calls)}: {chan.io_loop.calls}"
    delay, _cb = chan.io_loop.calls[0]
    assert delay == 2.0

    # pub_sock reset happens every time (pusher.publish was called twice,
    # and pub_sock was set before each call; both times it should be
    # cleared to None after handling).
    assert pusher.pub_sock is None


def test_warning_re_emits_after_cooldown_elapsed(monkeypatch):
    """
    After the cool-off window elapses, the WARNING + reschedule fires
    again for the same peer.  Validates that the debounce is not a
    one-shot latch.
    """
    pusher = _FakePusher("peer-a", raises=True)
    chan = _make_channel([pusher])

    crypticle = MagicMock()
    crypticle.dumps = lambda x: b"\xc0"
    monkeypatch.setattr(
        salt.channel.server, "_get_crypticle", lambda *a, **kw: crypticle
    )
    monkeypatch.setattr(
        salt.master.SMaster,
        "secrets",
        {"aes": MagicMock(value=b"fakekey")},
        raising=False,
    )

    fake_t = [1000.0]
    monkeypatch.setattr(salt.channel.server.time, "monotonic", lambda: fake_t[0])

    warnings = []
    monkeypatch.setattr(
        salt.channel.server.log, "warning", lambda *a, **k: warnings.append(a)
    )

    asyncio.run(_publish(chan, tag="salt/job/1/new"))
    # Advance past the cool-off window.
    fake_t[0] += salt.channel.server.PEER_RESET_COOLDOWN + 0.1

    # Re-prime pub_sock (the previous run cleared it).
    pusher.pub_sock = MagicMock()
    asyncio.run(_publish(chan, tag="salt/job/2/new"))

    assert len(warnings) == 2, f"expected 2 WARNINGs, got {len(warnings)}"
    assert len(chan.io_loop.calls) == 2


def test_debounce_is_per_peer(monkeypatch):
    """
    A cool-off recorded against peer-a does not suppress a warning for
    peer-b -- the debounce is per-peer, not global.
    """
    pusher_a = _FakePusher("peer-a", raises=True)
    pusher_b = _FakePusher("peer-b", raises=True)
    chan = _make_channel([pusher_a, pusher_b])

    crypticle = MagicMock()
    crypticle.dumps = lambda x: b"\xc0"
    monkeypatch.setattr(
        salt.channel.server, "_get_crypticle", lambda *a, **kw: crypticle
    )
    monkeypatch.setattr(
        salt.master.SMaster,
        "secrets",
        {"aes": MagicMock(value=b"fakekey")},
        raising=False,
    )

    fake_t = [1000.0]
    monkeypatch.setattr(salt.channel.server.time, "monotonic", lambda: fake_t[0])

    warnings = []
    monkeypatch.setattr(
        salt.channel.server.log, "warning", lambda *a, **k: warnings.append(a)
    )

    # One publish; both peers fail; both should warn (distinct peers).
    asyncio.run(_publish(chan, tag="salt/job/1/new"))

    emitted_peers = {args[-1] for args in warnings}
    assert emitted_peers == {
        "peer-a",
        "peer-b",
    }, f"expected warnings for both peers, got {emitted_peers}"
    assert len(chan.io_loop.calls) == 2


def test_pub_sock_still_reset_during_cooldown(monkeypatch):
    """
    Regression guard: suppressing the WARNING must not suppress the
    pub_sock reset.  A failed publish inside the cool-off still clears
    the broken socket so the next publish can reconnect.
    """
    pusher = _FakePusher("peer-a", raises=True)
    chan = _make_channel([pusher])

    crypticle = MagicMock()
    crypticle.dumps = lambda x: b"\xc0"
    monkeypatch.setattr(
        salt.channel.server, "_get_crypticle", lambda *a, **kw: crypticle
    )
    monkeypatch.setattr(
        salt.master.SMaster,
        "secrets",
        {"aes": MagicMock(value=b"fakekey")},
        raising=False,
    )

    fake_t = [1000.0]
    monkeypatch.setattr(salt.channel.server.time, "monotonic", lambda: fake_t[0])

    # First failure records the cool-off.
    asyncio.run(_publish(chan, tag="salt/job/1/new"))
    assert pusher.pub_sock is None

    # Simulate a reconnect (new socket assigned) followed by another failure.
    pusher.pub_sock = MagicMock()
    fake_t[0] += 0.1  # still within cool-off
    asyncio.run(_publish(chan, tag="salt/job/2/new"))

    # pub_sock must still have been cleared.
    assert pusher.pub_sock is None


def test_cooldown_constant_exported():
    """Smoke: the module exposes the cool-off constant for tests to patch."""
    assert hasattr(salt.channel.server, "PEER_RESET_COOLDOWN")
    assert salt.channel.server.PEER_RESET_COOLDOWN > 0
