"""
Throughput floor: attach N subscribers, publish M events, everyone
receives all events at some minimum rate.

This is intentionally a low floor (well under the master's real-world
rate) — the point is to catch regressions like "publisher wedges" or
"messages dropped even without backpressure", not to grade absolute
performance on shared CI hardware.
"""

from __future__ import annotations

import time

import pytest

from tests.pytests.stress.master_subprocess.pubchannel.helpers import (
    make_pusher,
    make_subscriber,
)


@pytest.mark.timeout(60)
def test_all_subscribers_receive_all_events(publisher):
    n_subs = 5
    n_events = 200
    subs = []
    for _ in range(n_subs):
        s = make_subscriber(publisher)
        s.connect()
        s.start_reader()
        subs.append(s)

    # Let subs finish connecting before we start pushing.  This matters
    # especially for zmq PUB — subscriptions racing with the first
    # publishes get dropped silently (zmq PUB slow-joiner problem).
    time.sleep(0.5)

    try:
        with make_pusher(publisher) as pusher:
            start = time.monotonic()
            for i in range(n_events):
                pusher.send(f"payload-{i}".encode())
            # Every subscriber must receive every event within a generous
            # bound.  On a healthy publisher this is well under 5s for 200
            # events across 5 subs on any machine that can run tests.
            for s in subs:
                assert s.wait_for_frames(
                    n_events, timeout=15.0
                ), f"subscriber only got {len(s.frames)}/{n_events} frames"
            elapsed = time.monotonic() - start

        # Throughput floor: 100 events/s per subscriber.  On slow shared
        # CI this may need to be relaxed, but 200 events across 5 subs in
        # 10 s is already glacial.
        rate = (n_events * n_subs) / elapsed
        assert (
            rate > 100.0
        ), f"pub rate {rate:.1f} evt/s below floor (elapsed {elapsed:.2f}s)"
        assert publisher.is_alive()
    finally:
        for s in subs:
            s.close()
