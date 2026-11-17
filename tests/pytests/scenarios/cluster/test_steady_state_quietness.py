"""
Scenario regression: a healthy clustered-master + minion topology must
be quiet when nothing is being published.

Pre-fix the scheduled ``__master_alive_<master>`` job on the minion
called ``status.master()``, which decided "still connected?" by
scanning the OS TCP table for the minion's own ``opts["publish_port"]``
(default 4505).  The pub channel actually connected to the
master-reported publish port from ``self.auth.creds["publish_port"]``
(an ephemeral port in saltfactories setups).  Each scheduler tick
therefore saw an empty result, fired ``__master_disconnected`` against
a healthy pub channel, and re-armed itself on reconnect -- producing a
~1 Hz flap.

In the 5-master cluster that surfaced this (``agents/reports/
status-master-impact/REPORT.md``), the flap logged 2347 ``Connection to
master ... lost`` lines per minion per 40 min.

PR #70726 (status.master) + PR #70725 (the sibling pub-channel default)
together close this.  To make the regression observable inside a
reasonable test window the fixture accelerates ``master_alive_interval``
to 3 s (vs. the Salt default 60 s) so the scheduled job fires ~20× in a
60 s observation window.  Pre-fix we would see every tick flap; post-
fix none do.
"""

import pathlib
import re
import time

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


# ``log.info("Connection to master %s lost", ...)`` is the signature
# emitted in ``Minion.handle_event`` on every spurious
# ``__master_disconnected``.  Used as the per-flap counter.
_FLAP_RE = re.compile(r"Connection to master .* lost")


def _tail(log_path, start_offset):
    """Return bytes appended to ``log_path`` since ``start_offset``."""
    if not log_path.exists():
        return ""
    with salt.utils.files.fopen(log_path, "r") as fp:
        fp.seek(start_offset)
        return fp.read()


def test_minion_is_quiet_when_idle(
    cluster_master_1, cluster_master_2, cluster_master_3, cluster_minion_fast_tick
):
    """
    Observe a steady-state minion for 60 s with ``master_alive_interval``
    = 3 s and assert zero ``Connection to master ... lost`` lines.

    Pre-fix: the status.master port-scan bug fires on every scheduler
    tick (~20× in 60 s), each producing a full pub-channel teardown +
    reconnect cycle and a matching ``Connection to master ... lost``
    INFO line in the minion log.  The historical flap rate was ~1 Hz
    -- well above a "1 or 2" slack this assertion allows for.

    Post-fix: ``status.master`` uses the authenticated publish port
    mirrored into ``opts["_auth_publish_port"]`` by
    ``AsyncPubChannel.connect()``.  The TCP table reports the healthy
    connection on the real port; no disconnect fires; the log stays
    quiet.
    """
    log_path = pathlib.Path(cluster_minion_fast_tick.config["log_file"])
    assert log_path.exists(), f"Minion log not written yet at {log_path}"
    start_offset = log_path.stat().st_size

    observation_window_s = 60
    time.sleep(observation_window_s)

    tail = _tail(log_path, start_offset)
    flap_lines = _FLAP_RE.findall(tail)

    # ``master_alive_interval`` = 3 s means ~20 scheduler ticks in the
    # 60 s window.  Pre-fix each tick flaps.  Allow a small slack for
    # genuinely transient races unrelated to the regression -- but the
    # bug's rate is an order of magnitude above this threshold.
    assert len(flap_lines) <= 2, (
        f"Minion flapped {len(flap_lines)} time(s) in {observation_window_s} s "
        f"(threshold: <= 2) -- status.master() is still firing spurious "
        f"__master_disconnected events on a healthy pub channel.  "
        f"Regression of PR #70726.\n\n" + "\n".join(flap_lines[:10])
    )
