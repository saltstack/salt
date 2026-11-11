"""
Scenario regression: a cluster whose masters publish on a non-default
port (any port ``!= 4505``) must still deliver published jobs to a
minion that has not been told about the port.

Two independent pre-fix bugs combine on this path:

* PR #70725 — ``AsyncPubChannel.connect()`` compared the minion's
  effective ``publish_port`` against ``4506`` (the *ret* port default)
  instead of ``4505`` (the actual publish-port default).  So a minion
  with its default ``publish_port: 4505`` was treated as "operator
  explicitly overrode", and the branch that would otherwise use the
  master-reported publish port was never taken.
* PR #70726 — ``status.master()`` scanned the OS TCP table for the
  minion's own ``publish_port`` config (default 4505) rather than the
  port the pub channel was actually using, firing spurious
  ``__master_disconnected`` on every scheduler tick.

The saltfactories cluster fixtures already make the masters' publish
port ephemeral (ports.get_unused_localhost_port()) and leave the
minion's ``publish_port`` at the Salt default (``4505``), so this
scenario is the exact mismatch that triggered the production bug.

The test asserts two things that pre-fix would both break:

1. ``test.ping`` from a cluster master to the minion returns ``True``.
   Pre-fix the minion subscribes to port 4505, which the masters are
   not listening on, so published jobs never arrive.
2. The minion log contains no ``Connection to master ... lost`` line
   during a 20 s steady-state window.  Pre-fix the ``status.master``
   port-scan fires every scheduler tick.
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


_FLAP_RE = re.compile(r"Connection to master .* lost")


def test_test_ping_and_quiet_on_non_default_publish_port(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_minion_fast_tick,
):
    """
    With masters on an ephemeral publish port and the minion at the
    default ``publish_port: 4505``, the minion must:

    * receive published jobs (``test.ping`` returns True)
    * not log spurious ``Connection to master ... lost`` lines

    Both halves of this assertion fail on pre-fix 3008.x due to
    PR #70725 + PR #70726.
    """
    # Sanity: the fixture must actually be on a non-default publish
    # port, otherwise the test tautologically passes on pre-fix code.
    master_publish_port = int(cluster_master_1.config["publish_port"])
    assert master_publish_port != 4505, (
        f"The scenario requires a non-default publish port on the "
        f"master; got {master_publish_port}.  The regression only "
        f"triggers when master.publish_port != minion.publish_port."
    )

    # First: test.ping must succeed.  Pre-fix the minion subscribes to
    # the wrong port and never receives the published job, so this
    # times out.
    cli = cluster_master_1.salt_cli(timeout=60)
    ret = cli.run("test.ping", minion_tgt=cluster_minion_fast_tick.id)
    assert ret.data is True, (
        f"test.ping failed via master.publish_port={master_publish_port} "
        f"-- the minion is not receiving published jobs.  "
        f"Regression of PR #70725 / #70726 (publish_port mismatch). "
        f"Raw result: {ret!r}"
    )

    # Second: watch the minion log for the next 20 s and confirm no
    # flap.  ``master_alive_interval`` is 3 s on this fixture so this
    # window covers ~6 scheduler ticks; pre-fix every tick flaps.
    log_path = pathlib.Path(cluster_minion_fast_tick.config["log_file"])
    assert log_path.exists(), f"Minion log not written yet at {log_path}"
    start_offset = log_path.stat().st_size

    time.sleep(20)

    with salt.utils.files.fopen(log_path, "r") as fp:
        fp.seek(start_offset)
        tail = fp.read()

    flap_lines = _FLAP_RE.findall(tail)
    assert not flap_lines, (
        f"Minion emitted {len(flap_lines)} ``Connection to master ... lost`` "
        f"line(s) over 20 s on a non-default publish_port cluster.  "
        f"Regression of PR #70726 (status.master port-scan bug).\n\n"
        + "\n".join(flap_lines[:10])
    )
