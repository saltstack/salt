"""
RSS regression for ZeroMQ ReqChannel churn (#68637).

Unpatched ReqChannel/SyncWrapper teardown left Tornado Queue waiters bound to
stopped IOLoops, causing roughly linear VmRSS growth under repeated factory use
(e.g. salt-api). This test loops the same pattern and asserts bounded growth
between a post-warmup sample and the end of the measured window.

Runs only on Linux (VmRSS from /proc). Marked slow_test: enable with --run-slow.
Churn uses ``connect()`` only (no ``send``) so the test does not block on a
full REQ/REP Salt payload when a master replies slowly or oddly.

Manual long runs: ``tools/repro_reqchannel_churn.py`` (post-fix plateau is ~flat
after warmup; see functional test docstring).
"""

from __future__ import annotations

import gc
import getpass
import sys

import pytest

import salt.channel.client

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def _linux_vmrss_kb() -> int:
    with open("/proc/self/status", encoding="ascii") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    raise RuntimeError("VmRSS not found in /proc/self/status")


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="RSS regression uses VmRSS from /proc/self/status (Linux only).",
)
@pytest.mark.timeout(300)
def test_reqchannel_factory_churn_bounded_rss_growth(tmp_path):
    """
    After warmup, VmRSS must not climb more than `_max_delta_rss_kb` over
    `_measured_iters` iterations.

    Post-fix: `tools/repro_reqchannel_churn.py` shows an essentially flat plateau
    after warmup (e.g. ~12 KiB drift from iter 100→3000 with SAMPLE_EVERY=100).
    This budget allows far more for CI VmRSS noise while still catching #68637
    linear-growth regressions (multiple MiB over 400 churns when unpatched).
    """
    _warmup_iters = 120
    _measured_iters = 400
    _max_delta_rss_kb = 512

    sock_root = tmp_path / "salt-sock"
    sock_root.mkdir(mode=0o700)
    dummy_pki = tmp_path / "dummy-pki"
    dummy_pki.mkdir(mode=0o700)

    master_uri = "tcp://127.0.0.1:4506"

    opts = {
        "transport": "zeromq",
        "master_uri": master_uri,
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "pki_dir": str(dummy_pki),
        "id": f"rss-regression-{getpass.getuser()}",
        "sock_dir": str(sock_root),
        "__role": "minion",
        "ipv6": False,
        "ipc_mode": "tcp",
        "publisher_port": 4505,
    }

    def _one_churn_iteration():
        # connect() schedules _send_recv + opens the REQ socket — same teardown
        # path we need — without send(), which waits for a REP and can deadlock
        # SyncWrapper's worker thread against pytest-timeout when the broker
        # does not behave like a Salt master REQ worker.
        try:
            with salt.channel.client.ReqChannel.factory(
                opts,
                crypt="clear",
                master_uri=master_uri,
            ) as chan:
                chan.connect()
        except Exception:
            pytest.fail("ReqChannel churn iteration failed unexpectedly")

    def _burn(n: int):
        for _ in range(n):
            _one_churn_iteration()

    _burn(_warmup_iters)
    gc.collect()
    rss_mid = _linux_vmrss_kb()

    _burn(_measured_iters)
    gc.collect()
    rss_end = _linux_vmrss_kb()

    delta_kb = rss_end - rss_mid
    assert delta_kb <= _max_delta_rss_kb, (
        f"VmRSS grew by {delta_kb} kB over {_measured_iters} ReqChannel churn "
        f"iterations after warmup (limit {_max_delta_rss_kb} kB); "
        "see #68637 and tools/repro_reqchannel_churn.py"
    )
