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
RSS_LEAK_KB_PER_MIN = _env_int("RSS_LEAK_KB_PER_MIN", 200)
MASTER_FD_LEAK_PER_MIN = _env_int("MASTER_FD_LEAK_PER_MIN", 30)
# Bytes/sec threshold used by the prometheus master-RSS slope check.
MASTER_RSS_LEAK_BYTES_PER_SEC = _env_int("MASTER_RSS_LEAK_BYTES_PER_SEC", 10240)


# Scenario-selection ping timeout.
PING_TIMEOUT_SEC = _env_int("PING_TIMEOUT_SEC", 15)
