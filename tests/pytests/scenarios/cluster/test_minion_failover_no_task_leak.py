"""
Scenario regression: a minion that fails over between masters must not
emit ``[WARNING]`` level ``Master ip address changed from %s to %s``
lines -- this is the intended behaviour of ``master_alive_interval``
DNS refresh and the failover path, not an operator-actionable signal.

PR #70729 (``Lower log level of helpful-behavior startup messages``)
demoted three always-emitted messages that were mis-categorised as
``[WARNING]`` or ``[CRITICAL]``:

* ``'master_type' set to 'failover' but 'retry_dns' is not 0`` --
  CRITICAL → INFO (covered by ``test_bootstrap_race.py``).
* ``Master ip address changed from %s to %s`` -- WARNING → INFO
  (covered by *this* test).
* ``Peer key missing`` during cluster startup race -- WARNING → INFO.

The master-IP-changed signature fires every time the pub-channel or
req-channel resolves the master host to a different IP, which is the
nominal failover trigger in a multi-master setup.  Pre-fix the WARNING
pollutes any failover round.  Post-fix it is INFO.

Separately, this test also scans for ``Task was destroyed but it is
pending!`` in case the ``_spawn_background`` strong-reference fix
(PR #70750) is reverted; that signature is more elusive under
saltfactories than it is in ``docker compose`` teardown (the GC
dynamics are different), so it is a secondary assertion -- the
failure is the message-text + level mismatch above.
"""

import pathlib
import re
import time

import pytest

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


_MASTER_IP_CHANGED_WARNING_RE = re.compile(
    r"\[WARNING\s*\].*Master ip address changed from .* to .*",
    re.IGNORECASE,
)
_TASK_DESTROYED = "Task was destroyed but it is pending"


@pytest.fixture
def failover_minion(cluster_master_1, cluster_master_2):
    """
    A minion with ``master_type: failover`` subscribed to two cluster
    masters so forcing a failover trips the ``Master ip address
    changed`` line in ``salt.minion``.
    """
    port = cluster_master_1.config["ret_port"]
    config_overrides = {
        "master": [
            f"{cluster_master_1.config['interface']}:{port}",
            f"{cluster_master_2.config['interface']}:{port}",
        ],
        "master_type": "failover",
        "retry_dns": 0,
        "master_alive_interval": 3,
        "auth_tries": 20,
        "auth_timeout": 5,
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-failover-leak",
        defaults={"transport": cluster_master_1.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


def test_failover_does_not_log_master_ip_changed_warning(
    cluster_master_1, cluster_master_2, failover_minion
):
    """
    Trigger a minion failover (by SIGTERMing the current master) and
    confirm the resulting ``Master ip address changed from X to Y``
    log line is emitted at ``[INFO]``, not ``[WARNING]``.

    Pre-fix PR #70729 the first failover emits one or more
    ``[WARNING]``-level lines with that message text.  Post-fix the
    same message appears only at ``[INFO]``.

    The regression is deterministic across the pre-fix / post-fix
    boundary: the message always fires on failover; only its level
    changed.
    """
    log_path = pathlib.Path(failover_minion.config["log_file"])
    assert log_path.exists(), f"Minion log not written yet at {log_path}"
    start_offset = log_path.stat().st_size

    # Force failover: SIGTERM master_1 so the minion has to pivot to
    # master_2.  The ``master_alive_interval`` is short on this
    # fixture, so the switch happens quickly.
    cluster_master_1.terminate()

    # Leave the minion a window to notice and fail over.
    time.sleep(15)

    with salt.utils.files.fopen(log_path, "r") as fp:
        fp.seek(start_offset)
        tail = fp.read()

    # Confirm the failover actually executed -- we need the
    # ``Master ip address changed`` text to appear in the log at
    # SOME level.  If this fails the fixture no longer triggers the
    # scenario PR #70729 is regression-tested against.
    assert "Master ip address changed from" in tail, (
        "Failover never fired ``Master ip address changed`` -- the "
        "fixture no longer triggers the scenario PR #70729 covers."
    )

    # The regression itself: the line must not appear at WARNING
    # level.  PR #70729 demoted it to INFO.
    warning_hits = _MASTER_IP_CHANGED_WARNING_RE.findall(tail)
    assert not warning_hits, (
        f"Minion emitted {len(warning_hits)} "
        f"``[WARNING] Master ip address changed from X to Y`` line(s) "
        f"after a cluster-master failover.  Regression of PR #70729 "
        f"(the line should log at INFO).\n\n" + "\n".join(warning_hits[:5])
    )

    # Secondary: PR #70750's ``_spawn_background`` strong-ref fix.
    # ``Task was destroyed but it is pending!`` in saltfactories is
    # less deterministic than in a docker ``compose down`` because
    # GC dynamics differ, so this is a best-effort secondary check.
    task_hits = [line for line in tail.splitlines() if _TASK_DESTROYED in line]
    assert not task_hits, (
        f"Minion log contains {len(task_hits)} ``Task was destroyed`` "
        f"warning(s) after a failover -- regression of PR #70750 "
        f"(``_spawn_background`` strong-reference leak).\n\n" + "\n".join(task_hits[:5])
    )
