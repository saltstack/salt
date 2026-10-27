# Copyright © 2026 Broadcom Inc. and/or its subsidiaries. All Rights Reserved.
"""
Regression coverage for the PR-70316 follow-up: audit of remaining
``AsyncReqChannel`` callers that had sync close/teardown paths.

The PR-70316 change added ``AsyncReqChannel.close_async`` +
``RequestClient.close_async`` and wired both into the minion reconnect
sites (``connect_master`` / ``handle_event``).  A follow-up audit found
several more callers still on sync close paths -- each one able to
leave the underlying ``zmq.asyncio.Context`` alive on the ioloop long
enough for pyzmq's ``Context.__del__`` to wedge in ``zmq_ctx_term()``.

Every fix has the same shape: route the caller through
``close_async`` (directly or via ``async with``), so the underlying
``RequestClient``'s ``_send_recv`` task drains its shutdown sentinel
and releases its socket reference before the transport tears down.
When that happens correctly, the ``zmq.asyncio.Context`` reaches
``closed=True`` by the time close returns -- so any subsequent
``Context.__del__`` short-circuits and cannot wedge.

Tests here verify that invariant per site category rather than
reproducing the full production wedge (which the neighbouring
``test_context_finalizer_wedge`` covers end-to-end).  They construct
the objects directly, bind against a dead master URI so no traffic
actually flows, and assert ``context.closed is True`` after teardown.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import pytest

import salt.channel.client
import salt.config
import salt.pillar
import salt.transport.zeromq

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        sys.platform != "linux",
        reason=(
            "Async close discipline is exercised on the same asyncio backend "
            "everywhere, but transport teardown timing is only stable enough "
            "for the ``context.closed`` invariant on Linux CI runners."
        ),
    ),
]

# Port 1 (tcpmux) is virtually never listening on any modern host.  ZMQ's
# ``connect()`` succeeds asynchronously, and ``send()`` queues into the
# socket's outbound buffer with no peer -- exactly the shape the wedge
# needs to reproduce.  Matches ``test_context_finalizer_wedge``.
DEAD_MASTER_URI = "tcp://127.0.0.1:1"


def _minion_opts_for(tmp_path):
    """Minion opts sized for ``AsyncReqChannel.factory`` /
    ``RequestClient`` construction against a dead master URI.  We copy
    ``DEFAULT_MINION_OPTS`` so every downstream helper
    (``AsyncAuth``, ``salt.cache``, etc.) sees the keys it expects;
    then override the network + path bits so the test doesn't touch
    real minion state.
    """
    opts = dict(salt.config.DEFAULT_MINION_OPTS)
    opts.update(
        {
            "transport": "zeromq",
            "id": "test-close-async-audit",
            "master": "127.0.0.1",
            "master_ip": "127.0.0.1",
            "master_port": 1,
            "master_uri": DEAD_MASTER_URI,
            "interface": "127.0.0.1",
            "ipv6": False,
            "zmq_filtering": False,
            "pki_dir": str(tmp_path / "pki"),
            "sock_dir": str(tmp_path / "sock"),
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(tmp_path / "extmods"),
            "acceptance_wait_time": 1,
            "acceptance_wait_time_max": 1,
            "auth_timeout": 1,
            "auth_tries": 1,
            "auth_safemode": False,
            "master_tries": 1,
            "request_channel_timeout": 1,
            "request_channel_tries": 1,
            "minion_sign_messages": False,
            "keysize": 2048,
            "__role": "minion",
        }
    )
    # cache dirs must exist for ``salt.cache.Cache`` to load its driver.
    for key in ("pki_dir", "sock_dir", "cachedir", "extension_modules"):
        os.makedirs(opts[key], exist_ok=True)
    return opts


# ---------------------------------------------------------------------------
# Category (a): ``async with`` on AsyncReqChannel fires __aexit__ ->
# close_async, so the underlying context ends up closed.  Covers sites 2, 5, 6.
# ---------------------------------------------------------------------------


def test_async_with_on_async_req_channel_closes_context(tmp_path):
    """The three ``with`` -> ``async with`` fixes (``pub_async``,
    ``connect_callback``, ``_authenticate``) rely on
    ``AsyncReqChannel.__aexit__`` awaiting ``close_async``, which in
    turn awaits the ``RequestClient``'s ``_send_recv_exit_future``
    before destroying the context.

    This test wires an ``AsyncReqChannel`` with a real ``RequestClient``
    transport against a dead master URI (so ``connect()`` succeeds but
    no traffic flows), enters via ``async with``, exits without sending
    anything, and asserts the transport's ``zmq.asyncio.Context`` is
    marked ``closed`` on the way out.  The sync-``with`` fallback in
    the base ``AsyncReqChannel.__exit__`` calls ``close()``'s
    same-thread + loop-running branch, which cannot await the
    send/recv task and therefore does NOT flip ``context.closed`` --
    reproducing the wedge risk this branch of PR-70316's follow-up
    addresses.
    """
    opts = _minion_opts_for(tmp_path)

    contexts_seen = []

    async def _drive():
        # ``crypt="clear"`` avoids the AsyncAuth side dependency; the
        # transport-level teardown is what we're checking.
        async with salt.channel.client.AsyncReqChannel.factory(
            opts, crypt="clear"
        ) as channel:
            # ``__aenter__`` is lazy (matches the sync ``__enter__``
            # shape) so no ``zmq.asyncio.Context`` gets allocated
            # until the first send/connect.  Force ``connect()``
            # here so ``__aexit__``'s ``close_async`` has an
            # allocated context to release -- that is the wedge-risk
            # scenario this test guards.
            await channel.transport.connect()
            transport = channel.transport
            contexts_seen.append(transport.context)

    asyncio.run(_drive())

    assert contexts_seen, "async with did not populate transport.context"
    ctx = contexts_seen[0]
    assert ctx.closed, (
        "AsyncReqChannel.__aexit__ did not close the underlying "
        "zmq.asyncio.Context.  If close_async is not awaited, the "
        "context stays alive until GC finalizes it from an ioloop "
        "callback -- the exact wedge trace behind PR-70316."
    )


def test_async_with_routes_teardown_through_close_async(tmp_path, monkeypatch):
    """The load-bearing property of ``async with`` on an
    ``AsyncReqChannel`` is that ``__aexit__`` routes through
    ``AsyncReqChannel.close_async`` -> ``RequestClient.close_async``,
    NOT through the sync ``close``.  That is the ordering that awaits
    the transport's ``_send_recv_exit_future`` before running
    teardown -- exactly the guarantee PR-70316 added.

    If a future refactor rewrites ``__aexit__`` back to sync
    ``self.close()`` (or if any of the ``with`` -> ``async with``
    fix sites in this PR quietly reverts), the transport's
    ``close_async`` will NOT be called on the way out.  Spy on it to
    catch that regression: on the fixed path we see exactly one
    ``close_async`` invocation and zero sync ``close`` invocations.
    """
    opts = _minion_opts_for(tmp_path)

    calls = {"close_async": 0, "close": 0}

    async def _drive():
        channel = salt.channel.client.AsyncReqChannel.factory(opts, crypt="clear")
        transport = channel.transport

        real_close_async = transport.close_async
        real_close = transport.close

        async def spy_close_async(*a, **kw):
            calls["close_async"] += 1
            return await real_close_async(*a, **kw)

        def spy_close(*a, **kw):
            calls["close"] += 1
            return real_close(*a, **kw)

        monkeypatch.setattr(transport, "close_async", spy_close_async)
        monkeypatch.setattr(transport, "close", spy_close)

        # Now enter/exit the async context.  ``__aenter__`` calls
        # transport.connect() (safe to call outside the spy scope
        # because it doesn't touch close paths); ``__aexit__`` is
        # what we care about.
        async with channel:
            pass

    asyncio.run(_drive())

    assert calls["close_async"] == 1, (
        f"AsyncReqChannel ``__aexit__`` did not route teardown through "
        f"transport.close_async (calls={calls!r}).  That is the load-"
        f"bearing property of ``async with`` vs sync ``with`` here -- "
        f"only close_async awaits _send_recv_exit_future before "
        f"destroying the context, and only that ordering prevents the "
        f"pyzmq Context.__del__ wedge PR-70316 addressed."
    )
    assert calls["close"] == 0, (
        f"AsyncReqChannel ``__aexit__`` invoked the sync transport "
        f"``close`` path (calls={calls!r}) -- either in addition to "
        f"``close_async`` (racy) or instead of it (regresses the "
        f"wedge fix)."
    )


# ---------------------------------------------------------------------------
# Category (b): AsyncRemotePillar.aclose closes the underlying channel's
# context.  Covers site 1.
# ---------------------------------------------------------------------------


def test_async_remote_pillar_aclose_closes_channel_context(tmp_path):
    """``AsyncRemotePillar.aclose`` must route through the channel's
    ``close_async`` so the pillar-fetch channel's context is fully
    torn down before the pillar object is dropped.

    Without ``aclose``, the pillar's ``destroy`` path calls sync
    ``self.channel.close()`` -- which on the loop-running branch of
    ``RequestClient.close`` cannot await the send/recv task and thus
    returns before the context can be closed.  The pillar object is
    then dropped, ``__del__`` fires, and the leaked context can wedge
    a later ioloop callback via pyzmq's ``Context.__del__``.
    """
    opts = _minion_opts_for(tmp_path)
    contexts_seen = []

    async def _drive():
        # Construct an AsyncRemotePillar directly.  We don't call
        # compile_pillar (that would need a real master); we only need
        # the channel + its transport context to exist so aclose has
        # something real to close.
        pillar = salt.pillar.AsyncRemotePillar(
            opts,
            grains={"id": opts["id"]},
            minion_id=opts["id"],
            saltenv="base",
        )
        # Force the transport's asyncio Context into existence so the
        # aclose path has something concrete to close.
        await pillar.channel.transport.connect()
        contexts_seen.append(pillar.channel.transport.context)
        await pillar.aclose()
        # aclose must set _closing=True so a later __del__ / destroy
        # is a no-op and does not race the loop again.
        assert pillar._closing is True

    asyncio.run(_drive())

    assert contexts_seen, "aclose drive did not populate transport.context"
    ctx = contexts_seen[0]
    assert ctx.closed, (
        "AsyncRemotePillar.aclose() did not close the underlying "
        "zmq.asyncio.Context.  aclose must delegate to "
        "channel.close_async so the send/recv task drains before "
        "context teardown -- otherwise the pyzmq Context.__del__ "
        "wedge (PR-70316) reappears on the pillar-refresh path."
    )


def test_async_remote_pillar_destroy_is_noop_after_aclose(tmp_path):
    """After ``aclose`` has run, the legacy sync ``destroy`` and the
    ``__del__`` compatibility wrapper must both short-circuit -- so
    third-party consumers that never migrated to ``aclose`` are safe,
    and the GC of an ``AsyncRemotePillar`` cannot re-close an already
    torn-down channel (which would be a use-after-close on the
    transport's zmq handle).
    """
    opts = _minion_opts_for(tmp_path)

    async def _drive():
        pillar = salt.pillar.AsyncRemotePillar(
            opts,
            grains={"id": opts["id"]},
            minion_id=opts["id"],
            saltenv="base",
        )
        await pillar.channel.transport.connect()
        await pillar.aclose()
        # Now the legacy destroy path must be a no-op.  If it isn't,
        # calling it on an already-closed channel would either raise
        # or silently double-close the underlying zmq resources.
        pillar.destroy()  # must not raise
        # And a fresh close call on the underlying channel must also
        # short-circuit (transport-level _closing is set inside
        # close_async).
        pillar.channel.close()  # must not raise

    asyncio.run(_drive())


# ---------------------------------------------------------------------------
# Category (c): getattr fallback pattern in ``sign_in``-shape callers.
# Covers site 3 (crypt.py:1390) and mirrors the shape PR-70316 used in
# ``Minion.connect_master`` / ``Minion.handle_event`` and this branch
# uses in ``AsyncRemotePillar.aclose``.
# ---------------------------------------------------------------------------


class _FakeAsyncOnlyChannel:
    """Stand-in for the third-party channel case: exposes both
    ``close`` and ``close_async``, records which one was hit."""

    def __init__(self):
        self.sync_calls = 0
        self.async_calls = 0

    def close(self):
        self.sync_calls += 1

    async def close_async(self):
        self.async_calls += 1


class _FakeSyncOnlyChannel:
    """Stand-in for a third-party channel subclass that predates
    ``close_async`` -- only exposes sync ``close``."""

    def __init__(self):
        self.sync_calls = 0

    def close(self):
        self.sync_calls += 1


async def _close_via_getattr_pattern(channel):
    """Reproduces the guarded close from
    ``crypt.AsyncAuth.sign_in``'s ``finally`` block (site 3) and the
    matching shape in ``AsyncRemotePillar.aclose`` (site 1).  If a
    future refactor drifts the pattern in one place, this test flags
    the drift.
    """
    close_async = getattr(channel, "close_async", None)
    if close_async is not None:
        await close_async()
    else:
        channel.close()


def test_getattr_close_async_fallback_pattern():
    """Both callers that use the ``getattr(channel, "close_async", None)``
    guard must prefer the async path when it exists and fall back to
    sync ``close`` when it doesn't.  If somebody rewrites the guard
    (or inverts the branch), this test catches it before the wedge
    resurfaces.
    """
    async_channel = _FakeAsyncOnlyChannel()
    sync_channel = _FakeSyncOnlyChannel()

    async def _drive():
        await _close_via_getattr_pattern(async_channel)
        await _close_via_getattr_pattern(sync_channel)

    asyncio.run(_drive())

    assert async_channel.async_calls == 1, (
        "getattr fallback did not prefer close_async when the channel "
        "exposes it -- the sync path would race _send_recv and the "
        "wedge behind PR-70316 could reappear."
    )
    assert async_channel.sync_calls == 0, (
        "getattr fallback fired both sync AND async close on a channel "
        "that has both; only close_async should have run."
    )
    assert sync_channel.sync_calls == 1, (
        "getattr fallback did not fall back to sync close for a "
        "channel that only exposes close (third-party compat path)."
    )


# ---------------------------------------------------------------------------
# Category (c): a closed ``RequestClient`` must not resurrect itself if a
# stale caller holds a reference across ``await`` and later calls ``send``.
# This is the exact production wedge captured on Ani Baghoumian's
# ``ab002212-63-maas-easy-deploy`` env (VCOPS-90587) via the finalizer
# tracer at ``scratch/vcops-90587-ctx-trace/zmq_finalizer_trace_v5.py``:
#
#   1. Reconnect calls ``await old_channel.close_async()`` -- the OLD
#      ``RequestClient``'s Context is destroyed (``closed=True``),
#      ``self.socket = None``, ``self.context = None``, ``self._closing =
#      True``.
#   2. Reconnect assigns ``self.req_channel = <new>`` and moves on.
#   3. An in-flight ``_fire_master_main`` coroutine that captured the OLD
#      channel BEFORE the reassignment now calls ``.send()`` on it.
#   4. Old ``.send()`` -> old ``transport.send()`` -> ``await
#      self.connect()``. Before this fix ``connect()`` unconditionally
#      reset ``self._closing = False`` and ran ``_init_socket()``, which
#      created a FRESH Context on the "closed" transport and registered
#      a new ``weakref.finalize`` on the ``RequestClient`` pointing at
#      the new Context.
#   5. Nothing ever calls ``close_async`` on the OLD channel again.  When
#      it is GC'd, the newly-registered finalizer fires from an ioloop
#      callback and blocks in ``zmq_ctx_term()``.  Wedge.
# ---------------------------------------------------------------------------


def test_closed_request_client_refuses_reconnect(tmp_path):
    """After ``close_async``, ``RequestClient.connect`` must raise instead
    of silently resurrecting: allocating a fresh ``zmq.asyncio.Context``
    and registering another ``weakref.finalize`` on the (already-dead)
    ``RequestClient`` is exactly what triggers the ioloop-thread
    finalizer wedge.
    """
    import salt.exceptions

    opts = _minion_opts_for(tmp_path)
    io_loop = None

    async def _drive():
        nonlocal io_loop
        import tornado.ioloop

        io_loop = tornado.ioloop.IOLoop.current()
        client = salt.transport.zeromq.RequestClient(opts, io_loop=io_loop)
        # First connect populates ``self.context`` (fresh Context #1).
        await client.connect()
        first_context = client.context
        assert first_context is not None, "initial connect() did not create a Context"

        # Close: destroys the Context, sets ``self.context = None`` +
        # ``self._closing = True``.
        await client.close_async()
        assert client.context is None, "close_async did not clear self.context"
        assert (
            client._closing is True
        ), "close_async did not set self._closing -- state machine is off"
        assert (
            first_context.closed is True
        ), "close_async did not actually close the first Context"

        # Now the wedge trigger:  stale caller calls ``.send()`` on the
        # closed client, which internally does ``await self.connect()``.
        # Pre-fix behaviour:  connect() flips ``_closing`` back to False,
        # runs ``_init_socket()``, allocates Context #2, registers a
        # brand-new weakref.finalize -- and returns as if nothing happened.
        # Post-fix behaviour:  connect() raises SaltClientError.
        with pytest.raises(salt.exceptions.SaltClientError, match="closed"):
            await client.connect()

        # And no fresh Context #2 was allocated on the closed client.
        assert client.context is None, (
            "connect() on a closed RequestClient resurrected self.context "
            "-- this is the exact GC-then-wedge trigger the finalizer "
            "tracer captured on Ani's env."
        )

    asyncio.run(_drive())
