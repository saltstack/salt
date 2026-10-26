"""
Functional tests for the ``--master`` scope of salt-key.

Exercises the new :class:`salt.key.Key` methods added for the
master-topology feature:

* :meth:`Key.list_master` returns the accepted/pending/rejected/denied
  cluster-id buckets scraped from ``pki_dir/masters*/``.
* :meth:`Key.accept_master` on solo masters renames
  ``masters_pre/<id>.pub`` to ``masters/<id>.pub`` and fires a
  ``salt/key`` event the publish daemon's PKI watcher consumes.
* :meth:`Key.accept_master` on clustered masters proposes
  ``MASTER_PEER_ATTACH`` into Raft and does **not** touch the file;
  the state machine's apply handler performs the rename.
* :meth:`Key.reject_master` moves the pending key to
  ``masters_rejected/``.
* :meth:`Key.delete_master` on clustered masters proposes
  ``MASTER_PEER_DETACH`` and does **not** touch the file; solo masters
  delete the file directly.
* :meth:`Key.finger_master` returns the stored key fingerprint.
* **Crash-resume safety**: if the propose succeeds but the apply
  crashes before the rename, the next apply (replay) is idempotent and
  re-does the rename.
* **No partial state**: a crash between propose and commit must not
  leave the key file in ``masters/`` without a Raft commit; the
  file-move is owned exclusively by the apply handler.

The tests exercise the real :class:`salt.key.Key`, the real
:class:`TopologyStateMachine` (plain Python callable; no Raft Node
needed), and the real :class:`salt.utils.mmap_cache.MmapCache` behind
the registry.  Only the Raft service is a shim that routes
``propose_peer_attach`` / ``propose_peer_detach`` straight through to
``sm.apply`` so proposals commit synchronously.  The ``event`` bus on
the Key is replaced with a lightweight recorder so no AsyncEventPublisher
needs to be stood up.
"""

import logging
import os

import pytest

import salt.key
import salt.topology.registry as registry
import salt.utils.crypt
import salt.utils.files
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


FAKE_PUB_EAST = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"east-cluster-identity-key\n"
    b"-----END PUBLIC KEY-----\n"
)
FAKE_PUB_WEST = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"west-cluster-identity-key\n"
    b"-----END PUBLIC KEY-----\n"
)


def _write_pub(path, body):
    with salt.utils.files.fopen(str(path), "wb") as fh:
        fh.write(body)
    os.chmod(str(path), 0o644)


class _RecordingEvent:
    """
    Stand-in for the Key's ``@cached_property event`` so tests can
    inspect what the propose-first paths fire without wiring up a
    real ``AsyncEventPublisher`` (which wants a running salt-master).

    Mirrors the attribute surface the real
    :class:`salt.utils.event.MasterEvent` exposes to the Key class:
    only ``fire_event`` and ``destroy``.
    """

    def __init__(self):
        self.fired = []  # list of (data, tag) tuples

    def fire_event(self, data, tag):
        self.fired.append((data, tag))

    def destroy(self):
        pass


def _build_opts(pki_root, sock_dir, raft_service=None, cluster_id=None):
    """
    Build the minimal opts dict ``salt.key.Key`` reads.

    Mirrors the shape produced by :func:`salt.config.master_config`
    but trimmed to what the Key class touches.  ``raft_service``,
    when provided, is the hook the propose-first Key methods use
    to talk to Raft; solo masters leave it ``None``.
    """
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)
    cachedir = sock_dir / "cache"
    cachedir.mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_root),
        "cachedir": str(cachedir),
        "sock_dir": str(sock_dir),
        "transport": "zeromq",
        "keys.cache_driver": "localfs_key",
        "key_cache": "",
        "preserve_minions": False,
        "rotate_aes_key": False,
        "hash_type": "sha256",
        "keysize": 2048,
        "__role": "master",
        "id": "test-master",
        "user": "root",
        "signing_key_pass": None,
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
    }
    if raft_service is not None:
        opts["raft_service"] = raft_service
    if cluster_id is not None:
        opts["cluster_id"] = cluster_id
    return opts


class FakeRaftService:
    """
    Shim raft-service that commits proposes synchronously by
    dispatching into the backing
    :class:`TopologyStateMachine`.

    Records every ``propose_peer_attach`` / ``propose_peer_detach``
    call so tests can assert propose-first ordering.  A ``crash_on``
    attribute lets a test force the state machine's apply to raise
    *after* propose records the call, mirroring the "proposed but
    apply crashed" window.
    """

    def __init__(self, state_machine):
        self._sm = state_machine
        self.proposed = []  # list of (kind, cmd) tuples
        self.crash_on = None  # entry_type value that should raise on apply

    def _apply(self, cmd):
        entry_type = cmd.get("type")
        if self.crash_on == entry_type:
            raise RuntimeError(f"simulated apply crash for {entry_type!r}")
        self._sm.apply(cmd, client_id="salt-key", sequence_num=len(self.proposed))

    def propose_peer_attach(
        self, cluster_id, public_key, endpoints=(), attached_at=0.0, **kwargs
    ):
        cmd = {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": cluster_id,
            "public_key": public_key,
            "endpoints": tuple(endpoints),
            "attached_at": float(attached_at),
        }
        cmd.update(kwargs)
        self.proposed.append(("attach", cmd))
        self._apply(cmd)

    def propose_peer_detach(self, cluster_id, reason="revoked", **kwargs):
        cmd = {
            "type": LogEntryType.MASTER_PEER_DETACH,
            "cluster_id": cluster_id,
            "reason": reason,
        }
        cmd.update(kwargs)
        self.proposed.append(("detach", cmd))
        self._apply(cmd)


@pytest.fixture
def pki_root(tmp_path):
    root = tmp_path / "pki"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def sock_dir(tmp_path):
    sock = tmp_path / "sock"
    sock.mkdir(parents=True, exist_ok=True)
    return sock


@pytest.fixture
def solo_opts(pki_root, sock_dir):
    """Opts for a solo (unclustered) master -- no raft_service."""
    return _build_opts(pki_root, sock_dir)


@pytest.fixture
def sm(pki_root, sock_dir):
    """
    Real :class:`TopologyStateMachine` wired to the real registry.

    The SM lives in the same ``pki_dir`` as the Key under test; its
    apply handlers do the file-move from ``masters_pre/`` to
    ``masters/``.
    """
    opts = _build_opts(pki_root, sock_dir)
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        try:
            machine.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


@pytest.fixture
def raft_service(sm):
    return FakeRaftService(sm)


@pytest.fixture
def clustered_opts(pki_root, sock_dir, raft_service):
    """Opts for a clustered master; carries a raft_service shim."""
    return _build_opts(pki_root, sock_dir, raft_service=raft_service, cluster_id="east")


def _make_key(opts):
    """
    Build a ``Key`` with its event bus replaced by a recorder.

    ``Key.event`` is a :func:`salt.utils.decorators.cached_property`;
    writing into ``__dict__`` wins over the descriptor on subsequent
    reads.
    """
    key = salt.key.Key(opts)
    key.__dict__["event"] = _RecordingEvent()
    return key


# ---------------------------------------------------------------------------
# list_master
# ---------------------------------------------------------------------------


def test_list_master_scrapes_masters_dirs(solo_opts, pki_root):
    """
    ``Key.list_master`` returns the four cluster-namespace buckets
    populated from ``pki_dir/masters*/``.
    """
    _write_pub(pki_root / "masters" / "accepted-one.pub", FAKE_PUB_EAST)
    _write_pub(pki_root / "masters_pre" / "pending-one.pub", FAKE_PUB_WEST)
    _write_pub(pki_root / "masters_pre" / "pending-two.pub", FAKE_PUB_WEST)
    _write_pub(pki_root / "masters_rejected" / "rej-one.pub", FAKE_PUB_WEST)
    _write_pub(pki_root / "masters_denied" / "den-one.pub", FAKE_PUB_WEST)

    with _make_key(solo_opts) as key:
        ret = key.list_master()

    assert ret == {
        "accepted": ["accepted-one"],
        "pending": ["pending-one", "pending-two"],
        "rejected": ["rej-one"],
        "denied": ["den-one"],
    }


def test_list_master_empty_when_dirs_absent(solo_opts):
    """
    Empty ``masters*/`` directories return the four empty buckets.
    """
    with _make_key(solo_opts) as key:
        ret = key.list_master()
    assert ret == {
        "accepted": [],
        "pending": [],
        "rejected": [],
        "denied": [],
    }


# ---------------------------------------------------------------------------
# accept_master -- solo
# ---------------------------------------------------------------------------


def test_accept_master_solo_moves_file_and_fires_event(solo_opts, pki_root):
    """
    On a solo master, ``accept_master`` renames
    ``masters_pre/<id>.pub`` to ``masters/<id>.pub`` and fires a
    ``salt/key`` event the publish daemon's PKI watcher consumes.
    """
    pending = pki_root / "masters_pre" / "east.pub"
    _write_pub(pending, FAKE_PUB_EAST)

    with _make_key(solo_opts) as key:
        ret = key.accept_master("east")
        fired = list(key.event.fired)

    accepted = pki_root / "masters" / "east.pub"
    assert accepted.exists(), "accepted key file should be moved to masters/"
    assert not pending.exists(), "pending key file should be gone"
    assert accepted.read_bytes() == FAKE_PUB_EAST

    assert ret == {"accepted": ["east"]}

    # Event was fired for the PKI watcher.
    assert fired, "accept_master should fire a key event"
    data, tag = fired[-1]
    assert data.get("act") == "accept"
    assert data.get("id") == "east"
    assert tag.startswith("salt/key")


def test_accept_master_solo_rejects_invalid_cluster_id(solo_opts):
    """
    ``accept_master`` refuses reserved/invalid cluster_ids before
    touching anything on disk.
    """
    with _make_key(solo_opts) as key:
        with pytest.raises(ValueError):
            key.accept_master("__identity_pub__")
        with pytest.raises(ValueError):
            key.accept_master("UPPER")  # fails CLUSTER_ID_RE


def test_accept_master_solo_missing_pending_is_noop(solo_opts):
    """
    Accepting a cluster_id with no pending key returns an empty
    result rather than raising.
    """
    with _make_key(solo_opts) as key:
        ret = key.accept_master("east")
    assert ret == {"accepted": []}


# ---------------------------------------------------------------------------
# accept_master -- clustered: propose-first
# ---------------------------------------------------------------------------


def test_accept_master_clustered_proposes_before_touching_file(
    clustered_opts, raft_service, pki_root
):
    """
    On a clustered master, ``accept_master`` proposes
    ``MASTER_PEER_ATTACH`` carrying the pub bytes.  salt-key must
    NOT rename the file first --- a crash between the rename and
    the propose would leave the file in ``masters/`` without a
    Raft commit.  The apply handler (shim here) does the rename.
    """
    pending = pki_root / "masters_pre" / "east.pub"
    _write_pub(pending, FAKE_PUB_EAST)

    with _make_key(clustered_opts) as key:
        key.accept_master("east")

    # Exactly one propose, of the attach type, carrying the pub bytes.
    assert len(raft_service.proposed) == 1
    kind, cmd = raft_service.proposed[0]
    assert kind == "attach"
    assert cmd["type"] == LogEntryType.MASTER_PEER_ATTACH
    assert cmd["cluster_id"] == "east"
    assert cmd["public_key"] == FAKE_PUB_EAST

    # After commit, the apply handler moved the file.
    accepted = pki_root / "masters" / "east.pub"
    assert accepted.exists()
    assert not pending.exists()


def test_accept_master_clustered_crash_before_apply_leaves_no_partial_state(
    clustered_opts, raft_service, pki_root
):
    """
    If the propose fires but the apply crashes before the rename,
    the file must still live in ``masters_pre/`` (never
    ``masters/``).  Simulates "committed to Raft but local apply
    exploded".
    """
    pending = pki_root / "masters_pre" / "east.pub"
    _write_pub(pending, FAKE_PUB_EAST)

    raft_service.crash_on = LogEntryType.MASTER_PEER_ATTACH

    with _make_key(clustered_opts) as key:
        with pytest.raises(RuntimeError, match="simulated apply crash"):
            key.accept_master("east")

    # Partial-state invariant: pending still intact, nothing in masters/.
    assert pending.exists(), "pending key must remain if apply crashed"
    accepted = pki_root / "masters" / "east.pub"
    assert not accepted.exists(), (
        "accepted key must NOT exist if apply crashed; otherwise the "
        "file-moved-but-Raft-not-committed invariant is violated"
    )
    # Propose did fire -- that's what makes the crash-resume path safe.
    assert raft_service.proposed, "propose must happen before apply"


def test_accept_master_clustered_apply_replay_is_idempotent(
    clustered_opts, raft_service, pki_root, sm
):
    """
    Crash-resume safety: on restart, replaying the already-proposed
    attach entry re-does the rename idempotently (file ends up in
    ``masters/``, no exception).
    """
    pending = pki_root / "masters_pre" / "east.pub"
    _write_pub(pending, FAKE_PUB_EAST)

    # First attempt crashes mid-apply.
    raft_service.crash_on = LogEntryType.MASTER_PEER_ATTACH
    with _make_key(clustered_opts) as key:
        with pytest.raises(RuntimeError):
            key.accept_master("east")

    # Replay: Raft re-delivers the committed entry to apply().
    raft_service.crash_on = None
    _, cmd = raft_service.proposed[-1]
    sm.apply(cmd, client_id="replay", sequence_num=99)

    accepted = pki_root / "masters" / "east.pub"
    assert accepted.exists(), "replay should rename pending -> accepted"
    assert accepted.read_bytes() == FAKE_PUB_EAST
    assert not pending.exists()

    # And a second replay is still a no-op (apply is idempotent).
    sm.apply(cmd, client_id="replay", sequence_num=100)
    assert accepted.exists()


# ---------------------------------------------------------------------------
# reject_master
# ---------------------------------------------------------------------------


def test_reject_master_moves_pending_to_rejected(solo_opts, pki_root):
    pending = pki_root / "masters_pre" / "east.pub"
    _write_pub(pending, FAKE_PUB_EAST)

    with _make_key(solo_opts) as key:
        ret = key.reject_master("east")

    rejected = pki_root / "masters_rejected" / "east.pub"
    assert rejected.exists()
    assert rejected.read_bytes() == FAKE_PUB_EAST
    assert not pending.exists()
    assert ret == {"rejected": ["east"]}


def test_reject_master_missing_pending_is_noop(solo_opts):
    with _make_key(solo_opts) as key:
        ret = key.reject_master("east")
    assert ret == {"rejected": []}


# ---------------------------------------------------------------------------
# delete_master -- solo + clustered propose-first
# ---------------------------------------------------------------------------


def test_delete_master_solo_removes_file(solo_opts, pki_root):
    accepted = pki_root / "masters" / "east.pub"
    _write_pub(accepted, FAKE_PUB_EAST)

    with _make_key(solo_opts) as key:
        ret = key.delete_master("east")

    assert not accepted.exists()
    assert ret == {"deleted": ["east"]}


def test_delete_master_clustered_proposes_detach(
    clustered_opts, raft_service, pki_root, sm
):
    """
    On clustered, ``delete_master`` proposes
    ``MASTER_PEER_DETACH`` and the apply handler removes the file.
    salt-key does NOT touch the file directly.
    """
    accepted = pki_root / "masters" / "east.pub"
    _write_pub(accepted, FAKE_PUB_EAST)
    # Seed the registry via the SM's writer (same process, shared handle)
    # so the detach apply has something to delete.
    registry.set_peer(
        sm.registry,
        "east",
        {
            "cluster_id": "east",
            "public_key": FAKE_PUB_EAST,
            "endpoints": (),
            "attached_at": 0.0,
        },
    )

    with _make_key(clustered_opts) as key:
        key.delete_master("east")

    # Exactly one detach proposed.
    detaches = [cmd for kind, cmd in raft_service.proposed if kind == "detach"]
    assert len(detaches) == 1
    cmd = detaches[0]
    assert cmd["type"] == LogEntryType.MASTER_PEER_DETACH
    assert cmd["cluster_id"] == "east"

    # Apply handler removed the file (default reason="revoked" deletes).
    assert not accepted.exists()


def test_delete_master_clustered_crash_before_apply_no_partial_state(
    clustered_opts, raft_service, pki_root
):
    """
    propose fires, apply crashes: the file must stay in
    ``masters/`` (nothing partial under ``masters_denied/``).
    """
    accepted = pki_root / "masters" / "east.pub"
    _write_pub(accepted, FAKE_PUB_EAST)

    raft_service.crash_on = LogEntryType.MASTER_PEER_DETACH
    with _make_key(clustered_opts) as key:
        with pytest.raises(RuntimeError, match="simulated apply crash"):
            key.delete_master("east")

    assert accepted.exists(), "accepted file must survive apply crash"
    denied = pki_root / "masters_denied" / "east.pub"
    assert not denied.exists()
    assert raft_service.proposed, "propose must happen before apply"


# ---------------------------------------------------------------------------
# finger_master
# ---------------------------------------------------------------------------


def test_finger_master_returns_fingerprint_string(solo_opts, pki_root):
    """
    ``finger_master`` returns the fingerprint of the peer's stored
    key regardless of which bucket (accepted/pending/rejected) it
    lives in.
    """
    accepted = pki_root / "masters" / "east.pub"
    _write_pub(accepted, FAKE_PUB_EAST)
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB_EAST, sum_type="sha256")

    with _make_key(solo_opts) as key:
        got = key.finger_master("east")

    assert got == expected


def test_finger_master_falls_back_through_buckets(solo_opts, pki_root):
    """
    If no accepted key exists, ``finger_master`` finds the key in
    the pending / rejected / denied buckets.
    """
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB_WEST, sum_type="sha256")
    _write_pub(pki_root / "masters_pre" / "west.pub", FAKE_PUB_WEST)

    with _make_key(solo_opts) as key:
        got = key.finger_master("west")
    assert got == expected


def test_finger_master_missing_returns_empty_string(solo_opts):
    with _make_key(solo_opts) as key:
        got = key.finger_master("east")
    assert got == ""
