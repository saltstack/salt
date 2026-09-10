"""
Peer churn: 100 subscribers connect + drain a few + disconnect in a
loop.  Publisher FD count and RSS must stay bounded.
"""

from __future__ import annotations

import time

import pytest

import salt.utils.platform
from tests.pytests.stress.master_subprocess.pubchannel.conftest import fd_count, rss_kb
from tests.pytests.stress.master_subprocess.pubchannel.helpers import (
    make_pusher,
    make_subscriber,
)


@pytest.mark.timeout(90)
def test_peer_churn_bounded_fd_and_rss(publisher):
    """
    100 rounds of {connect, receive a couple frames, disconnect}.

    The publisher's FD count must be ~constant across rounds (bounded
    ceiling, not linear growth), and RSS must not grow more than a few
    MiB — resource-leak canary for either transport's subscriber
    lifecycle path.
    """
    baseline_fd = fd_count(publisher.pid)
    baseline_rss = rss_kb(publisher.pid)

    with make_pusher(publisher) as pusher:
        # Steady-state background publishing so churning peers actually
        # exercise the write / drop path, not just accept/close.
        for round_ in range(100):
            sub = make_subscriber(publisher)
            sub.connect()
            sub.start_reader()
            # Push a couple messages so the peer is added to
            # ``pub_server.clients`` and the fast path runs.
            for i in range(3):
                pusher.send(f"round-{round_}-{i}".encode())
            # Let the subscriber receive at least one before we drop it
            # — otherwise on zmq PUB slow-joiner it may never see any.
            sub.wait_for_frames(1, timeout=1.0)
            sub.close()

    # Give the publisher a beat to garbage-collect its ``clients`` set.
    time.sleep(1.5)

    final_fd = fd_count(publisher.pid)
    final_rss = rss_kb(publisher.pid)

    fd_growth = final_fd - baseline_fd
    rss_growth_kb = final_rss - baseline_rss

    assert publisher.is_alive(), "publisher died after 100 peer-churn rounds"
    # FD ceiling: absolute number, not per-round.  Tornado holds a
    # handful of FDs per accept/close cycle briefly; 30 is plenty of
    # slack for either transport.
    assert fd_growth < 30, f"FD count grew by {fd_growth} across 100 peer-churn rounds"
    # RSS: 100 churn rounds shouldn't cost more than a few MiB.  25 MiB
    # is generous on x86_64.
    #
    # aarch64 note: glibc's per-thread malloc arenas on aarch64 default
    # to 64 MiB each; tornado / zmq / msgpack allocations across the
    # churn loop can pin one or two extra arenas that never get returned
    # to the OS.  We've observed 88-102 MiB one-shot expansion on Photon
    # OS 5 Arm64 that does not compound across repeat rounds (cached
    # allocator state, not a leak).  Widen the ceiling on aarch64 so
    # this canary still catches genuine runaway leaks without flagging
    # arena caching.
    max_growth_kb = 200_000 if salt.utils.platform.is_aarch64() else 25_000
    assert (
        rss_growth_kb < max_growth_kb
    ), f"RSS grew by {rss_growth_kb} KiB across 100 peer-churn rounds (ceiling {max_growth_kb} KiB)"
