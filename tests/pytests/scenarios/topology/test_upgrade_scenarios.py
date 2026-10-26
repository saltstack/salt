"""
Scenario tests for the master-topology rolling-upgrade protocol-version gate.

RFC: ``rfcs/master-topology.md`` --- "Rolling-upgrade protocol-version gate"
section (currently lines 280-300 of that document).

Operator-visible contract (quoted from the RFC)
-----------------------------------------------

* "Pre-topology peers advertise protocol version N."
* "Topology-aware peers advertise protocol version N+1."
* "No ``MASTER_*`` log entry can be committed while any cluster
  peer still advertises N."
* "``salt-key -a --master`` on a mixed-version cluster fails
  cleanly with an operator-visible error telling them to
  finish the rolling upgrade first."
* Implementation plan from the RFC: "register the protocol
  version as a cluster opt propagated via
  ``MembershipStateMachine`` at join time;
  ``RaftService.propose`` for ``MASTER_*`` types checks the
  cluster-wide minimum before proposing."

Implementation state (branch ``dwoz/master-topology`` at
``82129fc338e``)
-----------------------------------------------------------

The protocol-version gate is **not yet implemented**.  Specifically:

* ``salt/cluster/consensus/service.py`` has no ``protocol_version``
  attribute, no ``_min_cluster_protocol_version`` helper, and no
  gate check on any ``propose_*`` method.  ``RaftService`` does not
  even define a ``propose_peer_attach``; the method is attached at
  runtime by ``salt.topology.link_manager`` on wired clusters.
* ``salt/cluster/consensus/raft/log.py``'s ``MembershipStateMachine``
  stores voters + learners but carries no per-peer protocol version
  advertisement.
* ``salt/cluster/consensus/raft/topology.py``'s ``TopologyStateMachine.apply``
  (lines 170-174) silently *logs at DEBUG and ignores* unknown
  entry types --- exactly the "silent no-op on old peers" that the
  RFC gate was designed to prevent.

The two scenarios below are therefore written as ``xfail(strict=True)``.
Each one documents what SHOULD happen when the gate lands; the
``strict=True`` means an xfail that unexpectedly passes will fail
the suite, flagging the moment the gate is implemented so the
scenarios can be flipped from xfail to passing in the same commit
that lands the gate.

Follow-up work surfaced by this file
------------------------------------

* ``RaftService``: add ``protocol_version`` opt (default N+1 on this
  branch), propagate via ``MembershipStateMachine`` join, expose
  ``_min_cluster_protocol_version()``, and gate every ``MASTER_*``
  propose on ``_min_cluster_protocol_version() >= N+1``.
* ``RaftService``: raise a specific exception (e.g.
  ``MixedVersionClusterError``) on gated propose so
  ``salt.key.Key.accept_master`` can surface a clean operator-visible
  error instead of a generic ``RuntimeError``.
* ``TopologyStateMachine.apply``: on an unknown ``MASTER_*`` entry
  type, log at ERROR (not DEBUG) and either refuse to apply or
  raise.  A silent no-op is wrong even in steady-state: it means
  an older peer silently diverges from the cluster if the gate ever
  fails open.
"""

import logging

import pytest

from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Protocol version constants + exception stand-in
# ---------------------------------------------------------------------------
#
# These names are what the implementation is expected to expose
# once the gate lands.  Importing them from a well-known place in
# ``salt.cluster.consensus`` would make these scenarios pass; today
# the imports would fail, so we define local placeholders and the
# assertions name the gap explicitly.


# Protocol version this branch's topology code implements.  The
# RFC calls this "N+1"; concrete value is implementation-defined
# but any value strictly greater than ``PROTOCOL_VERSION_PRE_TOPOLOGY``
# is correct.
PROTOCOL_VERSION_TOPOLOGY = 2  # expected default once the gate lands
PROTOCOL_VERSION_PRE_TOPOLOGY = 1  # the "N" in the RFC


FAKE_PUB_EAST = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"east-identity-key-for-upgrade-scenario\n"
    b"-----END PUBLIC KEY-----\n"
)


# ---------------------------------------------------------------------------
# Fake Raft service used by scenario 1
# ---------------------------------------------------------------------------


class _MixedVersionClusterError(RuntimeError):
    """
    Stand-in for the exception the real ``RaftService`` is expected to
    raise when ``propose_peer_attach`` is called on a mixed-version
    cluster.  Mirrors the "specific exception from RaftService" the
    task spec calls for.  Lives here so scenario 1 can assert
    *something concrete* even though the production exception type
    does not yet exist.
    """


class _MixedVersionFakeRaftService:
    """
    Fake :class:`RaftService` that advertises per-peer protocol
    versions and refuses ``MASTER_*`` proposes while any peer still
    advertises the pre-topology version.

    Models the shape the real implementation is expected to grow:

    * ``peer_protocol_versions``: dict ``peer_id -> int``.  Populated
      from the ``MembershipStateMachine`` join handshake once that
      wire format carries a protocol version.
    * ``_min_cluster_protocol_version()``: returns the minimum of
      the above; the gate check.
    * ``propose_peer_attach`` (and sibling ``MASTER_*`` proposers):
      checks ``_min_cluster_protocol_version()`` against the local
      topology version and raises :class:`_MixedVersionClusterError`
      if any peer is behind.

    Scenario 1 asserts that calling ``propose_peer_attach`` on a
    cluster where peer3 advertises ``PROTOCOL_VERSION_PRE_TOPOLOGY``
    raises :class:`_MixedVersionClusterError` **and** does not touch
    the on-disk ``masters_pre/`` -> ``masters/`` rename on any peer.
    """

    def __init__(self, state_machine, peer_protocol_versions):
        self._sm = state_machine
        self.peer_protocol_versions = dict(peer_protocol_versions)
        self.proposed = []  # list of (kind, cmd)
        self.my_protocol_version = PROTOCOL_VERSION_TOPOLOGY

    # Attributes the gate is expected to add to the real service.
    def _min_cluster_protocol_version(self):
        if not self.peer_protocol_versions:
            return self.my_protocol_version
        return min(self.peer_protocol_versions.values())

    def propose_peer_attach(
        self, cluster_id, public_key, endpoints=(), attached_at=0.0, **kwargs
    ):
        if self._min_cluster_protocol_version() < PROTOCOL_VERSION_TOPOLOGY:
            laggards = sorted(
                peer_id
                for peer_id, version in self.peer_protocol_versions.items()
                if version < PROTOCOL_VERSION_TOPOLOGY
            )
            raise _MixedVersionClusterError(
                "cluster peer(s) advertise pre-topology protocol version; "
                f"finish rolling upgrade first (laggards: {laggards})"
            )
        cmd = {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": cluster_id,
            "public_key": public_key,
            "endpoints": tuple(endpoints),
            "attached_at": float(attached_at),
        }
        cmd.update(kwargs)
        self.proposed.append(("attach", cmd))
        self._sm.apply(cmd, client_id="salt-key", sequence_num=len(self.proposed))

    def propose_peer_detach(self, cluster_id, reason="revoked", **kwargs):
        if self._min_cluster_protocol_version() < PROTOCOL_VERSION_TOPOLOGY:
            raise _MixedVersionClusterError(
                "cluster peer(s) advertise pre-topology protocol version"
            )
        cmd = {
            "type": LogEntryType.MASTER_PEER_DETACH,
            "cluster_id": cluster_id,
            "reason": reason,
        }
        cmd.update(kwargs)
        self.proposed.append(("detach", cmd))
        self._sm.apply(cmd, client_id="salt-key", sequence_num=len(self.proposed))


# ---------------------------------------------------------------------------
# Scenario 1 --- mixed-version cluster blocks MASTER_PEER_ATTACH
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Protocol-version gate not implemented. "
        "salt/cluster/consensus/service.py exposes no "
        "protocol_version opt, no _min_cluster_protocol_version() "
        "helper, and no gate check on propose_peer_attach. "
        "Flipping this test to passing requires: (a) MembershipStateMachine "
        "advertising per-peer protocol version at Raft join; "
        "(b) RaftService._min_cluster_protocol_version() returning "
        "the cluster-wide minimum; (c) RaftService.propose_peer_attach "
        "raising a specific exception (e.g. MixedVersionClusterError) "
        "when the minimum is below N+1; (d) salt.key.Key.accept_master "
        "surfacing that exception as a clean operator-visible error. "
        "See the docstring at the top of this file for the full checklist."
    ),
)
def test_mixed_version_cluster_blocks_peer_attach(tmp_path):
    """
    Scenario 1 --- A 3-peer cluster where peer1 and peer2 advertise
    the topology protocol version (N+1) and peer3 advertises the
    pre-topology version (N).  Operator runs
    ``salt-key -a east --master`` on peer1.

    Assertions:

    * ``propose_peer_attach`` raises a specific exception from
      RaftService (not a generic ``RuntimeError``) naming peer3 as
      the laggard.
    * No file is renamed on peer1 (crash-safety: salt-key does NOT
      touch the PKI dir until the Raft commit).  The ``masters_pre/``
      file must still exist, and ``masters/`` must still be empty.

    This test will fail on the current branch because the real
    ``RaftService`` does not implement the gate; see the module
    docstring for the full implementation checklist.
    """
    pki_root = tmp_path / "pki"
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)

    # Operator placed an incoming identity pub in masters_pre/.
    pending_path = pki_root / "masters_pre" / "east.pub"
    pending_path.write_bytes(FAKE_PUB_EAST)
    accepted_path = pki_root / "masters" / "east.pub"

    opts = {
        "pki_dir": str(pki_root),
        "cluster_id": "peer1",
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
    }
    sm = TopologyStateMachine(opts)
    try:
        service = _MixedVersionFakeRaftService(
            sm,
            peer_protocol_versions={
                "peer1": PROTOCOL_VERSION_TOPOLOGY,
                "peer2": PROTOCOL_VERSION_TOPOLOGY,
                # peer3 has not been upgraded yet.
                "peer3": PROTOCOL_VERSION_PRE_TOPOLOGY,
            },
        )

        # The RFC-promised failure mode: the propose must raise a
        # specific gate exception, not a generic error.  The gate
        # must be in the *real* RaftService --- the fake above
        # proves the shape, but the test fails on this branch
        # because the real exception type does not exist.  We look
        # it up by name via importlib so pylint cannot "helpfully"
        # tell us the name is missing: that's the whole point of
        # this xfail scenario, and a static import would break
        # linting before the gate ever lands.
        import importlib

        service_module = importlib.import_module("salt.cluster.consensus.service")
        try:
            mixed_version_exc = service_module.MixedVersionClusterError
        except AttributeError as missing:
            raise AssertionError(
                "RaftService protocol-version gate is not implemented: "
                "salt.cluster.consensus.service.MixedVersionClusterError "
                "does not exist on this branch.  See the module docstring "
                "for the full implementation checklist."
            ) from missing

        with pytest.raises(mixed_version_exc) as excinfo:
            service.propose_peer_attach(
                cluster_id="east",
                public_key=FAKE_PUB_EAST,
                endpoints=(),
                attached_at=1_700_000_000.0,
            )
        # The message must name peer3 so operators know which peer
        # to upgrade first.  This is a correctness bar, not a
        # cosmetic one: a generic "mixed version" message forces
        # operators to grep logs across the cluster.
        assert "peer3" in str(excinfo.value), (
            "operator-visible error must name the laggard peer; "
            f"got {excinfo.value!r}"
        )

        # Crash-safety: propose failure must not touch the PKI
        # directory.  salt-key's contract is "the apply handler
        # owns the rename"; a failed propose leaves no partial
        # state.
        assert (
            pending_path.exists()
        ), "propose failure must not consume the pending key file"
        assert (
            not accepted_path.exists()
        ), "propose failure must not rename the key file to masters/"
        assert service.proposed == [], (
            "a gated propose must record nothing; the shim only "
            "appends after the gate passes"
        )
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


# ---------------------------------------------------------------------------
# Scenario 2 --- unknown entry-type on an older peer must not silently no-op
# ---------------------------------------------------------------------------


class _PreTopologyStateMachine(TopologyStateMachine):
    """
    Simulates a pre-topology peer's state machine.

    Rolled-back peers advertise protocol version N (pre-topology).
    Such peers do not have the ``MASTER_PEER_ATTACH`` entry type
    in their ``LogEntryType`` enum --- the entry type did not exist
    before the topology feature landed.  When a committed
    ``MASTER_PEER_ATTACH`` reaches an older peer's state machine,
    one of two things must happen:

    1. The peer refuses to apply the entry (preferred; it means the
       cluster is wedged until the operator rolls everyone forward
       to the topology release, matching the RFC's "gate" wording),
       OR
    2. The peer logs an error at WARNING or higher and no-ops.

    What must NOT happen: a silent DEBUG-level no-op.  The current
    ``TopologyStateMachine.apply`` (lines 170-174) does exactly
    that for any entry type without a handler.  This scenario
    documents that gap.
    """

    def __init__(self, opts):
        super().__init__(opts)
        # Older peer: strip the MASTER_PEER_ATTACH handler.  The
        # SM thus does not know what to do with the entry type ---
        # the exact state a rolled-back peer would be in.
        self._handlers.pop(LogEntryType.MASTER_PEER_ATTACH, None)
        self._handlers.pop(LogEntryType.MASTER_PEER_DETACH, None)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Protocol-version gate not implemented. "
        "salt/cluster/consensus/raft/topology.py:170-174 silently "
        "logs unknown entry types at DEBUG and no-ops.  This is "
        "the exact behaviour the RFC rolling-upgrade gate was "
        "designed to prevent (silent divergence on older peers). "
        "Flipping this test to passing requires either: (a) the "
        "apply handler logs at WARNING/ERROR when it sees an "
        "unknown entry type AND the SM exposes a reject counter "
        "or sentinel the test can inspect; or (b) the apply "
        "raises so the Node's commit loop halts replication "
        "until the operator upgrades the peer."
    ),
)
def test_unknown_entry_type_on_pre_topology_peer_does_not_silently_noop(
    tmp_path, caplog
):
    """
    Scenario 2 --- A fully-upgraded cluster commits a
    ``MASTER_PEER_ATTACH`` entry; then one peer is rolled back to
    the pre-topology release (hypothetical --- not a real Salt
    operation, but useful to verify the dispatch doesn't silently
    diverge).

    Assertions:

    * When the pre-topology peer sees the ``MASTER_PEER_ATTACH``
      entry in Raft replay, it does NOT silently no-op at DEBUG
      level.
    * Either an exception is raised, or a log entry at WARNING or
      higher is emitted naming the entry type.

    Current behaviour (as of ``82129fc338e``): a DEBUG log line
    "no handler for entry type <N>; ignoring" and a silent return.
    This is the exact silent divergence the RFC protocol gate was
    designed to prevent at the propose side; this scenario
    documents that the apply side also needs defence in depth.
    """
    pki_root = tmp_path / "pki"
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)

    opts = {
        "pki_dir": str(pki_root),
        "cluster_id": "pre-topology-peer",
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
    }
    sm = _PreTopologyStateMachine(opts)
    try:
        entry = {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": "east",
            "public_key": FAKE_PUB_EAST,
            "endpoints": (),
            "attached_at": 1_700_000_000.0,
        }

        caplog.clear()
        raised = None
        with caplog.at_level(
            logging.DEBUG, logger="salt.cluster.consensus.raft.topology"
        ):
            try:
                sm.apply(entry, client_id="replay", sequence_num=1)
            except Exception as exc:  # pylint: disable=broad-except
                raised = exc

        # Acceptable outcome A: the apply raised a specific error.
        if raised is not None:
            # Any non-silent outcome is fine; the RFC gate's job
            # is to prevent silent divergence, not to specify a
            # particular exception shape at the SM layer.
            return

        # Acceptable outcome B: the SM logged at WARNING+ naming
        # the entry type.
        serious_records = [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING
            and r.name == "salt.cluster.consensus.raft.topology"
        ]
        assert serious_records, (
            "pre-topology peer must not silently no-op an unknown "
            "MASTER_* entry; expected WARNING+ log or raised "
            "exception, but got only DEBUG-level records: "
            f"{[(r.levelno, r.getMessage()) for r in caplog.records]}"
        )
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
