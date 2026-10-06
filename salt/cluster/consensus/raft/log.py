"""
Raft replicated log, persistence interfaces, and state machine hooks.

### Maintainability guardrail: logic / side-effect firewall

Classes here define the **side-effect boundaries** the consensus core talks
to.  :class:`BaseStorage` and :class:`BaseStateMachine` are abstract so the
algorithm stays testable without real disks or networks.  The production
implementation lives in :mod:`salt.cluster.consensus.storage`.
"""

import base64
import json
import logging
from typing import NamedTuple

log = logging.getLogger(__name__)

# Envelope marker for multi-state-machine snapshots.  See
# Log.snapshot / Log.restore_state_machines_from_data.  Bumping this
# version is a breaking change for on-disk snapshot compatibility.
SNAPSHOT_ENVELOPE_VERSION = "raft.snapshot.v1"


class LogEntryCommitStatus:
    """
    Tracks which nodes have replicated a specific log entry.

    Used by the leader to determine when an entry is committed (replicated
    to a majority).
    """

    def __init__(self, total_nodes, initial_node=None):
        """Initialize the commitment status."""
        self.total_nodes = total_nodes
        self._committed_nodes = set()
        if initial_node:
            self._committed_nodes.add(initial_node)

    def set(self, node_id):
        """Mark this entry as replicated by node_id."""
        self._committed_nodes.add(node_id)

    def committed(self):
        """Return True if a majority of nodes have replicated this entry."""
        count = len(self._committed_nodes)
        return count >= (self.total_nodes // 2) + 1

    def info(self, include_commits=False):
        """Return a dict summary of commitment status."""
        data = {"committed": self.committed()}
        if include_commits:
            data["committed_nodes"] = list(self._committed_nodes)
        return data


class LogEntryType:
    """Enum for types of log entries."""

    COMMAND = 0
    CONFIG = 1
    SNAPSHOT = 2
    # Ring policy commit (members source + replication factor).  Lives
    # in a *per-ring* Raft log and drives that ring's
    # ``RingConfigStateMachine``.  Was originally a cluster-log entry
    # in the single-ring design; the multi-ring world treats it as
    # per-ring state.
    RING_CONFIG = 3
    # Cluster-log registry entry: ``{"ring_id": str,
    # "founding_voters": [str, ...], "status": "active"|"destroyed"}``.
    # Applied by ``RingRegistryStateMachine`` on the cluster log; the
    # daemon brings up (or tears down) the named ring's Raft group
    # when the entry commits.
    RING_REGISTRY = 4
    # Cluster-log data-type routing entry: ``{"data_type": str,
    # "ring_id": str|None}``.  Applied by ``RoutingStateMachine`` on
    # the cluster log; gates consult the routing table to decide
    # which ring (if any) owns a given cache.
    ROUTE = 5


class LogEntry(NamedTuple):
    """Represents a single entry in the Raft log (zero-copy optimized).

    The 'cmd' field is treated as raw cargo (bytes or memoryview).
    """

    term: int
    index: int
    cmd: bytes  # Can also be memoryview for zero-copy access
    node_id: str = None  # noqa: TYP005
    type: int = 0  # 0 = COMMAND, 1 = CONFIG  # noqa: TYP005
    client_id: str = None  # noqa: TYP005
    sequence_num: int = None  # noqa: TYP005

    @property
    def cmd_bytes(self):
        """Get cmd as bytes, converting memoryview if necessary."""
        if isinstance(self.cmd, memoryview):
            return self.cmd.tobytes()
        return self.cmd

    def __eq__(self, other):
        if isinstance(other, (bytes, str, memoryview)):
            target = other
            if isinstance(target, str):
                target = target.encode()
            elif isinstance(target, memoryview):
                target = target.tobytes()
            return self.cmd_bytes == target
        return tuple.__eq__(self, other)

    @property
    def cmd_view(self):
        """Get cmd as memoryview for zero-copy access."""
        if isinstance(self.cmd, memoryview):
            return self.cmd
        return memoryview(self.cmd)

    def info(self, include_commits=False):  # noqa: TYP004
        """Return a serializable representation of the entry."""
        # Convert bytes/memoryview cmd to string for JSON serialization
        cmd_str = self.cmd_bytes
        if isinstance(cmd_str, bytes):
            cmd_str = cmd_str.decode("utf-8", errors="replace")
        return (
            self.term,
            self.index,
            cmd_str,
            self.node_id,
            self.type,
            self.client_id,
            self.sequence_num,
        )


class BaseStorage:
    """
    Abstract interface for log and state persistence.

    Implementations should handle low-level disk I/O and durability (fsync).
    """

    def save_state(self, term, voted_for):
        """Persist currentTerm and votedFor (§5.2)."""
        raise NotImplementedError

    def load_state(self):
        """Load persisted state. Returns dict with 'term' and 'voted_for'."""
        raise NotImplementedError

    def save_log(self, entries):
        """Rewrite the entire log (used during log truncation or recovery)."""
        raise NotImplementedError

    def append_log(self, entry):
        """Append a single entry to the log (optional optimization)."""

    def load_log(self):
        """Load all persisted log entries. Returns list of LogEntry."""
        raise NotImplementedError

    def save_snapshot(self, data, index, term):
        """Persist a state machine snapshot and its metadata."""
        raise NotImplementedError

    def load_snapshot(self):
        """Load the latest snapshot. Returns dict with 'data', 'index', 'term'."""
        raise NotImplementedError


class Log:
    """
    Manages the replicated log for a Raft node.

    Handles Raft indexing, log offsets due to compaction, consistency checks,
    and delegation to persistence storage.
    """

    def __init__(self, term=0, index=None, storage=None, **kwargs):
        """Initialize the replicated log."""
        self._term = term
        self.entries = []
        self.storage = storage
        self.last_included_index = -1
        self.last_included_term = 0
        self._cached_index = -1
        self.state_machine = kwargs.get("state_machine")
        # Additional named state machines (e.g. ``membership_sm``) whose state
        # must also survive log compaction.  Snapshot/restore dispatches
        # through this registry on top of ``self.state_machine``.
        self._extra_state_machines = dict(kwargs.get("state_machines") or {})
        self.max_log_size = kwargs.get("max_log_size")
        self.commit_index = -1
        self.last_applied = -1

        if self.storage:
            self.entries = self.storage.load_log()
            snapshot = self.storage.load_snapshot()
            if snapshot:
                self.last_included_index = snapshot["index"]
                self.last_included_term = snapshot["term"]
                self.restore_state_machines_from_data(snapshot["data"])
            state = self.storage.load_state()
            self._term = state.get("term", 0) if isinstance(state, dict) else state[0]

        self._update_cached_index()

    def register_state_machine(self, name, sm):
        """
        Register an additional named state machine.

        The SM's ``get_snapshot()`` / ``restore_snapshot()`` are wired into
        :meth:`snapshot` and :meth:`restore_state_machines_from_data` so its
        state survives log compaction along with the application state
        machine.  ``name`` keys the SM inside the snapshot envelope and must
        be stable across restarts.
        """
        self._extra_state_machines[name] = sm

    def _update_cached_index(self):
        """Update the cached index based on current entries and snapshot."""
        if not self.entries:
            self._cached_index = self.last_included_index
        else:
            self._cached_index = self.entries[-1].index

    def __repr__(self):
        """Return a string representation of the log."""
        return f"<Log(term={self.term!r}, index={self.index!r}, last_included={self.last_included_index!r})>"

    @property
    def index(self):
        """Return the Raft index of the latest entry in the log."""
        if self.entries:
            return self.entries[-1].index
        return self.last_included_index

    @property
    def last_index(self):
        return self.index

    @property
    def term(self):
        """Return the current term of the log."""
        return self._term

    @term.setter
    def term(self, value):
        self._term = value

    @property
    def last_term(self):
        if self.entries:
            return self.entries[-1].term
        return self.last_included_term

    def get_entry(self, index):
        """
        Retrieve the entry at a specific Raft index, accounting for log offsets.

        Return None if the index has been discarded by snapshotting or doesn't exist.
        """
        if index <= self.last_included_index:
            return None
        internal_idx = index - (self.last_included_index + 1)
        res = None
        if 0 <= internal_idx < len(self.entries):
            res = self.entries[internal_idx]
        return res

    def get(self, index):
        return self.get_entry(index)

    def add(
        self,
        term,
        cmd,
        commit_status=None,
        node_id=None,
        index=None,
        entry_type=LogEntryType.COMMAND,
        in_memory_only=False,
        client_id=None,
        sequence_num=None,
    ):
        """
        Add a new entry to the log.
        """
        if term > self.term:
            self.term = term

        res = None
        if index is None:
            new_index = self.index + 1
            entry = LogEntry(
                term, new_index, cmd, node_id, entry_type, client_id, sequence_num
            )
            self.entries.append(entry)
            if self.storage and not in_memory_only:
                self.storage.append_log(entry)
            res = new_index
        else:
            if index <= self.last_included_index:
                return False

            internal_idx = index - (self.last_included_index + 1)

            if internal_idx < len(self.entries):
                existing = self.entries[internal_idx]
                if existing.term == term:
                    return index
                self.entries = self.entries[:internal_idx]
                entry = LogEntry(
                    term, index, cmd, node_id, entry_type, client_id, sequence_num
                )
                self.entries.append(entry)
                if self.storage and not in_memory_only:
                    self.storage.save_log(self.entries)
                res = index
            else:
                entry = LogEntry(
                    term, index, cmd, node_id, entry_type, client_id, sequence_num
                )
                self.entries.append(entry)
                if self.storage and not in_memory_only:
                    self.storage.append_log(entry)
                res = index

        self._update_cached_index()

        # Trigger automatic snapshot if log exceeds max size
        if self.max_log_size and len(self.entries) >= self.max_log_size:
            if self.entries and self.commit_index >= self.entries[0].index:
                self.snapshot()

        return res

    def append(
        self,
        term,
        data,
        index=None,
        entry_type=LogEntryType.COMMAND,
        client_id=None,
        sequence_num=None,
    ):
        return self.add(
            term,
            data,
            index=index,
            entry_type=entry_type,
            client_id=client_id,
            sequence_num=sequence_num,
        )

    def snapshot(self):
        """
        Compact the log by snapshotting every registered state machine.

        Writes a versioned envelope::

            {"__envelope__": "raft.snapshot.v1",
             "machines": {"state_machine": ..., "membership_sm": ..., ...}}

        Each SM's payload is the value of its ``get_snapshot()``; bytes
        payloads are base64-wrapped so the envelope stays JSON-safe.  Older
        single-SM snapshots written before this format are still recognised
        on load (see :meth:`restore_state_machines_from_data`).
        """
        if not self.entries:
            return
        last_entry = self.entries[-1]
        self.last_included_index = last_entry.index
        self.last_included_term = last_entry.term

        machines = {}
        if self.state_machine:
            machines["state_machine"] = self._encode_sm_payload(
                self.state_machine.get_snapshot()
            )
        for name, sm in self._extra_state_machines.items():
            machines[name] = self._encode_sm_payload(sm.get_snapshot())

        if machines and self.storage:
            envelope = {
                "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
                "machines": machines,
            }
            self.storage.save_snapshot(
                envelope, self.last_included_index, self.last_included_term
            )

        # Discard entries up to last_included_index
        self.entries = []
        self._update_cached_index()

    def restore_state_machines_from_data(self, data):
        """
        Restore every registered state machine from snapshot ``data``.

        Recognises three input shapes:

        * Envelope dict (or JSON bytes containing one) with the
          ``__envelope__`` marker — dispatches each ``machines[name]``
          payload to the SM registered under that name.
        * Anything else — legacy single-SM payload; passed straight through
          to ``self.state_machine.restore_snapshot``.  Extra SMs keep their
          current state; the post-snapshot log replay rebuilds them.

        Missing keys are silently ignored so a snapshot written by an older
        node (or a node that didn't yet register a particular SM) restores
        cleanly.
        """
        envelope = self._maybe_envelope(data)
        if envelope is not None:
            machines = envelope.get("machines", {}) or {}
            sm_payload = machines.get("state_machine")
            if sm_payload is not None and self.state_machine:
                self.state_machine.restore_snapshot(self._decode_sm_payload(sm_payload))
            for name, sm in self._extra_state_machines.items():
                if name in machines:
                    sm.restore_snapshot(self._decode_sm_payload(machines[name]))
            return
        if self.state_machine is not None:
            self.state_machine.restore_snapshot(data)

    @staticmethod
    def _maybe_envelope(data):
        """Return *data* as an envelope dict, or ``None`` if it isn't one."""
        if isinstance(data, dict):
            if data.get("__envelope__") == SNAPSHOT_ENVELOPE_VERSION:
                return data
            return None
        if isinstance(data, (bytes, bytearray, memoryview)):
            try:
                obj = json.loads(bytes(data).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None
            if (
                isinstance(obj, dict)
                and obj.get("__envelope__") == SNAPSHOT_ENVELOPE_VERSION
            ):
                return obj
        return None

    @staticmethod
    def _encode_sm_payload(payload):
        """Make an SM ``get_snapshot()`` value safe to embed in a JSON envelope."""
        if isinstance(payload, (bytes, bytearray, memoryview)):
            return {
                "__bytes__": base64.b64encode(bytes(payload)).decode("ascii"),
            }
        return payload

    @staticmethod
    def _decode_sm_payload(payload):
        """Inverse of :meth:`_encode_sm_payload`."""
        if isinstance(payload, dict) and len(payload) == 1 and "__bytes__" in payload:
            return base64.b64decode(payload["__bytes__"])
        return payload

    def commit(self, index):
        self.commit_index = max(getattr(self, "commit_index", -1), index)

    def clear(self):
        """Discard all log entries."""
        self.entries = []
        if self.storage:
            self.storage.save_log(self.entries)
        self._update_cached_index()

    def has_entry(self, term, index, cmd=None):
        """
        Check Raft log entries for consistency.
        """
        if index is None or index == -1:
            return True

        if index == self.last_included_index:
            return term == self.last_included_term

        entry = self.get_entry(index)
        if entry is None:
            return False

        if entry.term != term:
            return False

        return True

    def truncate_prefix(self, index):
        """
        Discard all log entries up to and including 'index'.
        """
        if index <= self.last_included_index:
            return

        entry = self.get_entry(index)
        if entry:
            self.last_included_term = entry.term

        internal_idx = index - (self.last_included_index + 1)
        self.entries = self.entries[internal_idx + 1 :]
        self.last_included_index = index

        if self.storage:
            self.storage.save_log(self.entries)

        self._update_cached_index()


class BaseStateMachine:
    """
    Interface for the application-level State Machine.
    """

    def apply(self, cmd, client_id=None, sequence_num=None):
        """Apply a committed command to the state machine."""
        raise NotImplementedError

    def get_snapshot(self):
        """Serialize the current state of the state machine to bytes."""
        raise NotImplementedError

    def restore_snapshot(self, data):
        """Restore the state machine from a serialized snapshot."""
        raise NotImplementedError


class MembershipStateMachine(BaseStateMachine):
    """
    State machine for Raft cluster membership.

    Applies committed ``CONFIG`` log entries to maintain the authoritative
    set of voting members and learners.  Snapshot/restore support allows the
    membership state to survive log compaction.

    The ``on_change`` callback (if set) is called after every successful
    ``apply`` with ``(voters: list[str], learners: list[str])``.  Nodes use
    this hook to update their in-memory peer routing tables via
    ``Node.on_config_change``.

    Sequence
    --------
    1. Leader proposes ``CONFIG`` entry ``{voters: [...], learners: [...]}``.
    2. Entry is replicated and committed.
    3. ``Node.apply_entries`` calls ``membership_sm.apply(cmd, index=i)``.
    4. ``MembershipStateMachine`` updates its voter/learner sets and calls
       ``on_change(voters, learners)``.
    5. ``Node.on_config_change`` (wired as ``on_change``) updates
       ``Node.peers`` voting flags and ``Node.voting``.
    """

    def __init__(self, on_change=None):
        """
        :param on_change: Optional ``callable(voters, learners)`` called after
                          each successful ``apply``.  When set to ``None`` the
                          SM operates as a pure query store with no side effects.
        """
        self._voters = set()
        self._learners = set()
        self._membership_version = -1
        self.on_change = on_change

    # ------------------------------------------------------------------
    # BaseStateMachine interface
    # ------------------------------------------------------------------

    def apply(self, cmd, client_id=None, sequence_num=None, index=-1):
        """
        Apply a committed CONFIG entry.

        :param cmd:   ``dict`` with keys ``"voters"`` (list[str]) and
                      optionally ``"learners"`` (list[str]).  Non-dict values
                      are treated as a plain voter list with no learners.
        :param index: Raft log index of this entry (used as version stamp).
        """
        if isinstance(cmd, dict):
            voters = list(cmd.get("voters", []))
            learners = list(cmd.get("learners", []))
        else:
            voters = list(cmd) if cmd else []
            learners = []

        self._voters = set(voters)
        self._learners = set(learners)
        self._membership_version = index

        if self.on_change is not None:
            self.on_change(voters, learners)

    def get_snapshot(self):
        """Return JSON-serialisable dict of current membership state."""
        return {
            "voters": sorted(self._voters),
            "learners": sorted(self._learners),
            "version": self._membership_version,
        }

    def restore_snapshot(self, data):
        """Restore membership from a snapshot dict (as produced by ``get_snapshot``)."""
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode())
        if not isinstance(data, dict):
            return
        self._voters = set(data.get("voters", []))
        self._learners = set(data.get("learners", []))
        self._membership_version = data.get("version", -1)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def current_voters(self):
        """Return a sorted list of current voting members."""
        return sorted(self._voters)

    def current_learners(self):
        """Return a sorted list of current learner (non-voting) members."""
        return sorted(self._learners)

    def is_voter(self, node_id):
        """Return True if *node_id* is in the current voter set."""
        return node_id in self._voters

    def is_learner(self, node_id):
        """Return True if *node_id* is in the current learner set."""
        return node_id in self._learners

    @property
    def membership_version(self):
        """Log index of the most recently applied CONFIG entry, or -1 if none."""
        return self._membership_version

    def __repr__(self):
        return (
            f"<MembershipStateMachine voters={sorted(self._voters)} "
            f"learners={sorted(self._learners)} version={self._membership_version}>"
        )


# ---------------------------------------------------------------------------
# RingConfigStateMachine
# ---------------------------------------------------------------------------


# Valid values for the ring's ``members`` policy.
RING_MEMBERS_SELF = "self"
RING_MEMBERS_VOTERS = "voters"
RING_MEMBERS_VALID = (RING_MEMBERS_SELF, RING_MEMBERS_VOTERS)


class RingConfigStateMachine(BaseStateMachine):
    """
    State machine for the cluster's :class:`~salt.cluster.ring.HashRing`
    policy — *what* the ring contains and *how many replicas* per key.

    Two committable knobs:

    * ``members`` — ``"self"`` (default; ring contains only this master so
      every key is owned locally — preserves today's broadcast behaviour)
      or ``"voters"`` (ring is rebuilt from the committed Raft voter set
      so writes shard across the cluster).
    * ``replicas`` — replication factor.  ``1`` (default) means each key
      has exactly one owner with no backups.  Higher values request the
      ring to keep the top-N nodes as replicas; the runner validates
      against ``len(voters)``.

    Driven by a ``LogEntryType.RING_CONFIG`` entry proposed through
    Raft (typically by a ``cluster.ring`` runner).  Operators flip from
    self-only to cluster-wide sharding by committing a single entry; no
    code changes required.

    The ``on_change`` callback (if set) runs after every successful
    ``apply`` with ``(members, replicas)``.  ``RaftService`` wires this
    to update :func:`salt.cluster.ring_membership.rebuild` so the
    process-local ring re-syncs to the new policy.

    Snapshot/restore round-trips through the same envelope shape used by
    ``MembershipStateMachine`` (registered under name ``"ring_sm"``), so
    ring config survives log compaction.
    """

    def __init__(self, on_change=None):
        self._members = RING_MEMBERS_SELF
        self._replicas = 1
        self._version = -1
        self.on_change = on_change

    # ------------------------------------------------------------------
    # BaseStateMachine interface
    # ------------------------------------------------------------------

    def apply(self, cmd, client_id=None, sequence_num=None, index=-1):
        """
        Apply a committed RING_CONFIG entry.

        :param cmd:   ``dict`` with keys ``"members"`` (str, one of
                      ``RING_MEMBERS_VALID``) and ``"replicas"`` (int).
                      Either may be omitted to keep the existing value
                      — useful for partial updates that only flip one
                      knob.  Unknown keys are ignored.
        :param index: Raft log index of this entry; stored as the
                      version stamp visible via :attr:`config_version`.
        """
        if isinstance(cmd, dict):
            new_members = cmd.get("members", self._members)
            new_replicas = cmd.get("replicas", self._replicas)
            if new_members in RING_MEMBERS_VALID:
                self._members = new_members
            else:
                log.warning(
                    "RingConfigStateMachine: ignoring unknown members policy %r "
                    "(expected one of %s)",
                    new_members,
                    RING_MEMBERS_VALID,
                )
            try:
                self._replicas = max(1, int(new_replicas))
            except (TypeError, ValueError):
                log.warning(
                    "RingConfigStateMachine: ignoring non-integer replicas %r",
                    new_replicas,
                )
        self._version = index
        if self.on_change is not None:
            self.on_change(self._members, self._replicas)

    def get_snapshot(self):
        """Return the JSON-serialisable ring policy."""
        return {
            "members": self._members,
            "replicas": self._replicas,
            "version": self._version,
        }

    def restore_snapshot(self, data):
        """Restore from a snapshot dict (as produced by :meth:`get_snapshot`)."""
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode())
        if not isinstance(data, dict):
            return
        members = data.get("members", self._members)
        if members in RING_MEMBERS_VALID:
            self._members = members
        try:
            self._replicas = max(1, int(data.get("replicas", self._replicas)))
        except (TypeError, ValueError):
            pass
        self._version = data.get("version", -1)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    @property
    def members(self):
        """Current members policy (``"self"`` or ``"voters"``)."""
        return self._members

    @property
    def replicas(self):
        """Current replication factor (>= 1)."""
        return self._replicas

    @property
    def config_version(self):
        """Log index of the most recently applied RING_CONFIG entry, or -1 if none."""
        return self._version

    def __repr__(self):
        return (
            f"<RingConfigStateMachine members={self._members!r} "
            f"replicas={self._replicas} version={self._version}>"
        )


# ---------------------------------------------------------------------------
# Multi-ring state machines (live on the cluster Raft log)
# ---------------------------------------------------------------------------


# Valid ring lifecycle states recorded in the registry.
RING_STATUS_ACTIVE = "active"
RING_STATUS_DESTROYED = "destroyed"
RING_STATUS_VALID = (RING_STATUS_ACTIVE, RING_STATUS_DESTROYED)


class RingRegistryStateMachine(BaseStateMachine):
    """
    Cluster-log registry of named rings.

    For each named Raft "ring" (a separate consensus group used to
    shard one Salt cache), the registry tracks ``founding_voters``
    (initial voter list at create time) and ``status`` (``"active"``
    or ``"destroyed"``).  Once a ring is created and brought up,
    further membership and policy churn lives in *that ring's own*
    Raft log — the registry only records the lifecycle moments
    cluster-wide consensus needs to agree on.

    Command shape applied from a ``LogEntryType.RING_REGISTRY`` entry::

        {"ring_id": "jobs",
         "founding_voters": ["m1", "m2", "m3"],
         "status": "active"}

    Or, to destroy::

        {"ring_id": "jobs", "status": "destroyed"}

    On each commit ``on_change(ring_id, founding_voters, status)``
    fires; ``RaftService`` wires this to bring up or tear down the
    named ring's per-ring Raft group inside the publish daemon.

    Snapshot/restore round-trip through the same multi-SM envelope
    used by :class:`MembershipStateMachine`, registered under name
    ``"ring_registry_sm"``.
    """

    def __init__(self, on_change=None):
        # ring_id -> {"founding_voters": [...], "status": "active"|"destroyed"}
        self._rings = {}
        self._version = -1
        self.on_change = on_change

    # ------------------------------------------------------------------
    # BaseStateMachine interface
    # ------------------------------------------------------------------

    def apply(self, cmd, client_id=None, sequence_num=None, index=-1):
        """
        Apply a committed RING_REGISTRY entry.

        Status defaults to ``"active"`` so the common create case is
        a two-field commit; founding voters are sorted to canonicalise
        the on-disk representation.  ``ring_id`` is required.
        """
        if not isinstance(cmd, dict):
            log.warning("RingRegistryStateMachine: ignoring non-dict cmd %r", cmd)
            return
        ring_id = cmd.get("ring_id")
        if not ring_id:
            log.warning(
                "RingRegistryStateMachine: ignoring entry without ring_id: %r",
                cmd,
            )
            return
        status = cmd.get("status", RING_STATUS_ACTIVE)
        if status not in RING_STATUS_VALID:
            log.warning(
                "RingRegistryStateMachine: ignoring unknown status %r "
                "(expected one of %s)",
                status,
                RING_STATUS_VALID,
            )
            return
        existing = self._rings.get(ring_id) or {}
        # Preserve the existing founding_voters when the incoming
        # entry omits them — destroy commits ride this path so the
        # audit trail keeps "who founded this ring."  ``cmd.get`` is
        # checked against ``None`` rather than truthiness so an
        # explicit empty list still wins (operator-driven correction).
        if "founding_voters" in cmd and cmd.get("founding_voters") is not None:
            founders = sorted(cmd["founding_voters"] or [])
        else:
            founders = existing.get("founding_voters", [])
        # Destruction of a never-registered ring is a no-op write to
        # the registry — keep the entry so the lifecycle is auditable.
        self._rings[ring_id] = {
            "founding_voters": founders,
            "status": status,
        }
        self._version = index
        if self.on_change is not None:
            self.on_change(ring_id, founders, status)

    def get_snapshot(self):
        """Return the JSON-serialisable registry."""
        return {
            "rings": {ring_id: dict(entry) for ring_id, entry in self._rings.items()},
            "version": self._version,
        }

    def restore_snapshot(self, data):
        """Restore from a snapshot dict (as produced by :meth:`get_snapshot`)."""
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode())
        if not isinstance(data, dict):
            return
        rings = data.get("rings", {})
        if isinstance(rings, dict):
            self._rings = {
                ring_id: {
                    "founding_voters": sorted(entry.get("founding_voters", []) or []),
                    "status": entry.get("status", RING_STATUS_ACTIVE),
                }
                for ring_id, entry in rings.items()
                if isinstance(entry, dict)
            }
        self._version = data.get("version", -1)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def rings(self):
        """Return the full ring_id -> entry dict.  Copy; callers may mutate."""
        return {ring_id: dict(entry) for ring_id, entry in self._rings.items()}

    def active_rings(self):
        """Return a sorted list of ring ids whose status is ``"active"``."""
        return sorted(
            ring_id
            for ring_id, entry in self._rings.items()
            if entry.get("status") == RING_STATUS_ACTIVE
        )

    def get(self, ring_id):
        """Return the registry entry for *ring_id*, or ``None`` if unknown."""
        entry = self._rings.get(ring_id)
        return dict(entry) if entry is not None else None

    @property
    def registry_version(self):
        """Log index of the most recently applied RING_REGISTRY entry, or -1."""
        return self._version

    def __repr__(self):
        return (
            f"<RingRegistryStateMachine rings={sorted(self._rings)} "
            f"version={self._version}>"
        )


class RoutingStateMachine(BaseStateMachine):
    """
    Cluster-log data-type -> ring mapping.

    For each Salt data type that a master writes to a cache (e.g.
    ``"jobs"``), the routing table answers "which ring owns this
    data?".  A mapping of ``None`` means *broadcast* — no ring is
    consulted and every master writes the data unconditionally
    (the pre-multi-ring default).

    Command shape applied from a ``LogEntryType.ROUTE`` entry::

        {"data_type": "jobs", "ring_id": "jobs_ring"}

    Or, to clear a route back to broadcast::

        {"data_type": "jobs", "ring_id": None}

    On each commit ``on_change(data_type, ring_id)`` fires;
    ``RaftService`` wires this so the local routing table used by the
    gate sites in ``salt/master.py`` stays in sync without IPC.

    Snapshot/restore round-trip through the same multi-SM envelope
    used by :class:`MembershipStateMachine`, registered under name
    ``"routing_sm"``.
    """

    def __init__(self, on_change=None):
        # data_type -> ring_id or None
        self._routes = {}
        self._version = -1
        self.on_change = on_change

    # ------------------------------------------------------------------
    # BaseStateMachine interface
    # ------------------------------------------------------------------

    def apply(self, cmd, client_id=None, sequence_num=None, index=-1):
        """Apply a committed ROUTE entry."""
        if not isinstance(cmd, dict):
            log.warning("RoutingStateMachine: ignoring non-dict cmd %r", cmd)
            return
        data_type = cmd.get("data_type")
        if not data_type:
            log.warning(
                "RoutingStateMachine: ignoring entry without data_type: %r",
                cmd,
            )
            return
        # Use a sentinel so we can distinguish "ring_id absent" (treat as
        # a clear-to-broadcast) from "ring_id explicitly None".  Both
        # map to broadcast semantically, so we accept either; the more
        # natural form for an operator is to send ``"ring_id": None``.
        ring_id = cmd.get("ring_id")
        self._routes[data_type] = ring_id
        self._version = index
        if self.on_change is not None:
            self.on_change(data_type, ring_id)

    def get_snapshot(self):
        """Return the JSON-serialisable routing table."""
        return {
            "routes": dict(self._routes),
            "version": self._version,
        }

    def restore_snapshot(self, data):
        """Restore from a snapshot dict (as produced by :meth:`get_snapshot`)."""
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode())
        if not isinstance(data, dict):
            return
        routes = data.get("routes", {})
        if isinstance(routes, dict):
            self._routes = dict(routes)
        self._version = data.get("version", -1)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def routes(self):
        """Return a copy of the data_type -> ring_id mapping."""
        return dict(self._routes)

    def get(self, data_type, default=None):
        """Return the ring_id for *data_type*, or *default* if unrouted."""
        return self._routes.get(data_type, default)

    @property
    def routing_version(self):
        """Log index of the most recently applied ROUTE entry, or -1."""
        return self._version

    def __repr__(self):
        return (
            f"<RoutingStateMachine routes={self._routes!r} " f"version={self._version}>"
        )


class CounterStateMachine(BaseStateMachine):
    """Simple state machine that counts applied commands with exactly-once logic."""

    def __init__(self):
        """Initialize the counter and sessions."""
        self.count = 0
        # client_id -> last_sequence_num
        self.sessions = {}

    def apply(self, cmd, client_id=None, sequence_num=None):
        """Increment the counter for each applied command (accepts bytes or strings)."""
        if client_id is not None and sequence_num is not None:
            last_seq = self.sessions.get(client_id, -1)
            if sequence_num <= last_seq:
                # Duplicate request, do not execute
                return self.count
            self.sessions[client_id] = sequence_num

        self.count += 1
        return self.count

    def get_snapshot(self):
        """Return the current count and sessions as a JSON-encoded snapshot."""
        return json.dumps({"count": self.count, "sessions": self.sessions}).encode(
            "utf-8"
        )

    def restore_snapshot(self, data):
        """Restore the counter and sessions from a snapshot."""
        if not isinstance(data, dict):
            log.debug(
                "CounterStateMachine.restore_snapshot expected dict, got %s", type(data)
            )
            # If it's bytes, it should have been decoded by Node, but let's be safe
            if isinstance(data, (bytes, bytearray)):
                try:
                    data = json.loads(data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    data = {}
            else:
                data = {}

        self.count = data.get("count", 0)
        self.sessions = data.get("sessions", {})
