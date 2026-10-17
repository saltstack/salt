"""
Regression test for saltstack/salt issue #70399 — "Master cluster
(isolated filesystem) behind a load balancer: 'Master did not return a
session key for pillar request'".

With ``cluster_isolated_filesystem: True`` and an L4 load balancer
(HAProxy round-robin) in front of ports 4505/4506, each cluster master
holds a *private* ``cachedir``.  The minion's per-minion session key
lives at ``cachedir/sessions/<minion_id>`` and was generated as random
bytes by :meth:`salt.channel.server.ReqServerChannel.session_key`.
Because the random bytes were per-master, a minion that auth'd against
master A received ``S_A`` in its auth-reply but any subsequent request
round-robined to master B hit "bad load" because B decrypted under its
own ``S_B``.

The fix derives the per-minion session key from ``cluster_aes`` via
HKDF-SHA256 when ``cluster_isolated_filesystem`` is set.  Every peer
already agrees on ``cluster_aes`` (distributed via
``cluster/peer/join-reply`` and rotated cluster-wide by
``rotate_cluster_aes_key``), so every peer derives an identical session
key for the same minion with no replication.
"""

import ctypes
import logging
import multiprocessing
import pathlib

import pytest

import salt.channel.server
import salt.master

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


def _install_cluster_aes_in_test_process(aes_bytes):
    """
    Populate ``SMaster.secrets["cluster_aes"]`` in the pytest process so
    an in-process :class:`PoolRoutingChannel` can call its ``session_key``
    code path.  Running master daemons populate this via
    ``populate_secrets`` in their own subprocess; the pytest process does
    not, so we mirror the setup here with the aes bytes the cluster
    actually agreed on.
    """
    salt.master.SMaster.secrets["cluster_aes"] = {
        "secret": multiprocessing.Array(ctypes.c_char, aes_bytes),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": lambda: aes_bytes,
    }


def test_isolated_cluster_session_keys_agree_across_masters(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
):
    """
    For an isolated-FS cluster, ``session_key(minion_id)`` on every peer
    master must return the *same* bytes.  Otherwise a minion whose auth
    was routed to master A will fail every subsequent request routed by
    an L4 balancer to master B — the exact "bad load" / "Master did not
    return a session key for pillar request" failure in issue #70399.

    Pre-fix: each master generates random bytes stored at its private
    ``cachedir/sessions/<minion>`` → three distinct keys → fails.
    Post-fix: each master derives from the shared ``cluster_aes`` via
    HKDF-SHA256 → identical keys → passes.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    minion_id = cluster_minion_1_isolated.id

    aes_bytes_per_master = {
        m.config["interface"]: (
            pathlib.Path(m.config["cluster_pki_dir"]) / ".aes"
        ).read_bytes()
        for m in masters
    }
    assert len(set(aes_bytes_per_master.values())) == 1, (
        f"cluster_aes diverges across the cluster — bug beyond #70399: "
        f"{ {addr: len(v) for addr, v in aes_bytes_per_master.items()} }"
    )

    _install_cluster_aes_in_test_process(next(iter(aes_bytes_per_master.values())))

    keys = {}
    channels = []
    try:
        for master in masters:
            channel = salt.channel.server.ReqServerChannel.factory(dict(master.config))
            channels.append(channel)
            keys[master.config["interface"]] = channel.session_key(minion_id)
    finally:
        for channel in channels:
            try:
                channel.close()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Error closing channel")

    unique = set(keys.values())
    assert len(unique) == 1, (
        f"session_key({minion_id!r}) returns different bytes on each "
        f"cluster master (issue #70399). Per-master key byte-lengths: "
        f"{ {addr: len(v) for addr, v in keys.items()} }. "
        f"Three distinct values means every peer handed the minion a "
        f"different session key — a round-robin L4 balancer would hit "
        f"'bad load' on the first pillar request routed to a non-auth "
        f"peer."
    )
