"""
Zeromq HWM behavior: verify ``pub_hwm`` actually caps the per-subscriber
outgoing queue on the master.

For a PUB socket the default HWM behavior is *silent drop* — this test
pins that behavior so a change from drop-to-block (which would wedge
the entire publisher loop) shows up immediately in CI.
"""

from __future__ import annotations

import time

import pytest

from tests.pytests.stress.master_subprocess.pubchannel.helpers import (
    make_pusher,
    make_subscriber,
)


@pytest.mark.timeout(60)
@pytest.mark.parametrize("publisher_opts_overrides", [{"pub_hwm": 10}], indirect=True)
def test_zmq_pub_hwm_caps_queue_via_silent_drop(publisher):
    """
    With ``pub_hwm=10`` the PUB drops silently instead of blocking.

    Setup:
    * Attach a SUB but do NOT drain it — its OS buffer plus zmq
      RCVHWM fill quickly.
    * Push 500 events of 4 KiB each.
    * Publisher does NOT wedge (pushes complete quickly).
    * Publisher stays alive.

    The zmq PUB socket documented behavior is
    ``ZMQ_XPUB_NODROP=0`` (default): silently drop when SNDHWM is
    reached.  If someone flips this in Salt, ``pusher.send()`` calls
    would start blocking indefinitely and this test would time out.
    """
    if publisher.transport != "zeromq":
        pytest.skip("zmq-only HWM test")

    n_events = 500
    payload = b"x" * 4096

    stalled = make_subscriber(publisher, rcvhwm=10)
    stalled.connect()
    # DO NOT start_reader — the SUB stays stalled.
    time.sleep(0.5)  # settle subscription

    try:
        with make_pusher(publisher) as pusher:
            start = time.monotonic()
            for i in range(n_events):
                pusher.send(payload + f"-{i}".encode())
            elapsed = time.monotonic() - start

        # If PUB were blocking on HWM, this would take much longer than
        # a normal burst.  On my dev box 500 4KiB events over the pull
        # socket completes in <0.5 s even when PUB is dropping.  Give
        # ourselves generous headroom for CI — 10 s is way more than a
        # non-blocking burst but way less than a blocking one (which
        # would hit the 60 s test timeout).
        assert (
            elapsed < 10.0
        ), f"push burst took {elapsed:.1f}s — HWM policy may have changed to block"
        # Publisher stays alive.
        assert publisher.is_alive(), "publisher died under HWM pressure"
    finally:
        stalled.close()
