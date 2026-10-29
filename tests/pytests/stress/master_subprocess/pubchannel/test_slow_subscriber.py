"""
Slow-subscriber behavior of ``PubServerChannel._publish_daemon``.

The important production mechanism these tests pin:

* zeromq PUB drops messages **silently** to subscribers whose SUB
  receive queue is over ``pub_hwm``.  The subscriber has no way to
  detect the drop from its socket alone — the connection stays "up"
  from its perspective, but events go missing.
* tcp PUB, in contrast, does **not** drop.  It doesn't set
  ``max_write_buffer_size`` on the per-subscriber tornado ``IOStream``,
  so per-client write buffers grow without bound; the publisher process
  RSS climbs and the fast subscribers get slowed down but the slow SUB
  is never dropped by the publisher.  This is a different failure mode
  from what the prompt described as "StreamBufferFullError path"; that
  path is never entered in production because the limit is unset.

These tests document both behaviors so regressions in either direction
(zmq: drops become visible / stop happening; tcp: master starts
dropping OR starts holding write buffers past new limits) show up as
CI-detectable diffs rather than silent behavior changes.
"""

from __future__ import annotations

import time

import pytest

from tests.pytests.stress.master_subprocess.pubchannel.helpers import (
    make_pusher,
    make_subscriber,
)

# ---------------------------------------------------------------------------
# zeromq: silent HWM drop
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_zmq_slow_subscriber_drops_are_invisible(publisher):
    """
    ZeroMQ PUB drops overflow to a slow SUB silently.

    Reproduce the production bug we want a regression guard for:
    * a fast SUB and a slow SUB attach.
    * we publish more events than fit in the per-connection PUB
      SNDHWM (default ``pub_hwm=1000``).
    * the slow SUB never drains but its socket appears "still
      connected" to itself.
    * observe missing events on the slow SUB without any error / close
      notification on its socket.

    The PUB SNDHWM is per outbound connection, so filling the slow SUB's
    queue does NOT starve the fast SUB.  We assert that: fast SUB gets
    everything, slow SUB gets far less than everything, slow SUB's
    socket still ``getpeername()``-s (no FIN / RST / error).
    """
    if publisher.transport != "zeromq":
        pytest.skip("zmq-only mechanism")

    n_events = 5000
    payload_bytes = b"x" * 4096  # 4 KiB / event, > default MTU

    fast = make_subscriber(publisher)
    slow = make_subscriber(publisher, rcvhwm=10)

    fast.connect()
    fast.start_reader()
    slow.connect()
    # NOTE: we do NOT start slow's reader.  Its OS receive buffer +
    # zmq RCVHWM fill fast; then the PUB's per-connection SNDHWM (=1000)
    # fills; then further messages targeted at that SUB are silently
    # dropped by the PUB.
    time.sleep(1.0)  # settle SUB subscriptions (PUB slow-joiner)

    try:
        with make_pusher(publisher) as pusher:
            for i in range(n_events):
                pusher.send(payload_bytes + f"-{i}".encode())
            # Fast SUB should get everything (PUB SNDHWM is per-connection).
            got_all_fast = fast.wait_for_frames(n_events, timeout=30.0)

        # Let the slow SUB accumulate what it can into its OS buffer.
        time.sleep(1.0)

        # Now drain the slow SUB to see how much it captured.
        slow.start_reader()
        time.sleep(2.0)
        slow.stop_reading()

        assert got_all_fast, (
            f"fast SUB only got {len(fast.frames)}/{n_events} — "
            "PUB SNDHWM is shared across connections, that would be a regression"
        )
        drained_slow = len(slow.frames)
        # The whole point: slow SUB lost events.
        assert drained_slow < n_events, (
            f"slow SUB received {drained_slow} of {n_events} — silent "
            "drop mechanism did not fire, HWM behavior may have changed"
        )
        # And critically: from the slow SUB's OWN socket view, it is
        # still connected.  No FIN, no RST, no zmq disconnect event.
        # This is the production regression guard — the master silently
        # dropped a good chunk of its events and the minion has no
        # local socket signal that anything went wrong.
        assert (
            slow.socket_thinks_connected()
        ), "slow SUB was closed by publisher — zmq PUB drop-visibility changed"
        assert publisher.is_alive(), "publisher died while shedding load"
    finally:
        fast.close()
        slow.close()


# ---------------------------------------------------------------------------
# tcp: unbounded write buffer (documented, NOT the StreamBufferFullError path)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_tcp_slow_subscriber_is_not_dropped(publisher):
    """
    Pin the (surprising) TCP behavior: a slow SUB is **not** dropped.

    ``PubServer`` creates per-subscriber ``tornado.iostream.IOStream``
    instances without ``max_write_buffer_size``, so the write buffer
    grows without bound.  The prompt's "StreamBufferFullError path"
    would only be reached if that limit were set.  This test guards
    against a silent policy change: if someone starts setting the limit,
    this test will start failing (slow SUB drops), and we can decide
    whether that's the intended new behavior.
    """
    if publisher.transport != "tcp":
        pytest.skip("tcp-only mechanism")

    n_events = 500
    payload = b"x" * 512  # 512 B/event

    fast = make_subscriber(publisher)
    slow = make_subscriber(publisher, so_rcvbuf=4096)

    fast.connect()
    fast.start_reader()
    slow.connect()
    # slow: never start reader, and clamp SO_RCVBUF so its OS buffer
    # fills quickly — this makes the master's per-client write buffer
    # grow without needing to publish enormous volume.
    time.sleep(0.2)

    try:
        with make_pusher(publisher) as pusher:
            for i in range(n_events):
                pusher.send(payload + f"-{i}".encode())

            # Fast subscriber drains everything.
            assert fast.wait_for_frames(
                n_events, timeout=15.0
            ), f"fast SUB drained {len(fast.frames)}/{n_events}"

        # Give the master a moment to notice if it were going to close
        # the slow subscriber.
        time.sleep(1.0)

        # Slow SUB is NOT closed by the master — no FIN, no RST.  If
        # this assertion fails, someone added a per-subscriber buffer
        # cap to the tcp PubServer.  That may be a good change, but
        # this test needs updating in that case.
        assert (
            slow.socket_thinks_connected()
        ), "slow SUB was dropped — tcp PubServer added a write-buffer cap?"
        assert publisher.is_alive(), "publisher died under slow-SUB load"
    finally:
        fast.close()
        slow.close()


# ---------------------------------------------------------------------------
# Backpressure: many subscribers
# ---------------------------------------------------------------------------


@pytest.mark.timeout(90)
def test_many_slow_subscribers_do_not_starve_fast_ones(publisher):
    """
    With 20 subscribers, half draining slowly / not at all, the fast
    half must still receive every event.

    * On zeromq: slow subs are dropped by HWM; fast subs get everything.
    * On tcp: slow subs backpressure the write path (per-client await
      of ``client.stream.write(...)``), but the publisher uses
      ``asyncio.gather``-style concurrent write dispatch — see
      #66282 fix — so the fast subs still see everything without waiting
      on the slow ones.
    """
    n_events = 400
    n_fast = 10
    n_slow = 10

    fast_subs = [make_subscriber(publisher) for _ in range(n_fast)]
    slow_subs = [make_subscriber(publisher) for _ in range(n_slow)]

    for s in fast_subs:
        s.connect()
        s.start_reader()
    for s in slow_subs:
        s.connect()
        # never start reader — total starvation.

    time.sleep(0.5)  # subs settle before we push

    try:
        with make_pusher(publisher) as pusher:
            for i in range(n_events):
                pusher.send(f"e-{i}".encode())
            for s in fast_subs:
                assert s.wait_for_frames(
                    n_events, timeout=30.0
                ), f"fast subscriber only got {len(s.frames)}/{n_events}"
        assert publisher.is_alive()
    finally:
        for s in fast_subs + slow_subs:
            s.close()
