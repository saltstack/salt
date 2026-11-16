"""Duration tiers for the Salt resiliency test suite.

Each tier is keyed to a salt-side timeout boundary (not a round number
inherited from stress-test precedent).  Scenario tests pick one of the
TIER_* values for the fault hold and the matching RECOVER_* for the
reconnect assertion window.

Environment overrides: every constant honors ``RESILIENCY_<NAME>`` in
``os.environ``, so a one-off run can widen or narrow a tier without
editing code.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    """Return int from env ``RESILIENCY_<NAME>`` or default."""
    raw = os.environ.get(f"RESILIENCY_{name}")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"RESILIENCY_{name}={raw!r} must be an integer") from exc


# Reference: salt's own default timeouts.  Named so the tier values
# below are self-documenting (sub-keepalive, 3x keepalive, etc).
SALT_MASTER_ALIVE_INTERVAL = _env_int("SALT_MASTER_ALIVE_INTERVAL", 30)
SALT_AUTH_TIMEOUT = _env_int("SALT_AUTH_TIMEOUT", 60)
SALT_REQUEST_CHANNEL_TIMEOUT = _env_int("SALT_REQUEST_CHANNEL_TIMEOUT", 60)


# Fault-hold tiers.
#
#   SUBKEEPALIVE  25    < master_alive_interval; data path only, keepalive silent
#   FIRSTMISS     35    > master_alive_interval; first keepalive miss fires
#   STANDARD      90    3x keepalive; reconnect state machine fully engaged
#   DEEPREC       300   5 min; multiple auth_timeout retries
#   BACKOFF       600   10 min; exponential-backoff caps
#   ACCUM         1800  30 min; the long-outage concurrent-auth race floor
#   MARATHON      3600  1 h; #70772 fix target
#   UPGRADE       7200  2 h; real-world upgrade-window scale
TIER_SUBKEEPALIVE_SEC = _env_int("TIER_SUBKEEPALIVE_SEC", 25)
TIER_FIRSTMISS_SEC = _env_int("TIER_FIRSTMISS_SEC", 35)
TIER_STANDARD_SEC = _env_int("TIER_STANDARD_SEC", 90)
TIER_DEEPREC_SEC = _env_int("TIER_DEEPREC_SEC", 300)
TIER_BACKOFF_SEC = _env_int("TIER_BACKOFF_SEC", 600)
TIER_ACCUM_SEC = _env_int("TIER_ACCUM_SEC", 1800)
TIER_MARATHON_SEC = _env_int("TIER_MARATHON_SEC", 3600)
TIER_UPGRADE_SEC = _env_int("TIER_UPGRADE_SEC", 7200)


# Recovery-window pairs.  How long assert_reconnect waits for every
# minion to answer test.ping after the fault is cleared.  Wider for
# deeper outages where exponential backoff might land the minion
# mid-sleep when the fault clears.
RECOVER_FAST_SEC = _env_int("RECOVER_FAST_SEC", 60)
RECOVER_STANDARD_SEC = _env_int("RECOVER_STANDARD_SEC", 180)
RECOVER_LONG_SEC = _env_int("RECOVER_LONG_SEC", 300)
RECOVER_MARATHON_SEC = _env_int("RECOVER_MARATHON_SEC", 600)


# Pacing between phases.
PACING_INTER_PHASE_SEC = _env_int("PACING_INTER_PHASE_SEC", 30)
PACING_ROLLING_SEC = _env_int("PACING_ROLLING_SEC", 60)


# Leak thresholds (shared with the bash suite's lib/common.sh).
#
# The leak-fail rule is "fd_delta > 0 OR rss_delta_kb > LEAK_BULK_RSS_KB"
# AND "rss_per_min > RSS_LEAK_KB_PER_MIN".  fd accumulation is the
# primary leak signature; the bulk-RSS guard catches ``fd_delta == 0``
# cases where ~10 MB+ is retained in a single phase (typical of
# auth-state or event-cache growth after a long-outage marathon).
RSS_LEAK_KB_PER_MIN = _env_int("RSS_LEAK_KB_PER_MIN", 200)
LEAK_BULK_RSS_KB = _env_int("LEAK_BULK_RSS_KB", 5000)
# ``fd_delta`` is summed across every minion in the topology.  A thin
# signal (e.g. +2 across 5 minions = 0.4 fd/minion) is below the noise
# floor: a single lingering async-return socket, a chunked register
# fork-pair spike, or a mid-pillar-refetch sampling race on ANY one
# minion accounts for +1.  Gate ``leak_fd`` on a per-minion threshold
# so the fleet scale doesn't produce false positives.  Default 1
# fd/minion matches the empirical floor demonstrated by local
# reproduction on mm-failover (single-minion churn fork-pair spike
# of +14 above steady, settled within 500 ms).
MIN_FD_DELTA_PER_MINION = _env_int("MIN_FD_DELTA_PER_MINION", 1)
# Quiet window applied between a successful ping sweep and the AFTER
# sample inside ``assert_reconnect``.  ``sample_minions`` is
# instantaneous, which lands exactly when the minion's return-channel
# fork is still open on single-minion topologies (demonstrated on the
# mm-failover minion_churn repro: +14 fds above steady, settled within
# 500 ms).  2 s is enough for the transient fork pair / docker-exec
# children to drain without materially inflating per-test wall time.
# Set to 0 to disable.
SAMPLE_SETTLE_SEC = _env_int("SAMPLE_SETTLE_SEC", 2)
MASTER_FD_LEAK_PER_MIN = _env_int("MASTER_FD_LEAK_PER_MIN", 30)
# Bytes/sec threshold used by the prometheus master-RSS slope check.
MASTER_RSS_LEAK_BYTES_PER_SEC = _env_int("MASTER_RSS_LEAK_BYTES_PER_SEC", 10240)


# Scenario-selection ping timeout.
PING_TIMEOUT_SEC = _env_int("PING_TIMEOUT_SEC", 15)
