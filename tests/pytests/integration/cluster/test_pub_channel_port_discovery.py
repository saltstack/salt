"""
Integration regression for PR #70725 / issue #70724.

``AsyncPubChannel.connect()`` picks between the minion-side
``publish_port`` opt and the master-reported value with:

.. code-block:: python

    if int(self.opts.get("publish_port", 4506)) != 4506:
        publish_port = self.opts.get("publish_port")
    else:
        publish_port = self.auth.creds["publish_port"]

The fallback default ``4506`` is the *ret* port; the publish-port default
is ``4505``.  With the wrong sentinel, a minion with its default
``publish_port: 4505`` satisfies ``int(4505) != 4506`` and always goes
into the "operator explicitly overrode" branch -- so the master-reported
publish port from ``auth.creds["publish_port"]`` is ignored and the pub
channel connects to port 4505 regardless of where the master is actually
listening.

PR #70725 uses ``4505`` as the sentinel so the default-vs-override
detection matches the real default; a minion that didn't set
``publish_port`` now takes the master-reported value as intended.

This test asserts the connect-time log line emitted by
``salt.transport.zeromq.PublishClient.connect`` names the master's
*actual* publish port, not 4505:

    [DEBUG] Connecting the Minion to the Master publish port,
            using the URI: tcp://<ip>:<port>

Pre-fix the ``<port>`` captured on this line is 4505 for any minion
without an explicit ``publish_port`` override; post-fix it is the
master's ephemeral port.
"""

import pathlib
import re
import time

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout(240),
]


# Captures the port on the zeromq pub-client connect log line.  The
# ``\S*?`` keeps the match tolerant to IPv6 brackets etc.
_PUB_URI_RE = re.compile(
    r"Connecting the Minion to the Master publish port,\s*using the URI:\s*"
    r"tcp://\S*?:(?P<port>\d+)"
)


def test_pub_channel_uses_master_reported_publish_port(
    cluster_master_1, cluster_master_2, cluster_minion_1
):
    """
    With the master on an ephemeral ``publish_port`` and the minion at
    the Salt default (4505, not overridden), the pub channel must connect
    to the master's actual port -- not 4505.

    Pre-fix: ``AsyncPubChannel.connect()`` chooses 4505 and the zeromq
    publish-client log line names ``tcp://<ip>:4505``.  The channel
    silently fails to receive published jobs because the master is not
    listening there.

    Post-fix: the log line names the master's ephemeral port and the
    channel receives publishes normally.

    ``cluster_master_2`` is pulled in so the 3-peer Raft config reaches
    quorum (2 of 3) and the minion finishes its pillar fetch without
    being blocked on ``cluster_retry``.
    """
    # Sanity check -- the regression only reproduces when the master
    # publish_port differs from the minion default.
    master_publish_port = int(cluster_master_1.config["publish_port"])
    assert master_publish_port != 4505, (
        f"Fixture requires a non-default master publish_port to be "
        f"meaningful; got {master_publish_port}."
    )

    # Belt-and-braces: pub channel is zmq transport-specific; TCP has its
    # own connect path and doesn't take the AsyncPubChannel.connect()
    # branch.
    if cluster_master_1.config.get("transport") == "tcp":
        pytest.skip("TCP transport uses a different pub-connect code path")

    # Minion must be at the Salt default ``publish_port`` -- that's the
    # exact shape (common-case production config) the bug hits.  If a
    # future fixture edit sets ``publish_port`` to the master's port
    # the bug no longer reproduces and the test tautologically passes.
    # The minion opts dict uses an ``OptsDict`` that only exposes keys
    # the config system knows about; ``publish_port`` lives in the
    # DEFAULT_MINION_OPTS fallback rather than an explicit override, so
    # ``.get()`` with a sentinel is the safest probe here.
    minion_publish_port = cluster_minion_1.config.get("publish_port", 4505)
    assert int(minion_publish_port) == 4505, (
        f"cluster_minion_1 must leave publish_port at the Salt default "
        f"(4505) for this regression to reproduce; got "
        f"{minion_publish_port}.  Fixture changed?"
    )

    log_path = pathlib.Path(cluster_minion_1.config["log_file"])
    # Give the minion a moment to finish the auth -> pub-connect
    # sequence; the ``started()`` context manager returns on 'Minion is
    # ready' which is after this, but the log may still be buffering.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if log_path.exists():
            with salt.utils.files.fopen(log_path, "r") as fp:
                log_text = fp.read()
            if _PUB_URI_RE.search(log_text):
                break
        time.sleep(0.5)
    else:
        pytest.fail(
            f"Minion did not log the pub-connect URI within 30 s "
            f"(log={log_path!r}).  Transport log line regressed?"
        )

    matches = _PUB_URI_RE.findall(log_text)
    assert matches, (
        "Expected at least one 'Connecting the Minion to the Master "
        "publish port' DEBUG line in the minion log"
    )

    # The *first* connect is what the fix controls -- any later
    # reconnects after cluster events may use a different code path
    # (``self._reconnected`` short-circuits).  Grab the first match.
    first_port = int(matches[0])
    assert first_port == master_publish_port, (
        f"Minion's pub channel connected to port {first_port}, but the "
        f"master is publishing on {master_publish_port}.  Regression of "
        f"PR #70725: ``AsyncPubChannel.connect()`` compared the minion "
        f"opt to the wrong sentinel (4506 instead of 4505), so a minion "
        f"with the default publish_port ignores the master-reported "
        f"value and subscribes to the wrong port."
    )
