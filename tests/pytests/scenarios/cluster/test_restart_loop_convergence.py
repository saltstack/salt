"""
Scenario regression: a cluster that is cycled (daemons stopped and
re-started) must re-converge cleanly on each cycle, and must not
re-emit the ``[CRITICAL]`` / ``[ERROR]`` signatures PR #70729 and
PR #70732 silenced.

Two restart paths are exercised:

* The minion restart cycle re-walks the minion's startup path.  Pre-fix
  PR #70729, every restart on a ``master_type: failover`` minion
  re-emits the ``retry_dns`` auto-correction at ``[CRITICAL]``; this
  test asserts it does not.  (Covers the same regression as
  ``test_bootstrap_race.py`` but across multiple consecutive startups,
  which is where operators actually hit it under rolling-restart
  playbooks.)
* The master restart cycle re-walks the Raft leader-election + peer-
  publisher cache paths.  Pre-fix PR #70732's latent ``_running = None``
  reset was a repeat-failover bug (first-master retry task left
  silently unbound); regression here is visible as ``test.ping`` not
  returning through a peer master after the cycle.

Together: each restart cycle must converge, produce clean
``test.ping``, and emit zero ``[CRITICAL]`` in the restarted minion
log.  Pre-fix the CRITICAL line fires once per minion startup.
"""

import pathlib
import time

import pytest

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


@pytest.fixture
def restart_cycle_minion(cluster_master_1, cluster_master_2):
    """
    Minion configured so every startup goes through the ``retry_dns``
    auto-correction branch (``master_type: failover`` + ``retry_dns >
    0``).  Pre-fix PR #70729 this emits a ``[CRITICAL]`` on every
    startup -- so three restart cycles produce three CRITICAL hits.
    Post-fix: zero, across any number of cycles.
    """
    port = cluster_master_1.config["ret_port"]
    config_overrides = {
        "master": [
            f"{cluster_master_1.config['interface']}:{port}",
            f"{cluster_master_2.config['interface']}:{port}",
        ],
        "master_type": "failover",
        "retry_dns": 10,
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-restart",
        defaults={"transport": cluster_master_1.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


def _ping(cli, minion_id, cycle_tag):
    ret = cli.run("test.ping", minion_tgt=minion_id)
    assert ret.data is True, (
        f"test.ping failed after cycle {cycle_tag} -- cluster did not "
        f"converge after the restart.  Possible regression of PR "
        f"#70732 latent-correctness ``_running`` reset.  Raw: {ret!r}"
    )


def test_cluster_restart_cycles_are_quiet_and_converge(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    restart_cycle_minion,
):
    """
    Two full restart cycles.  Each cycle:

    1. SIGTERM the subject daemon (minion, then a peer master).
    2. Re-start it (``stopped()`` re-emits the original start args).
    3. Confirm ``test.ping`` returns True through ``cluster_master_1``.

    After both cycles the minion log is scanned for ``[CRITICAL]``.
    Pre-fix PR #70729 each minion restart re-emits the ``retry_dns``
    auto-correction at CRITICAL (so at minimum 2 hits across the
    cycles, 3 counting the initial bringup).  Post-fix: 0.
    """
    cli = cluster_master_1.salt_cli(timeout=60)
    minion_log = pathlib.Path(restart_cycle_minion.config["log_file"])
    assert minion_log.exists()

    # Initial-bringup assertion establishes the baseline.
    _ping(cli, restart_cycle_minion.id, "initial")

    # Cycle 1 -- restart the minion.  ``stopped()`` returns a context
    # manager that terminates the daemon and re-starts it on exit.
    with restart_cycle_minion.stopped():
        time.sleep(1)
    time.sleep(5)
    _ping(cli, restart_cycle_minion.id, "minion-restart")

    # Cycle 2 -- restart a peer master.
    with cluster_master_2.stopped():
        time.sleep(1)
    time.sleep(10)
    _ping(cli, restart_cycle_minion.id, "master-restart")

    # Now scan the (restarted) minion log for CRITICAL lines emitted
    # at any point during the test.  The ``retry_dns`` auto-correction
    # fires on every startup -- so at least 2 hits pre-fix (initial +
    # minion-restart).
    with salt.utils.files.fopen(minion_log, "r") as fp:
        log_text = fp.read()

    critical_lines = [
        line
        for line in log_text.splitlines()
        if "[CRITICAL" in line and "retry_dns" in line
    ]
    assert not critical_lines, (
        f"Minion emitted {len(critical_lines)} ``[CRITICAL]`` line(s) "
        f"for the ``retry_dns`` auto-correction across the restart "
        f"cycles -- regression of PR #70729 (the auto-correction "
        f"should log at INFO on every bringup).\n\n" + "\n".join(critical_lines[:5])
    )
