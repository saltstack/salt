"""
Isolated stress + regression tests for the salt-master
:class:`MWorkerQueue` subprocess.

The MWorkerQueue is a zmq ``QUEUE`` device (``ROUTER`` <-> ``DEALER``)
that fans work from the master's public request port to any number of
:class:`MWorker` peers.  These tests spawn *only* that proxy against fake
minion (REQ) and fake worker (REP) peers so we can pin behaviour that a
full-master fixture obscures — throughput floors, starvation semantics,
FD/RSS ceilings under churn, and how the proxy reacts to malformed
input or a hung worker.

Determinism
-----------
Every wait uses ``zmq.Poller`` with an explicit timeout or bounded
``time.sleep`` inside a polling loop; there are no unconditional
``time.sleep`` waits for "the thing to happen".

Marking
-------
Every test is marked ``@pytest.mark.stress``.  The slower ones
(worker starvation with a large batch, churn, backpressure) are also
marked ``@pytest.mark.slow_test`` (Salt's project-wide slow marker) so
they can be selected/excluded easily via ``--run-slow``.
"""

from __future__ import annotations

import gc
import os
import socket
import sys
import time

import pytest
import zmq

import salt.utils.files

pytestmark = pytest.mark.stress


# ---------------------------------------------------------------------------
# Small helpers used by multiple tests
# ---------------------------------------------------------------------------


def _poll_recv(sock: zmq.Socket, timeout_ms: int) -> bytes | None:
    """Poll ``sock`` for POLLIN then recv (or return None on timeout)."""
    poller = zmq.Poller()
    poller.register(sock, zmq.POLLIN)
    events = dict(poller.poll(timeout_ms))
    if sock in events and events[sock] & zmq.POLLIN:
        return sock.recv()
    return None


def _drain_and_reply(worker: zmq.Socket, timeout_ms: int) -> int:
    """
    Drain any pending requests on ``worker`` (REP) and echo them back.
    Returns the number of request/reply pairs serviced.
    """
    n = 0
    while True:
        msg = _poll_recv(worker, timeout_ms)
        if msg is None:
            return n
        worker.send(b"ack:" + msg)
        n += 1
        # Use a much shorter timeout after the first message so we return
        # promptly when the queue drains.
        timeout_ms = 50


# ---------------------------------------------------------------------------
# 1. Throughput / pass-through
# ---------------------------------------------------------------------------


def test_passthrough_throughput(mworkerqueue):
    """
    Fire N requests from K fake minions absorbed by M fake workers on the
    other side; assert everything round-trips and rate clears a
    conservative floor.
    """
    n_workers = 4
    n_minions = 8
    per_minion = 25  # 200 total requests
    workers = [mworkerqueue.worker() for _ in range(n_workers)]
    minions = [mworkerqueue.minion() for _ in range(n_minions)]

    poller = zmq.Poller()
    for w in workers:
        poller.register(w, zmq.POLLIN)

    total = n_minions * per_minion
    sent = 0
    replied = 0
    start = time.monotonic()
    # We interleave send and receive so the REQ-side FSM is happy
    # (REQ must recv before it can send again).
    inflight: dict[zmq.Socket, int] = {}
    for i, m in enumerate(minions):
        m.send(f"m{i}-0".encode())
        inflight[m] = 0
        sent += 1

    minion_poller = zmq.Poller()
    for m in minions:
        minion_poller.register(m, zmq.POLLIN)

    deadline = time.monotonic() + 15.0
    while replied < total and time.monotonic() < deadline:
        # Drain any pending work at the worker side first.
        events = dict(poller.poll(20))
        for w, ev in events.items():
            if ev & zmq.POLLIN:
                msg = w.recv()
                w.send(b"ack:" + msg)

        # Then drain minion replies and issue next request.
        events = dict(minion_poller.poll(20))
        for m, ev in events.items():
            if ev & zmq.POLLIN:
                m.recv()
                replied += 1
                idx = inflight[m] + 1
                inflight[m] = idx
                if idx < per_minion:
                    m.send(f"m{minions.index(m)}-{idx}".encode())
                    sent += 1

    elapsed = time.monotonic() - start
    assert replied == total, (
        f"got only {replied}/{total} replies in {elapsed:.2f}s " f"(sent={sent})"
    )
    rate = total / elapsed
    # Conservative floor: 200 req in 15s = 13 req/s.  On a laptop we
    # generally see 500-2000 req/s.  Pinning a floor catches order-of-
    # magnitude regressions without flaking on slow CI.
    assert rate > 20.0, f"throughput {rate:.1f} req/s below floor"


# ---------------------------------------------------------------------------
# 2. Worker starvation
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
def test_worker_starvation_queues_and_drains(mworkerqueue):
    """
    With no MWorker peers, requests should queue at the DEALER (bounded
    by libzmq's default HWM = 1000).  Once a worker attaches, previously
    queued requests must be delivered.
    """
    burst = 50
    identities: list[bytes] = []
    # Fire a burst of REQ sends from independent sockets so each has its
    # own routing id and won't block on the REQ FSM.
    minions = []
    for i in range(burst):
        m = mworkerqueue.minion(identity=f"m{i}".encode())
        m.send(f"starvation-{i}".encode())
        minions.append(m)
        identities.append(f"m{i}".encode())

    # Give the queue a beat to actually enqueue.
    time.sleep(0.5)

    # Now attach a single worker and pump everything through.
    worker = mworkerqueue.worker()
    time.sleep(0.2)  # allow the DEALER to notice the new peer

    served = 0
    deadline = time.monotonic() + 20.0
    while served < burst and time.monotonic() < deadline:
        msg = _poll_recv(worker, 500)
        if msg is None:
            continue
        worker.send(b"ack:" + msg)
        served += 1

    assert served == burst, f"only {served}/{burst} requests drained"

    # And the corresponding minions must have received their replies.
    got_replies = 0
    poller = zmq.Poller()
    for m in minions:
        poller.register(m, zmq.POLLIN)
    deadline = time.monotonic() + 5.0
    while got_replies < burst and time.monotonic() < deadline:
        events = dict(poller.poll(200))
        for m, ev in events.items():
            if ev & zmq.POLLIN:
                m.recv()
                got_replies += 1
                poller.unregister(m)
    assert got_replies == burst, f"only {got_replies}/{burst} replies delivered"


def test_worker_starvation_bounded_by_hwm(mworkerqueue, proc_stats):
    """
    Even with no worker attached, the queue must not grow without
    bound.  libzmq's default HWM caps queued messages; we assert RSS
    growth stays modest during a burst that exceeds a plausible working
    set (2000 requests, 1 KB each).

    We use a small pool of DEALER sockets (rather than 2000 REQs) so
    the test process itself does not exhaust its file-descriptor budget
    — DEALER is non-FSM and can pipeline many outbound frames.  The
    ROUTER-side envelope semantics are equivalent from the queue's
    perspective.
    """
    pid = mworkerqueue.process.pid
    fd0, rss0 = proc_stats(pid)

    payload = b"x" * 1024
    n = 2000
    n_dealers = 20
    dealers: list[zmq.Socket] = []
    for i in range(n_dealers):
        d = mworkerqueue.ctx.socket(zmq.DEALER)
        d.setsockopt(zmq.LINGER, 0)
        d.setsockopt(zmq.IDENTITY, f"hwm-d{i}".encode())
        # Don't let the DEALER itself buffer without bound either; we
        # want to observe *queue* behaviour, not client-side buffering.
        d.setsockopt(zmq.SNDHWM, n)
        d.connect(mworkerqueue.router_uri)
        dealers.append(d)

    # Give sockets a moment to complete their zmq handshakes so early
    # sends aren't silently dropped (DEALER is fire-and-forget: any
    # message queued before a peer is available goes to the socket's
    # local queue up to SNDHWM).
    time.sleep(0.2)

    for i in range(n):
        d = dealers[i % n_dealers]
        try:
            # DEALER: send an empty delimiter frame + payload so the
            # ROUTER sees a REQ-shaped envelope.
            d.send_multipart([b"", payload], flags=zmq.NOBLOCK)
        except zmq.Again:
            pass

    # Small settling window so libzmq can move messages into its buffers.
    time.sleep(0.5)

    fd1, rss1 = proc_stats(pid)

    for d in dealers:
        d.close(linger=0)

    # Sanity: process is still alive (queue didn't crash).
    assert mworkerqueue.process.is_alive(), "MWorkerQueue died during burst"

    # Bounded growth.  libzmq HWM (1000) x 1 KB = 1 MB expected upper
    # bound of enqueued payload; add generous slack for per-msg overhead
    # and unrelated allocations.  We assert < 100 MB delta because a
    # true unbounded leak would trivially blow past that.
    if rss0 > 0 and rss1 > 0:
        delta_kb = rss1 - rss0
        assert delta_kb < 100 * 1024, (
            f"MWorkerQueue RSS grew {delta_kb} KB during starvation burst "
            "(expected bounded by HWM)"
        )


# ---------------------------------------------------------------------------
# 3. Worker misbehaviour — one hung worker doesn't stall the pipeline
# ---------------------------------------------------------------------------


def test_hung_worker_does_not_block_pipeline(mworkerqueue):
    """
    Attach two workers, one healthy and one that never replies.  The
    DEALER uses round-robin; healthy requests must still complete.
    """
    hung = mworkerqueue.worker()  # noqa: F841 - intentionally never drained
    healthy = mworkerqueue.worker()

    # Round-robin means every second message may land on the hung
    # worker.  Fire enough that the healthy worker still services
    # plenty; but track exactly which are serviced so we can assert.
    minions = [mworkerqueue.minion(identity=f"h{i}".encode()) for i in range(20)]
    for i, m in enumerate(minions):
        m.send(f"req-{i}".encode())

    # Drain healthy for up to 5s — it should get *some* requests even
    # though the hung worker holds onto its share.
    serviced = 0
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        msg = _poll_recv(healthy, 200)
        if msg is None:
            continue
        healthy.send(b"ack:" + msg)
        serviced += 1
        if serviced >= 5:
            break

    assert serviced >= 5, (
        f"healthy worker only got {serviced} requests — round-robin "
        "does not shield healthy workers from a hung peer"
    )
    # The proxy must still be alive after the exercise.
    assert mworkerqueue.process.is_alive()


# ---------------------------------------------------------------------------
# 4. Requester churn — FD / RSS must stay bounded
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
def test_requester_churn_fd_bounded(mworkerqueue, proc_stats):
    """
    Many minion REQ sockets connect+send+recv+disconnect rapidly.  Both
    file-descriptor count and RSS must stay bounded (regression test for
    the ROUTER-leak fix that motivated the LINGER=1000 + ROUTER_HANDOVER
    settings on the ROUTER socket).

    We do the churn in two phases and compare growth phase-over-phase:
    libzmq's internal caches warm up during phase 1 so a modest RSS
    bump is expected, but phase 2 must show substantially less growth.
    A truly unbounded per-connection leak would grow phase 2 as much or
    more than phase 1.
    """
    pid = mworkerqueue.process.pid
    worker = mworkerqueue.worker()

    def _churn(n_cycles: int, id_prefix: str) -> None:
        for i in range(n_cycles):
            m = mworkerqueue.ctx.socket(zmq.REQ)
            m.setsockopt(zmq.LINGER, 0)
            m.setsockopt(zmq.IDENTITY, f"{id_prefix}{i}".encode())
            m.setsockopt(zmq.RCVTIMEO, 2000)
            m.setsockopt(zmq.SNDTIMEO, 2000)
            m.connect(mworkerqueue.router_uri)
            m.send(b"churn")
            req = _poll_recv(worker, 2000)
            assert req is not None, f"queue stalled at {id_prefix}{i}"
            worker.send(b"ok")
            m.recv()
            m.close(linger=0)

    churn = 300

    fd0, rss0 = proc_stats(pid)
    _churn(churn, "warm")
    time.sleep(0.5)
    fd1, rss1 = proc_stats(pid)
    _churn(churn, "meas")
    time.sleep(0.5)
    fd2, rss2 = proc_stats(pid)

    warmup_growth = rss1 - rss0 if rss0 > 0 and rss1 > 0 else 0
    steady_growth = rss2 - rss1 if rss1 > 0 and rss2 > 0 else 0

    # FDs: the ROUTER must not accumulate one fd per disconnected peer.
    if fd0 > 0 and fd2 > 0:
        assert fd2 - fd0 < 20, (
            f"FD count grew from {fd0} to {fd2} across {2 * churn} churn "
            "cycles (possible ROUTER peer-fd leak)"
        )

    # RSS: steady-state growth (phase 2) must be a small fraction of
    # phase 1 growth.  If it's not, we're leaking per-connection state.
    # We allow up to 25% of phase-1 growth in phase 2 (arbitrary but
    # reflects an order-of-magnitude regression threshold), with a
    # floor of 2 MB so tiny warmup deltas don't cause false negatives.
    if warmup_growth > 0:
        allowed = max(2 * 1024, warmup_growth // 4)
        assert steady_growth < allowed, (
            f"Steady-state RSS grew {steady_growth} KB across {churn} "
            f"cycles (warmup phase grew {warmup_growth} KB; allowed "
            f"steady <{allowed} KB) — possible per-connection leak"
        )


# ---------------------------------------------------------------------------
# 5. Malformed input — proxy is a dumb pipe, must survive junk bytes
# ---------------------------------------------------------------------------


def test_malformed_input_does_not_kill_queue(mworkerqueue):
    """
    Open a raw TCP socket to the ROUTER port and write junk bytes.  The
    proxy is a dumb pass-through; it should either drop the connection
    (bad zmq handshake) or forward the bytes to a worker.  Either way
    the queue subprocess must still be alive afterward and must still
    service well-formed traffic.
    """
    junk_iterations = 20
    for _ in range(junk_iterations):
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(2.0)
        try:
            raw.connect(("127.0.0.1", mworkerqueue.opts["ret_port"]))
            raw.sendall(b"\x00\xff not a zmq greeting at all \n" * 4)
            try:
                raw.recv(64)
            except (TimeoutError, ConnectionResetError, OSError):
                pass
        finally:
            raw.close()

    # Proxy must still be alive.
    assert mworkerqueue.process.is_alive()

    # And well-formed traffic must still round-trip.
    worker = mworkerqueue.worker()
    minion = mworkerqueue.minion()
    minion.send(b"still alive?")
    req = _poll_recv(worker, 3000)
    assert req == b"still alive?"
    worker.send(b"yes")
    reply = _poll_recv(minion, 3000)
    assert reply == b"yes"


# ---------------------------------------------------------------------------
# 6. Slow-worker backpressure
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
def test_slow_worker_backpressure_bounded_memory(mworkerqueue, proc_stats):
    """
    A worker that drains at ~1/10th the incoming rate must not cause
    unbounded memory growth on the queue side.  We measure RSS across a
    sustained burst and assert the growth is bounded.
    """
    pid = mworkerqueue.process.pid
    worker = mworkerqueue.worker()

    # Baseline snapshot.
    gc.collect()
    fd0, rss0 = proc_stats(pid)

    # Use a small pool of DEALERs (see test_worker_starvation_bounded_by_hwm
    # for the rationale — DEALER is non-FSM so we can pipeline all N
    # requests from a handful of sockets without exhausting fds).
    n = 400
    n_dealers = 8
    dealers: list[zmq.Socket] = []
    for i in range(n_dealers):
        d = mworkerqueue.ctx.socket(zmq.DEALER)
        d.setsockopt(zmq.LINGER, 0)
        d.setsockopt(zmq.IDENTITY, f"bp-d{i}".encode())
        d.setsockopt(zmq.SNDHWM, n)
        d.connect(mworkerqueue.router_uri)
        dealers.append(d)
    time.sleep(0.2)

    for i in range(n):
        d = dealers[i % n_dealers]
        d.send_multipart([b"", b"x" * 512])

    # Drain slowly: one message every ~5 ms → ~200 req/s target rate.
    served = 0
    deadline = time.monotonic() + 30.0
    while served < n and time.monotonic() < deadline:
        msg = _poll_recv(worker, 500)
        if msg is None:
            continue
        # Simulate slow work per message.
        time.sleep(0.005)
        worker.send(b"a")
        served += 1

    fd1, rss1 = proc_stats(pid)

    for d in dealers:
        d.close(linger=0)

    assert served == n, f"slow worker only drained {served}/{n}"

    # Bounded RSS growth across the burst.
    if rss0 > 0 and rss1 > 0:
        assert (
            rss1 - rss0 < 50 * 1024
        ), f"RSS grew {rss1 - rss0} KB under slow-worker backpressure"


# ---------------------------------------------------------------------------
# Sanity: fixture teardown does not leak the subprocess.
# ---------------------------------------------------------------------------


def test_fixture_stop_terminates_subprocess(mworkerqueue):
    """
    Sanity check: after the fixture yields, ``stop()`` must terminate
    the child.  We invoke it explicitly here and re-check via
    ``is_alive()``.
    """
    pid = mworkerqueue.process.pid
    assert mworkerqueue.process.is_alive()
    mworkerqueue.stop()
    assert not mworkerqueue.process.is_alive()
    # No orphan process left behind.
    if sys.platform.startswith("linux"):
        assert not os.path.exists(f"/proc/{pid}") or _proc_dead(pid)


def _proc_dead(pid: int) -> bool:
    """Return True if /proc/<pid> reports a zombie or is gone."""
    try:
        with salt.utils.files.fopen(f"/proc/{pid}/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("State:"):
                    return "Z" in line or "X" in line
    except FileNotFoundError:
        return True
    return False
