"""
RSS regression for ReqChannel churn against a live master (#68637).

Salt API and ``LocalClient.pub`` create a short-lived ``ReqChannel`` per call.
Uses the integration ``salt_master`` / ``salt_minion`` stack plus
``salt.client.LocalClient.pub(..., listen=False)``, which wraps the real
publish REQ path (without waiting on the master event bus).

Linux VmRSS via /proc. Post-warmup growth over 80 ``pub`` calls capped at ~17 MiB
(empirical lab + headroom; see test docstring).

Refs #68637. See also
``tests/pytests/functional/transport/zeromq/test_reqchannel_memory.py``.
"""

from __future__ import annotations

import gc
import sys

import pytest

import salt.client

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
@pytest.mark.timeout(480)
def test_localclient_pub_churn_bounded_rss_under_live_master(
    client_config,
    salt_master,
    salt_minion,
):
    """
    Each iteration runs ``LocalClient.pub`` (fresh ``ReqChannel`` per publish).

    Looser than the functional ``connect()``-only churn test: each iteration
    allocates the full publish REQ payload on a real master. Lab sample (Ubuntu,
    zeromq): VmRSS grew ~12.9 MiB across 80 publishes after warmup; ceiling is
    ~35% headroom over that for allocator / CI jitter. #68637 regressions show
    far steeper ramps than this budget allows.
    """
    if salt_master.config.get("transport") != "zeromq":
        pytest.skip(
            "Zeromq ReqChannel teardown regression tracked only under transport=zeromq"
        )

    assert salt_master.is_running()
    assert salt_minion.is_running()

    _warmup_iters = 60
    _measured_iters = 80
    # Observed max ~12920 KiB Δ over 80 publishes (Ubuntu 2404 zeromq lab); ~1.35× margin.
    _max_delta_rss_kb = 17408

    lc = salt.client.LocalClient(mopts=dict(client_config))

    def _one_iteration():
        try:
            ret = lc.pub(
                salt_minion.id,
                "test.ping",
                listen=False,
                timeout=30,
                tgt_type="list",
            )
        except Exception as exc:
            pytest.fail(f"LocalClient.pub against live master failed: {exc!r}")

        assert isinstance(ret, dict)
        assert ret.get("jid"), f"unexpected publish return: {ret!r}"

    def _burn(n: int):
        for _ in range(n):
            _one_iteration()

    _burn(_warmup_iters)
    gc.collect()
    rss_mid = _linux_vmrss_kb()

    _burn(_measured_iters)
    gc.collect()
    rss_end = _linux_vmrss_kb()

    delta_kb = rss_end - rss_mid
    assert delta_kb <= _max_delta_rss_kb, (
        f"VmRSS grew by {delta_kb} kB over {_measured_iters} publish iterations "
        f"after warmup (limit {_max_delta_rss_kb} kB); see #68637"
    )
