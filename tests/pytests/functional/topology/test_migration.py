"""
Functional tests for :mod:`salt.topology.migration`.

Exercises the real :class:`salt.utils.mmap_cache.MmapCache` backing
the registry and a real
:class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`;
no mocks of either.  The Raft ``Node`` is never spun up --- the SM's
``apply`` is a plain Python callable, and ``promote_solo_to_clustered``
takes any object exposing ``propose(cmd)``.  For these tests the
``raft_service`` is a thin shim that routes ``propose`` straight into
``sm.apply`` so a proposal commits synchronously.  This keeps the
test boundary at the migration contract (``needs_migration`` /
``promote_solo_to_clustered``) without pulling in a 3008.x cluster.

Covered
-------
* ``needs_migration`` is True when the registry holds peers but the
  SM has not applied any (solo master wrote directly before flipping
  to clustered).
* ``needs_migration`` is True when the registry holds the identity
  pub but the SM is pre-bootstrap.
* ``needs_migration`` is False on a fresh clustered install (both
  the registry and the SM are empty).
* ``needs_migration`` is False on steady-state (registry and SM
  applied set agree).
* ``needs_migration`` is False on a solo master
  (``cluster_peers`` empty): migration is a clustered-mode concern.
* ``promote_solo_to_clustered`` on first invocation proposes
  identity + every pending peer, in that order, with the identity
  entry first.
* ``promote_solo_to_clustered`` on crash-resume proposes only the
  un-proposed subset (idempotent across replay).
* After ``promote_solo_to_clustered`` completes,
  ``needs_migration`` returns False.
"""

import logging

import pytest

import salt.topology.migration as migration
import salt.topology.registry as registry
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_windows,  # fork(2) + 0o400 permissions assumptions
]


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


FAKE_PUB_IDENTITY = b"-----BEGIN PUBLIC KEY-----\nIDENTITY\n-----END PUBLIC KEY-----\n"
FAKE_PRIV_IDENTITY = (
    b"-----BEGIN RSA PRIVATE KEY-----\nidentity\n-----END RSA PRIVATE KEY-----\n"
)


def _opts(pki_root, cluster_peers=("peer-1",)):
    """
    Build the minimal opts dict the migration module + SM read.

    ``cluster_peers`` toggles clustered vs solo mode: an empty tuple
    is the solo-master shape.
    """
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "keysize": 2048,
        "hash_type": "sha256",
        "cluster_peers": list(cluster_peers),
    }


@pytest.fixture
def opts(tmp_path):
    return _opts(tmp_path)


@pytest.fixture
def opts_solo(tmp_path):
    """Same shape as :func:`opts` but ``cluster_peers`` is empty."""
    return _opts(tmp_path, cluster_peers=())


@pytest.fixture
def sm(opts):
    """
    Real :class:`TopologyStateMachine` wired to the real registry.

    Closed on teardown so each test opens its own writer handle
    against its own tmp pki_dir with no shared flock state.
    """
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        try:
            machine.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


class FakeRaftService:
    """
    Minimal :class:`raft_service` stand-in for the migration tests.

    Exposes a ``propose(cmd)`` that commits synchronously by
    dispatching into the backing :class:`TopologyStateMachine`'s
    ``apply``.  Records every proposed cmd in :attr:`proposed`
    for order/content assertions.

    The real Raft service will enforce leader-only + wait-for-commit
    semantics; those are out of scope for migration logic and are
    covered under the Raft service's own tests.
    """

    def __init__(self, state_machine):
        self._sm = state_machine
        self.proposed = []

    def propose(self, cmd):
        self.proposed.append(cmd)
        self._sm.apply(cmd, client_id="migration", sequence_num=len(self.proposed))


def _write_identity_pem_to_disk(opts_):
    """
    Simulate what a solo master's publish daemon has already done:
    stash the identity private key at the well-known on-disk path
    so :func:`promote_solo_to_clustered` can read it back.
    """
    import os

    import salt.utils.files

    master_dir = os.path.join(opts_["pki_dir"], "master")
    priv_path = os.path.join(master_dir, "master_identity.pem")
    pub_path = os.path.join(master_dir, "master_identity.pub")
    with salt.utils.files.fopen(priv_path, "wb") as fh:
        fh.write(FAKE_PRIV_IDENTITY)
    os.chmod(priv_path, 0o400)
    with salt.utils.files.fopen(pub_path, "wb") as fh:
        fh.write(FAKE_PUB_IDENTITY)
    os.chmod(pub_path, 0o444)


def _seed_solo_registry(opts_, peers):
    """
    Simulate the solo-master write path: open the registry writer,
    stash identity_pub + each peer directly (bypassing Raft), close.

    ``peers`` is an iterable of ``(cluster_id, pub_pem)`` tuples.
    Peers get a stable ``attached_at`` so sort assertions are
    deterministic.
    """
    writer = registry.open_writer(opts_)
    try:
        registry.set_identity_pub(writer, FAKE_PUB_IDENTITY)
        for idx, (cluster_id, pub) in enumerate(peers):
            registry.set_peer(
                writer,
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "public_key": pub,
                    "endpoints": (f"127.0.0.1:450{idx}",),
                    "attached_at": 1_700_000_000.0 + idx,
                },
            )
    finally:
        writer.close()


def _seed_identity_only(opts_):
    """
    Variant of :func:`_seed_solo_registry` that writes only the
    identity_pub --- no peers.  Models a solo master that bootstrapped
    its identity but never accepted any peers.
    """
    writer = registry.open_writer(opts_)
    try:
        registry.set_identity_pub(writer, FAKE_PUB_IDENTITY)
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# needs_migration
# ---------------------------------------------------------------------------


def test_needs_migration_true_when_registry_has_peers_but_sm_empty(opts, sm):
    """
    Solo master wrote peers directly to the registry MmapCache.
    A fresh clustered boot reads the registry, sees peers, but the
    SM has never applied anything via Raft --- migration must run.
    """
    # pre-sm teardown would race the writer: close the SM's writer
    # before the test writes solo-direct, then rely on the SM's
    # reader path only via ``needs_migration``.
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    _seed_solo_registry(
        opts,
        [
            ("east", b"-----BEGIN PUBLIC KEY-----\nEAST\n-----END PUBLIC KEY-----\n"),
            ("west", b"-----BEGIN PUBLIC KEY-----\nWEST\n-----END PUBLIC KEY-----\n"),
        ],
    )
    assert migration.needs_migration(opts) is True


def test_needs_migration_true_when_identity_set_but_pre_bootstrap(opts, sm):
    """
    Registry has an identity_pub but the SM has never applied a
    ``MASTER_IDENTITY_KEY`` entry (crash immediately after solo
    identity bootstrap, before any clustered boot).  Migration
    must run to propose the identity.
    """
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    _seed_identity_only(opts)
    assert migration.needs_migration(opts) is True


def test_needs_migration_false_on_fresh_clustered_install(opts, sm):
    """
    Both the registry and the SM are empty: nothing to migrate.
    """
    # SM constructor already materialised the mmap; nothing was
    # written through either path.  Close SM to release the writer
    # lock before needs_migration opens a reader.
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    assert migration.needs_migration(opts) is False


def test_needs_migration_false_on_steady_state(opts, sm):
    """
    Registry entries were written via the SM's apply path (as they
    would be in steady-state clustered operation): the SM's
    applied set and the registry contents agree.  Nothing to
    migrate.
    """
    svc = FakeRaftService(sm)
    svc.propose(
        {
            "type": LogEntryType.MASTER_IDENTITY_KEY,
            "public_key": FAKE_PUB_IDENTITY,
            "private_key": FAKE_PRIV_IDENTITY,
        }
    )
    for cluster_id in ("alpha", "beta"):
        svc.propose(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": cluster_id,
                "public_key": (
                    b"-----BEGIN PUBLIC KEY-----\n"
                    + cluster_id.upper().encode("ascii")
                    + b"\n-----END PUBLIC KEY-----\n"
                ),
                "endpoints": ("127.0.0.1:4506",),
                "attached_at": 1_700_000_000.0,
            }
        )
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    assert migration.needs_migration(opts) is False


def test_needs_migration_false_on_solo_master(opts_solo, tmp_path):
    """
    ``cluster_peers`` is empty: migration is a clustered-mode
    concern and must short-circuit to False, even if the registry
    happens to hold peers (e.g. test fixture leftovers).  A solo
    master is never a migration source.
    """
    _seed_solo_registry(
        opts_solo,
        [
            ("east", b"-----BEGIN PUBLIC KEY-----\nEAST\n-----END PUBLIC KEY-----\n"),
        ],
    )
    assert migration.needs_migration(opts_solo) is False


# ---------------------------------------------------------------------------
# promote_solo_to_clustered
# ---------------------------------------------------------------------------


def test_promote_first_invocation_proposes_identity_then_peers(opts, sm):
    """
    Fresh promote on a registry with identity + two peers:
    * Proposes MASTER_IDENTITY_KEY first.
    * Proposes MASTER_PEER_ATTACH for every peer, in sorted
      ``cluster_id`` order.
    * No duplicates.
    """
    # Simulate solo pre-state: identity on disk (so the private half
    # can be forwarded through Raft) + identity_pub + peers in the
    # registry.
    _write_identity_pem_to_disk(opts)
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    _seed_solo_registry(
        opts,
        [
            ("zeta", b"-----BEGIN PUBLIC KEY-----\nZ\n-----END PUBLIC KEY-----\n"),
            ("alpha", b"-----BEGIN PUBLIC KEY-----\nA\n-----END PUBLIC KEY-----\n"),
            ("mike", b"-----BEGIN PUBLIC KEY-----\nM\n-----END PUBLIC KEY-----\n"),
        ],
    )
    # Build a fresh SM against the now-populated registry: this is
    # the shape a clustered-boot process would see after the SM's
    # own ``__init__`` opens the mmap.
    fresh = TopologyStateMachine(opts)
    try:
        svc = FakeRaftService(fresh)
        migration.promote_solo_to_clustered(opts, svc)
    finally:
        try:
            fresh.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    types_seen = [cmd["type"] for cmd in svc.proposed]
    assert types_seen[0] == LogEntryType.MASTER_IDENTITY_KEY
    attach_cmds = [
        cmd for cmd in svc.proposed if cmd["type"] == LogEntryType.MASTER_PEER_ATTACH
    ]
    assert [c["cluster_id"] for c in attach_cmds] == ["alpha", "mike", "zeta"]
    assert len(svc.proposed) == 4  # identity + 3 peers
    identity_cmd = svc.proposed[0]
    assert identity_cmd["public_key"] == FAKE_PUB_IDENTITY
    assert identity_cmd.get("private_key") == FAKE_PRIV_IDENTITY


def test_promote_crash_resume_proposes_only_pending_subset(opts, sm):
    """
    Simulate the crash-mid-migration path.  First promote proposes
    identity + ``alpha`` and then the process ``crashes'' before
    the second peer is proposed.  The second promote on resume
    MUST propose only ``beta`` --- identity + ``alpha`` are
    already applied via the SM's prior session.
    """
    _write_identity_pem_to_disk(opts)
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    _seed_solo_registry(
        opts,
        [
            ("alpha", b"-----BEGIN PUBLIC KEY-----\nA\n-----END PUBLIC KEY-----\n"),
            ("beta", b"-----BEGIN PUBLIC KEY-----\nB\n-----END PUBLIC KEY-----\n"),
        ],
    )
    # First promote: force an "incomplete" run by proposing only
    # identity + alpha through a controlled service.
    partial_sm = TopologyStateMachine(opts)
    try:
        partial_svc = FakeRaftService(partial_sm)
        # Manually drive the two commits a complete first-run would
        # have produced (identity + alpha), simulating the crash
        # before beta.
        partial_svc.propose(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_IDENTITY,
                "private_key": FAKE_PRIV_IDENTITY,
            }
        )
        partial_svc.propose(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "alpha",
                "public_key": (
                    b"-----BEGIN PUBLIC KEY-----\nA\n-----END PUBLIC KEY-----\n"
                ),
                "endpoints": ("127.0.0.1:4500",),
                "attached_at": 1_700_000_000.0,
            }
        )
    finally:
        try:
            partial_sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    # Second promote (resume) --- a fresh SM opens the registry and
    # finds identity + alpha already in the Raft-applied sentinel;
    # only beta should get proposed.
    resumed_sm = TopologyStateMachine(opts)
    try:
        resumed_svc = FakeRaftService(resumed_sm)
        migration.promote_solo_to_clustered(opts, resumed_svc)
    finally:
        try:
            resumed_sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    assert len(resumed_svc.proposed) == 1, (
        f"resume should propose only the un-applied subset; "
        f"saw {[c['type'] for c in resumed_svc.proposed]}"
    )
    only = resumed_svc.proposed[0]
    assert only["type"] == LogEntryType.MASTER_PEER_ATTACH
    assert only["cluster_id"] == "beta"


def test_needs_migration_false_after_promote(opts, sm):
    """
    After a complete ``promote_solo_to_clustered`` run,
    ``needs_migration`` reports False --- the applied set matches
    the registry contents and the bootstrap flag is set.
    """
    _write_identity_pem_to_disk(opts)
    try:
        sm.registry.close()
    except Exception:  # pylint: disable=broad-except
        pass
    _seed_solo_registry(
        opts,
        [
            ("east", b"-----BEGIN PUBLIC KEY-----\nE\n-----END PUBLIC KEY-----\n"),
            ("west", b"-----BEGIN PUBLIC KEY-----\nW\n-----END PUBLIC KEY-----\n"),
        ],
    )
    assert migration.needs_migration(opts) is True
    fresh = TopologyStateMachine(opts)
    try:
        svc = FakeRaftService(fresh)
        migration.promote_solo_to_clustered(opts, svc)
    finally:
        try:
            fresh.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    assert migration.needs_migration(opts) is False
