"""
Regression tests for four TCP PubServer backpressure findings on 3008.x.

Each test encodes a bug that a 2026-08-26 fuzz run reproduced on
``origin/3008.x`` tip ``b959cedd9da`` and asserts the post-fix behavior
recommended in the corresponding fuzz report:

  * ``agents/reports/fuzz-eventpublisher-3008x-20260826-0921.md``
  * ``agents/reports/fuzz-pubserverchannel-3008x-20260826-0918.md``

Findings covered
----------------

* **P1** -- per-``Subscriber`` ``msgpack.Unpacker`` has no
  ``max_buffer_size`` cap; each subscriber pins ~1 MB of C-heap on
  msgpack 1.2.1 (200-sub master = 200 MB just to idle).  Fix: pass a
  bounded ``max_buffer_size`` (and preferably a smaller ``read_size``)
  when constructing the per-subscriber ``Unpacker`` in
  ``PubServer._stream_read``.

* **P3** -- ``ipc_write_buffer`` opt exists on 3008.x but its default
  is ``0`` (unbounded).  Slow subscribers grow their per-stream
  ``_write_buffer`` bytearray to ~47 MB before ``publish_drain_timeout``
  fires.  Fix: ship a bounded default on master/3008.x so the operator
  gets backpressure without opt-in.

* **R1-2026-08 / N2** -- ``PubServer.publish_payload`` schedules one
  ``asyncio.ensure_future(_make_drain_task(client)(fut))`` per
  subscriber per event.  A 20 000-event burst against 8 subscribers
  produced 160 000 drain tasks and drove RSS to 820 MB; a 100 000-event
  burst hit 2.9 GB and starved the io_loop.  Fix (recommended in the
  fuzz report): per-``Subscriber`` writer coroutine draining from a
  bounded ``asyncio.Queue`` so in-flight drain tasks per subscriber are
  capped at a small constant.

* **N1** -- when ``_discard_slow_client`` fires, in-flight drain tasks
  for the discarded subscriber are not cancelled.  Their closures pin
  the payload bytes + ``client`` reference for up to
  ``publish_drain_timeout`` seconds (default 5 s).  Fix: cancel those
  drain tasks in ``_discard_slow_client`` so the closures release.

All four tests are marked ``xfail(strict=True)`` because they encode
the post-fix contract; they will start failing loudly (and CI will
notice) the moment the fix ships and the ``xfail`` needs to come off.
"""

import asyncio

import pytest
import tornado.concurrent
import tornado.ioloop
import tornado.iostream

import salt.config
import salt.transport.tcp
import salt.utils.msgpack
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]


# ---------------------------------------------------------------------------
# P1: per-Subscriber msgpack.Unpacker must have a bounded max_buffer_size.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "unfixed on 3008.x head as of 2026-08-26 -- PubServer._stream_read "
        "constructs salt.utils.msgpack.Unpacker() with no max_buffer_size, "
        "pinning ~1 MB C-heap per subscriber (fuzz report "
        "agents/reports/fuzz-pubserverchannel-3008x-20260826-0918.md, "
        "finding P1)"
    ),
)
async def test_pub_server_stream_read_unpacker_has_max_buffer_size_cap(
    master_opts, io_loop
):
    """
    Post-fix contract: ``PubServer._stream_read`` must construct its
    per-subscriber ``salt.utils.msgpack.Unpacker`` with a bounded
    ``max_buffer_size`` kwarg (and, per the fuzz report, a smaller
    ``read_size`` / ``buf_size`` too).  Without a cap the msgpack C-heap
    per subscriber is ~1 MB on msgpack 1.2.1 -- 200 subscribers pin
    ~200 MB of resident memory just to idle.

    See ``salt/transport/tcp.py:1422`` and finding P1 in the fuzz
    report at
    ``agents/reports/fuzz-pubserverchannel-3008x-20260826-0918.md``.

    This test intercepts the ``Unpacker`` constructor with
    ``monkeypatch.setattr`` on ``salt.utils.msgpack.Unpacker`` (the
    exact symbol ``PubServer._stream_read`` uses) and records the
    kwargs.  If the reader passed ``max_buffer_size`` bounded to a
    "sane" cap (< 128 MB, well above any legitimate event but below
    the unbounded default), the fix is in and the test passes.
    """
    ctor_kwargs = []

    class _RecordingUnpacker:
        def __init__(self, *args, **kwargs):
            ctor_kwargs.append(kwargs)

        def feed(self, data):  # pragma: no cover - exercised via read loop
            return None

        def __iter__(self):
            return iter(())

    class _EOFStream:
        def read_bytes(self, *args, **kwargs):
            # Return immediately closed so ``_stream_read`` allocates
            # its Unpacker and then exits its ``while not self._closing``
            # loop on the first read.
            raise tornado.iostream.StreamClosedError()

    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    client = MagicMock()
    client.stream = _EOFStream()
    client.address = "p1-cap-client"

    with patch("salt.utils.msgpack.Unpacker", _RecordingUnpacker):
        await server._stream_read(client)

    assert ctor_kwargs, "PubServer._stream_read never constructed an Unpacker"
    kwargs = ctor_kwargs[0]
    # Fix contract: max_buffer_size must be present and bounded.  The
    # exact value is a design choice -- the fuzz report suggests 16 MB
    # (well above any legitimate frame); anything > 0 and reasonably
    # small counts.  A missing kwarg -- the current 3008.x behavior --
    # is the bug.
    assert "max_buffer_size" in kwargs, (
        "Unpacker constructed without max_buffer_size -- per-subscriber "
        "C-heap grows unbounded on msgpack 1.2.1; see fuzz report P1"
    )
    cap = kwargs["max_buffer_size"]
    assert (
        isinstance(cap, int) and cap > 0
    ), f"max_buffer_size must be a positive int (got {cap!r})"
    assert cap <= 128 * 1024 * 1024, (
        f"max_buffer_size={cap} is effectively unbounded -- the fix's "
        "intent is a sane per-subscriber cap (< 128 MB)"
    )


# ---------------------------------------------------------------------------
# P3: ipc_write_buffer must default to a bounded value on 3008.x/master.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "unfixed on 3008.x head as of 2026-08-26 -- "
        "salt.config.apply_master_config() forces ipc_write_buffer=0 when "
        "the operator hasn't set it, so slow subscribers can grow the "
        "per-stream write buffer to ~47 MB before publish_drain_timeout "
        "fires (fuzz report "
        "agents/reports/fuzz-pubserverchannel-3008x-20260826-0918.md, "
        "recommendation R2-2026-08 / P3)"
    ),
)
def test_master_default_ipc_write_buffer_is_bounded(tmp_path):
    """
    Post-fix contract: a master config with no ``ipc_write_buffer``
    override must resolve to a bounded (> 0) default on 3008.x /
    master.  The 3006.x/3007.x LTS branches keep the historical
    ``0``/unset behavior (no default flips on LTS per project policy),
    but on 3008.x the fuzz report recommends a sane default (e.g.
    128 MB) so slow subscribers get sharp backpressure via
    ``StreamBufferFullError`` instead of unbounded buffer growth
    followed by a 5-second ``publish_drain_timeout``.

    See ``salt/config/__init__.py`` around line 4256-4259
    (``apply_master_config``) and finding P3 / R2-2026-08 in
    ``agents/reports/fuzz-pubserverchannel-3008x-20260826-0918.md``.
    """
    root_dir = tmp_path / "master"
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        (root_dir / name).mkdir(parents=True, exist_ok=True)
    conf_dir = root_dir / "conf_dir"
    conf_file = conf_dir / "master"
    conf_file.write_text("")  # empty master config -- no overrides at all

    opts = salt.config.master_config(str(conf_file))
    opts["root_dir"] = str(root_dir)

    cap = opts.get("ipc_write_buffer", 0)
    assert cap and cap > 0, (
        "Default master ipc_write_buffer is 0 (unbounded) on 3008.x; "
        "the fuzz report recommends a bounded default (e.g. 128 MB) so "
        "slow-subscriber writes trip StreamBufferFullError instead of "
        "growing the tornado _StreamBuffer without bound"
    )


# ---------------------------------------------------------------------------
# R1-2026-08 / N2: in-flight drain tasks per subscriber must be capped.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("burst_size", [1000])
async def test_pub_server_publish_payload_caps_in_flight_drain_tasks(
    master_opts, io_loop, burst_size
):
    """
    Post-fix contract: after N publishes to a subscriber whose write
    futures do not resolve, the number of in-flight drain tasks for
    that subscriber must be bounded (fuzz report recommends per-
    subscriber writer coroutine reading from a bounded
    ``asyncio.Queue(maxsize<=64)``; cap here = 64).

    Current 3008.x behavior: ``publish_payload`` at
    ``salt/transport/tcp.py:1668-1681`` calls
    ``asyncio.ensure_future(_make_drain_task(client)(fut))`` per
    subscriber per event.  A 1000-event burst against one slow
    subscriber leaves ~1000 pending drain tasks, each holding a
    ``TimerHandle`` for ``asyncio.wait_for`` + a ``_drain`` coroutine
    closure that pins ``client`` and the write future.  A production
    100k-burst hits 2.9 GB RSS and starves the io_loop (see
    ``fuzz-eventpublisher-3008x-20260826-0921.md`` finding F3-2026-08).

    A per-subscriber writer coroutine reading from a bounded queue
    keeps in-flight drain tasks capped at a small constant regardless
    of burst size.  We assert <= 64 outstanding drain tasks per
    subscriber after a 1000-event burst; the current code produces
    ~1000.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    # A single "slow" subscriber whose stream.write() returns a
    # never-resolving Future.  Every publish schedules a drain task
    # that parks on ``asyncio.wait_for(fut, timeout=drain_timeout)``.
    pending_write_futures = []

    def _slow_write(payload):
        fut = tornado.concurrent.Future()
        pending_write_futures.append(fut)
        return fut

    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = _slow_write
    client.id_ = "slow"
    client.address = "slow-sub-address"
    server.clients = {client}

    # Snapshot the asyncio task set before the burst so we can diff.
    loop = asyncio.get_running_loop()
    tasks_before = {id(t) for t in asyncio.all_tasks(loop)}

    for _ in range(burst_size):
        await server.publish_payload({"foo": "bar"})

    # Let the io_loop scheduler run one turn so any Task objects that
    # ``ensure_future`` scheduled become visible in ``all_tasks``.
    await asyncio.sleep(0)

    new_tasks = [
        t for t in asyncio.all_tasks(loop) if id(t) not in tasks_before and not t.done()
    ]
    try:
        drain_task_count = len(new_tasks)
        # Fix contract: per-subscriber cap on in-flight drain tasks.
        # A per-subscriber writer coroutine (one Task per subscriber)
        # reading from a bounded queue yields 1 outstanding Task per
        # sub regardless of burst size; even generous cap of 64
        # catches the unbounded-scheduling bug.
        assert drain_task_count <= 64, (
            f"{drain_task_count} in-flight drain tasks after {burst_size} "
            "publishes to one subscriber -- publish_payload is scheduling "
            "one asyncio.Task per (subscriber, event) with no cap; see "
            "R1-2026-08 in fuzz-eventpublisher-3008x-20260826-0921.md"
        )
    finally:
        # Resolve the parked write futures so the drain tasks can
        # exit; then cancel any remaining so the event loop teardown
        # doesn't warn about pending tasks.
        for fut in pending_write_futures:
            if not fut.done():
                fut.set_exception(tornado.iostream.StreamClosedError())
        for t in new_tasks:
            if not t.done():
                t.cancel()
        # Yield so cancellation delivers.
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        except Exception:  # pylint: disable=broad-except
            pass
        server.close()


# ---------------------------------------------------------------------------
# N1: _discard_slow_client must cancel in-flight drain tasks for the client.
# ---------------------------------------------------------------------------


async def test_discard_slow_client_cancels_pending_drain_tasks(master_opts, io_loop):
    """
    Post-fix contract: when ``_discard_slow_client`` fires (either from
    a drain timeout or from an operator-forced removal), all drain
    tasks that were scheduled for that subscriber must be cancelled --
    otherwise their ``_drain`` closures keep the ``client`` reference
    and the ``payload`` bytes alive for up to ``publish_drain_timeout``
    seconds (default 5 s).

    Current behavior: ``_discard_slow_client`` at
    ``salt/transport/tcp.py:1481-1504`` calls ``client.close()`` and
    removes the client from ``self.clients``, but doesn't track or
    cancel the ``asyncio.Task`` objects that ``publish_payload``
    scheduled.  The fuzz report measured **46 MB of retained payload
    bytes at ``tornado/iostream.py:991`` *after* the slow subscriber
    was already discarded** (finding N1).

    Test strategy: publish 100 events to a slow subscriber, snapshot
    the set of outstanding drain-task ``Task`` objects, call
    ``_discard_slow_client`` for that subscriber, and assert those
    tasks are cancelled (or gone from ``asyncio.all_tasks``) after one
    event loop turn.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    pending_write_futures = []

    def _slow_write(payload):
        fut = tornado.concurrent.Future()
        pending_write_futures.append(fut)
        return fut

    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = _slow_write
    client.stream.closed.return_value = False
    client.id_ = "slow"
    client.address = "slow-sub-address"
    server.clients = {client}

    loop = asyncio.get_running_loop()
    tasks_before = {id(t) for t in asyncio.all_tasks(loop)}

    for _ in range(100):
        await server.publish_payload({"foo": "bar"})
    await asyncio.sleep(0)

    drain_tasks_before_discard = [
        t for t in asyncio.all_tasks(loop) if id(t) not in tasks_before and not t.done()
    ]
    try:
        # If R1-2026-08 lands too and caps the per-subscriber task
        # count at ~1, the count is much smaller but the invariant we
        # test here still holds: whatever drain-side tasks exist for
        # this subscriber must go away when the subscriber is
        # discarded.  Guard against a totally empty diff so the test
        # doesn't vacuously pass on a code path where publish_payload
        # decided not to schedule any tasks at all.
        assert drain_tasks_before_discard, (
            "no drain tasks were scheduled -- test setup did not "
            "reproduce the pre-condition for N1"
        )

        server._discard_slow_client(client, reason="test-forced")
        # Give asyncio one turn to deliver ``.cancel()`` to the drain
        # coroutines that the fix should have called it on.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        still_alive = [t for t in drain_tasks_before_discard if not t.done()]
        assert not still_alive, (
            f"{len(still_alive)} drain tasks still pending after "
            "_discard_slow_client returned; their closures pin the "
            "payload bytes and client reference for up to "
            "publish_drain_timeout seconds -- fuzz report N1"
        )
    finally:
        # Resolve/cancel to avoid stray "Task was destroyed but pending"
        # warnings from the io_loop teardown.
        for fut in pending_write_futures:
            if not fut.done():
                fut.set_exception(tornado.iostream.StreamClosedError())
        for t in drain_tasks_before_discard:
            if not t.done():
                t.cancel()
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        except Exception:  # pylint: disable=broad-except
            pass
        server.close()
