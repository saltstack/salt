"""
Integration regression for PR #70726 / issue #66846.

``status.master()`` is called from the ``__master_alive_<master>`` scheduled
job on every minion.  It decides "still connected?" by scanning the OS TCP
table for a port and asking whether the master's resolved IP shows up there.

Pre-fix, the port it scanned was the minion's own ``opts["publish_port"]``
(default 4505).  When the master publishes on a non-default port (any
saltfactories master uses an ephemeral port), the scan found nothing and
``status.master`` returned ``False`` for a healthy pub channel -- firing
``__master_disconnected``, tearing the channel down, and re-arming the
scheduled job on reconnect.  In the 5-master cluster that surfaced this
(``agents/reports/status-master-impact/REPORT.md``) that produced a ~1 Hz
flap and 2347 spurious disconnects per minion per 40 min.

Post-fix, ``status.master`` prefers the master-reported publish port that
``AsyncPubChannel.connect()`` writes back into opts as
``_auth_publish_port``.  The scan finds the real connection and the
function returns ``True`` for a connected minion.

This test is the exact cross-module slice that the unit tests on
``test_status.py`` can't cover:

* a real ``salt-minion`` process (opts carried through pickle to the
  scheduler child process),
* against a real ``salt-master`` listening on an ephemeral publish port,
* with the saltfactories-default minion config (no ``publish_port``
  override), which is the common-case production shape that triggered
  the bug.
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout(240),
]


def test_status_master_detects_connection_on_non_default_publish_port(
    cluster_master_1, cluster_master_2, cluster_minion_1
):
    """
    ``status.master`` must return ``True`` for a connected minion when the
    master publishes on a non-default port and the minion's config has no
    ``publish_port`` override.

    Pre-fix (3008.x without PR #70726): returns ``False`` because the
    OS-table scan uses the minion-side default ``publish_port=4505`` which
    the master is not listening on.

    ``cluster_master_2`` is pulled into the dependency set so the
    ``cluster_peers: [127.0.0.2, 127.0.0.3]`` configuration can form a Raft
    quorum (2 of 3) and the minion's pillar fetch completes without
    deferring on ``cluster_retry``.
    """
    # The saltfactories master fixture picks an ephemeral publish_port --
    # if that ever becomes 4505 the test tautologically passes, so sanity
    # check up front.
    master_publish_port = int(cluster_master_1.config["publish_port"])
    assert master_publish_port != 4505, (
        f"The regression only reproduces when the master's publish_port "
        f"differs from the minion's default (4505); got "
        f"{master_publish_port}.  Fixture changed?"
    )

    minion_addr = cluster_master_1.config["interface"]

    cli = cluster_master_1.salt_cli(timeout=60)
    ret = cli.run(
        "status.master",
        f"master={minion_addr}",
        "connected=True",
        minion_tgt=cluster_minion_1.id,
    )
    assert (
        ret.returncode == 0
    ), f"salt call failed: stdout={ret.stdout!r}, stderr={ret.stderr!r}"
    assert ret.data is True, (
        f"status.master(master={minion_addr!r}, connected=True) returned "
        f"{ret.data!r} on a known-connected minion.  Regression of PR #70726: "
        f"the scheduled __master_alive job is scanning the wrong port "
        f"(minion default 4505, not master-reported ephemeral "
        f"{master_publish_port}).  Pre-fix this would fire a spurious "
        f"__master_disconnected event every scheduler tick."
    )
