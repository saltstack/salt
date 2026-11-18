"""
Regression test for the founder-side state-machine commit path.

``_start_raft_as_founding_voter`` must call ``mark_committed`` for the
founder's locally-generated ``cluster_aes`` + ``cluster.pem`` so that:

1. On process restart the sentinel + on-disk bytes match and the state
   machine stays in COMMITTED (rather than reverting to BOOTSTRAP and
   accepting a stranger's key arriving via join-reply).
2. Later join-replies that echo the founder's keys back do not
   re-trigger any install path -- the state machine fast-pathing on
   ``matches committed; no-op``.

Without this commit, the founder master's cluster_aes + cluster.pem
are never marked COMMITTED (``mark_committed`` only fires from the
receiver install path, and the founder never receives its own keys).
See ``agents/reports/`` for the diagnosis of PR #70831's remaining
Arm64 integration-3 failure.
"""

import pathlib

import pytest

import salt.channel._cluster_key_state as sm_mod
from salt.channel.server import MasterPubServerChannel
from tests.support.mock import MagicMock, patch


@pytest.fixture
def opts(tmp_path):
    pki = tmp_path / "cluster_pki"
    pki.mkdir()
    return {
        "id": "127.0.0.1_master",
        "cluster_id": "test_cluster",
        "cluster_pki_dir": str(pki),
    }


def _make_channel(opts):
    ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
    ch.opts = opts
    ch._raft_service = None
    ch._cluster_key_sm = None
    ch.io_loop = MagicMock()
    ch.pushers = []
    return ch


def _seed_keys(opts, aes=b"founder-aes-v1", pem=b"founder-pem-v1"):
    pki = pathlib.Path(opts["cluster_pki_dir"])
    (pki / ".aes").write_bytes(aes)
    (pki / "cluster.pem").write_bytes(pem)
    return aes, pem


def test_founding_voter_commits_own_cluster_keys_to_state_machine(opts):
    """
    After ``_start_raft_as_founding_voter`` completes, the state
    machine must be COMMITTED for both ``cluster_aes`` and
    ``cluster_pem`` with the on-disk bytes' fingerprints.
    """
    aes, pem = _seed_keys(opts)
    ch = _make_channel(opts)

    with patch.object(ch, "_mark_joined_cluster"), patch(
        "salt.cluster.consensus.service.RaftService"
    ), patch(
        "salt.cluster.consensus.service.build_peer_pushers", return_value=[]
    ), patch(
        "salt.utils.asynchronous.aioloop", return_value=MagicMock()
    ):
        ch._start_raft_as_founding_voter()

    sm = ch._cluster_key_state_machine()
    assert sm is not None
    assert sm.state_of("cluster_aes") == sm_mod.STATE_COMMITTED
    assert sm.state_of("cluster_pem") == sm_mod.STATE_COMMITTED
    assert sm.fingerprint_of("cluster_aes") == sm_mod.fingerprint_bytes(aes)
    assert sm.fingerprint_of("cluster_pem") == sm_mod.fingerprint_bytes(pem)


def test_founding_voter_writes_sentinels_on_disk(opts):
    """
    ``mark_committed`` persists the sentinel file; after founder
    election the sentinel on disk must match the fingerprint of the
    on-disk key bytes.  Without this, the next process restart cannot
    verify the COMMITTED state and reverts to BOOTSTRAP.
    """
    aes, pem = _seed_keys(opts)
    ch = _make_channel(opts)

    with patch.object(ch, "_mark_joined_cluster"), patch(
        "salt.cluster.consensus.service.RaftService"
    ), patch(
        "salt.cluster.consensus.service.build_peer_pushers", return_value=[]
    ), patch(
        "salt.utils.asynchronous.aioloop", return_value=MagicMock()
    ):
        ch._start_raft_as_founding_voter()

    aes_sentinel = sm_mod.cluster_key_sentinel_path(
        opts["cluster_pki_dir"], "cluster_aes"
    )
    pem_sentinel = sm_mod.cluster_key_sentinel_path(
        opts["cluster_pki_dir"], "cluster_pem"
    )
    assert pathlib.Path(aes_sentinel).is_file()
    assert pathlib.Path(pem_sentinel).is_file()
    assert sm_mod.read_sentinel_fingerprint(aes_sentinel) == sm_mod.fingerprint_bytes(
        aes
    )
    assert sm_mod.read_sentinel_fingerprint(pem_sentinel) == sm_mod.fingerprint_bytes(
        pem
    )


def test_founding_voter_without_cluster_keys_on_disk_is_noop(opts):
    """
    If the founder somehow reaches the election path without having
    written its keys yet (edge case / test harness quirk), the commit
    call is a no-op rather than raising.  The state machine stays in
    BOOTSTRAP and the receiver install path remains available.
    """
    ch = _make_channel(opts)  # no _seed_keys()

    with patch.object(ch, "_mark_joined_cluster"), patch(
        "salt.cluster.consensus.service.RaftService"
    ), patch(
        "salt.cluster.consensus.service.build_peer_pushers", return_value=[]
    ), patch(
        "salt.utils.asynchronous.aioloop", return_value=MagicMock()
    ):
        ch._start_raft_as_founding_voter()

    sm = ch._cluster_key_state_machine()
    assert sm is not None
    assert sm.state_of("cluster_aes") == sm_mod.STATE_BOOTSTRAP
    assert sm.state_of("cluster_pem") == sm_mod.STATE_BOOTSTRAP
