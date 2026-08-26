"""
Per-subprocess stress + regression tests for :class:`salt.master.MWorker`.

Runs MWorker in isolation — no full master, no minion — using the
shared ``mworker`` fixture in ``conftest.py``.  Each test exercises a
single failure mode or throughput floor.

The traffic used here is cleartext ``ping``, which reaches
:meth:`salt.master.ClearFuncs.ping` and is echoed back.  ``ping`` was
picked because it (a) has no side effects, (b) exercises the full
DEALER → REP → transport.handle_message → MWorker._handle_payload →
_handle_clear → ClearFuncs.get_method → ping code path, and (c) has
predictable, tiny payloads that keep the memory-ceiling test's signal
crisp.
"""

import logging
import platform
import time

import pytest

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skipif(
        platform.system() != "Linux",
        reason="/proc/<pid>/status parsing is Linux-specific; "
        "these tests use it for the RSS-ceiling check.",
    ),
    pytest.mark.timeout(120),
]


def _ping(minion_id: str = "test-minion") -> dict:
    """Build a benign clear-text ping payload."""
    return {"enc": "clear", "load": {"cmd": "ping", "id": minion_id}}


# ---------------------------------------------------------------------------
# Sanity + throughput
# ---------------------------------------------------------------------------


def test_ping_roundtrip_smoke(mworker):
    """
    Baseline: a single clear ping goes out and its echo comes back.
    All subsequent throughput / concurrency / fault tests depend on
    this working.
    """
    reply = mworker.send_recv(_ping(), timeout=5.0)
    assert reply == {"cmd": "ping", "id": "test-minion"}
    assert mworker.is_alive()


@pytest.mark.timeout(60)
def test_throughput_floor_clear_ping(mworker):
    """
    Fire N sequential clear pings; assert throughput >= floor.

    Floor picked low (25 req/s) so this doesn't flake on a loaded CI
    runner or under coverage tracing, but high enough that a
    regression that adds even ~40 ms per request (e.g. accidental
    disk sync, mutex on hot path) trips the test.  Locally on a
    developer box this suite hits ~500 req/s.
    """
    n = 200
    start = time.monotonic()
    for i in range(n):
        reply = mworker.send_recv(_ping(f"m-{i}"), timeout=5.0)
        assert reply["cmd"] == "ping"
        assert reply["id"] == f"m-{i}"
    elapsed = time.monotonic() - start
    rate = n / elapsed
    log.info("ping throughput: %.1f req/s over %.2fs (n=%d)", rate, elapsed, n)
    floor = 25.0
    assert rate >= floor, (
        f"MWorker clear-ping throughput {rate:.1f} req/s below floor "
        f"{floor} req/s (n={n}, elapsed={elapsed:.2f}s)"
    )


@pytest.mark.timeout(60)
def test_concurrent_requests_no_drops(mworker):
    """
    Pipeline K requests without awaiting each reply; then drain all K
    replies.  Every request must produce exactly one reply with the
    corresponding minion id.  Verifies MWorker + the plain
    ReqServerChannel don't drop requests when the sender pipelines.

    Note that a REP socket only accepts one outstanding request at a
    time — so real pipelining would deadlock a REP peer.  MWorker's
    ``request_handler`` loop naturally serializes: it receives one,
    dispatches (awaits) and replies, then loops.  So this test really
    verifies "K requests can be queued at the DEALER→REP boundary
    without getting lost."
    """
    k = 50
    for i in range(k):
        mworker.send(_ping(f"c-{i}"))
    seen = set()
    for _ in range(k):
        reply = mworker.recv(timeout=10.0)
        seen.add(reply["id"])
    assert seen == {f"c-{i}" for i in range(k)}, (
        f"missing responses: expected {k}, saw {len(seen)} unique ids; "
        f"missing={ {f'c-{i}' for i in range(k)} - seen }"
    )


# ---------------------------------------------------------------------------
# Fault injection
# ---------------------------------------------------------------------------


def test_malformed_msgpack_drops_and_keeps_serving(mworker):
    """
    Send a payload that is not valid msgpack.  MWorker's transport
    layer decodes at :meth:`RequestServer.handle_message`; a
    ``SaltDeserializationError`` there returns ``{"msg": "bad load"}``
    without invoking the payload handler at all.  The worker must
    survive and keep serving subsequent well-formed requests.
    """
    mworker.send_raw(b"\xff\xff\xff\xff not valid msgpack \x00\x01")
    reply = mworker.recv(timeout=5.0)
    # RequestServer.handle_message returns {"msg": "bad load"} for a
    # deserialization failure.
    assert isinstance(reply, dict) and reply.get("msg") == "bad load", reply

    # Immediately follow up with a good request — must succeed.
    good = mworker.send_recv(_ping("survivor"), timeout=5.0)
    assert good == {"cmd": "ping", "id": "survivor"}
    assert mworker.is_alive()


def test_missing_enc_or_load_returns_bad_load(mworker):
    """
    ReqServerChannel.handle_message requires both ``enc`` and ``load``
    keys.  When either is absent the channel rejects the payload with
    the literal string ``"bad load"`` (a plain, non-dict reply),
    logging a warning; MWorker never sees the request.
    """
    reply = mworker.send_recv({"only_enc": "clear"}, timeout=5.0)
    # handle_message returns the bare string "bad load" here — the
    # transport encodes it via msgpack, so we get back the str.
    assert reply == "bad load", reply

    # And another shape: missing load.
    reply2 = mworker.send_recv({"enc": "clear"}, timeout=5.0)
    assert reply2 == "bad load", reply2

    # Still serving.
    assert mworker.send_recv(_ping(), timeout=5.0)["cmd"] == "ping"


def test_unknown_clear_command_returns_empty_and_keeps_serving(mworker):
    """
    A well-formed clear payload whose ``cmd`` isn't in
    ``ClearFuncs.expose_methods`` triggers the "method not exposed"
    branch: ``_handle_clear`` returns ``({}, {"fun": "send_clear"})``,
    which the channel serializes as the empty dict ``{}``.  MWorker
    logs the miss and keeps serving.
    """
    reply = mworker.send_recv(
        {"enc": "clear", "load": {"cmd": "definitely-not-a-real-cmd", "id": "m1"}},
        timeout=5.0,
    )
    assert reply == {}, reply

    # A benign follow-up still works.
    good = mworker.send_recv(_ping("after-unknown"), timeout=5.0)
    assert good["id"] == "after-unknown"


def test_id_with_null_byte_rejected_and_keeps_serving(mworker):
    """
    ``ReqServerChannel.handle_message`` explicitly rejects loads whose
    ``id`` contains a null byte (a longstanding hardening against
    filesystem-path injection into ``pki_dir/minions/<id>``).  MWorker
    stays serving.
    """
    reply = mworker.send_recv(
        {"enc": "clear", "load": {"cmd": "ping", "id": "bad\0id"}},
        timeout=5.0,
    )
    assert reply == "bad load: id contains a null byte", reply

    good = mworker.send_recv(_ping("clean-id"), timeout=5.0)
    assert good["id"] == "clean-id"


def test_requester_disconnect_midflight_leaves_worker_alive(
    _mworker_secrets, mworker_opts
):
    """
    Fire one request, close the DEALER without waiting for the reply,
    then reconnect a fresh DEALER on the same URI and make sure
    MWorker still responds.  This models a minion that drops its
    connection between "sent request" and "got reply".

    We construct this from scratch (instead of reusing the ``mworker``
    fixture) because we need to close & re-open the DEALER in the same
    test, which the fixture's teardown otherwise owns.
    """
    from tests.pytests.stress.master_subprocess.mworker.conftest import MWorkerHandle

    handle = MWorkerHandle(mworker_opts)
    handle.start(ready_timeout=15.0)
    try:
        # Send a request, then immediately drop the socket.
        handle.send(_ping("drop-me"))
        handle._dealer.close(linger=0)  # noqa: SLF001 — intentional
        handle._dealer = None
        if handle._monitor is not None:
            handle._monitor.close(linger=0)
            handle._monitor = None

        # Give the child a beat to finish processing (and hit send
        # failure on the reply if anything cares).
        time.sleep(0.5)

        # Verify child is still alive.
        assert handle.is_alive(), "MWorker exited after requester disconnected"

        # Reconnect a fresh DEALER and send a fresh request.
        import zmq
        import zmq.utils.monitor

        # Use a fresh context for the new DEALER.  Reusing handle._ctx
        # can race two ways on a loaded CI runner:
        #   1. The old DEALER's ``inproc://monitor.s-<FD>`` endpoint may
        #      still be held by the closed monitor socket; a new DEALER
        #      that recycles the same FD then hits ``Address already in
        #      use`` when ``get_monitor_socket()`` re-binds the same
        #      inproc name.
        #   2. The closed DEALER's TCP port may still be in TIME_WAIT
        #      even with ``LINGER=0``; a same-context rebind fails.
        # A fresh context sidesteps both — no shared FD table, no shared
        # inproc namespace.  ``handle.stop()`` still terms the old
        # context via ``req_channel.close()``.
        new_ctx = zmq.Context()
        new_dealer = new_ctx.socket(zmq.DEALER)
        new_dealer.setsockopt(zmq.LINGER, 0)
        bind_deadline = time.monotonic() + 5.0
        while True:
            try:
                new_dealer.bind(handle.w_uri)
                break
            except zmq.error.ZMQError:
                if time.monotonic() >= bind_deadline:
                    raise
                time.sleep(0.1)
        # Swap contexts so ``handle.stop()`` tears down the new one too.
        old_ctx = handle._ctx
        handle._ctx = new_ctx
        old_ctx.term()
        handle._dealer = new_dealer
        handle._monitor = new_dealer.get_monitor_socket()

        # Wait for REP handshake to re-establish.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if handle._monitor.poll(200):
                ev = zmq.utils.monitor.recv_monitor_message(handle._monitor)
                if ev.get("event") == zmq.Event.HANDSHAKE_SUCCEEDED:
                    break

        # MWorker had already dispatched and queued the reply for the
        # "drop-me" request before we closed the DEALER; on reconnect
        # libzmq redelivers that queued reply to our fresh DEALER
        # first.  Drain it, then send + receive a fresh request.
        try:
            stale = handle.recv(timeout=2.0)
            log.info("drained stale reply after reconnect: %r", stale)
        except TimeoutError:
            # Some libzmq versions do not redeliver buffered replies
            # after a peer identity change; that is fine too.
            log.info("no stale reply queued")

        good = handle.send_recv(_ping("after-reconnect"), timeout=10.0)
        assert good == {"cmd": "ping", "id": "after-reconnect"}
    finally:
        handle.stop()


# ---------------------------------------------------------------------------
# Memory ceiling
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
@pytest.mark.timeout(180)
def test_rss_bounded_over_5000_pings(mworker):
    """
    Fire a burst of 5000 clear pings and verify RSS growth is bounded.

    The intent is to catch a per-request leak (e.g. every ``ping``
    accumulates something in ClearFuncs) — a burst of 5000 x tiny
    payloads that grew MWorker's RSS by many MB would flag such a
    regression.  Real per-request working-set growth after warm-up is
    < 1 MB on the fixtures used here; we allow 25 MB as a comfortable
    ceiling for CI noise, coverage tracing, and Python's arena
    fragmentation.

    Marked ``slow_test`` because the burst takes 15-30 s locally and
    longer under coverage.
    """
    # Warm up so first-request allocations (module load, event init) are
    # settled before we sample the baseline RSS.
    for i in range(50):
        assert mworker.send_recv(_ping(f"warm-{i}"), timeout=5.0)["cmd"] == "ping"

    baseline_kb = mworker.rss_kb()
    log.info("MWorker RSS after warm-up: %d kB", baseline_kb)

    n = 5000
    t0 = time.monotonic()
    for i in range(n):
        reply = mworker.send_recv(_ping(f"burst-{i}"), timeout=5.0)
        assert reply["cmd"] == "ping"
    elapsed = time.monotonic() - t0

    # Small idle so any deferred cleanup (asyncio finalizers,
    # per-request task refs) runs before we sample.
    time.sleep(0.5)

    final_kb = mworker.rss_kb()
    growth_kb = final_kb - baseline_kb
    growth_mb = growth_kb / 1024.0
    log.info(
        "RSS after %d pings: %d kB (baseline %d, +%d kB / %.1f MB) in %.1fs",
        n,
        final_kb,
        baseline_kb,
        growth_kb,
        growth_mb,
        elapsed,
    )
    ceiling_mb = 25.0
    assert growth_mb < ceiling_mb, (
        f"MWorker RSS grew by {growth_mb:.1f} MB over {n} clear pings "
        f"(baseline {baseline_kb} kB, final {final_kb} kB); ceiling {ceiling_mb} MB. "
        f"This likely indicates a per-request leak."
    )


# ---------------------------------------------------------------------------
# Backpressure — MWorker must remain responsive when the event-bus IPC
# has no consumer.  MWorker fires stats/response-time events into
# EventPublisher via IPC; if EP isn't running, those fire_event calls
# must NOT wedge the request handler.  Our fixture never starts an EP,
# so this test just verifies MWorker keeps serving after the request
# handler has completed one round-trip.  A tighter reproducer (blocked
# EP that accepts a connect but never drains) belongs in the
# EventPublisher stress suite.
# ---------------------------------------------------------------------------


def test_serves_requests_with_no_event_publisher_running(mworker):
    """
    No EventPublisher is spawned by this fixture — MWorker's
    ``AESFuncs.event`` / ``ClearFuncs.event`` fire-event calls can
    therefore only ever fail to deliver.  Ensure that this does NOT
    block ``_handle_payload`` from completing.

    We do 100 pings (well beyond what a first-request lazy-connect
    quirk could hide) and require every one to round-trip within the
    per-request timeout.
    """
    for i in range(100):
        reply = mworker.send_recv(_ping(f"noEP-{i}"), timeout=5.0)
        assert reply == {"cmd": "ping", "id": f"noEP-{i}"}
    assert mworker.is_alive()
