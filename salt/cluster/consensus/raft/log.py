"""
Raft replicated log, persistence interfaces, and state machine hooks.

### Maintainability guardrail: logic / side-effect firewall

Classes here define the **side-effect boundaries** the consensus core talks
to.  :class:`BaseStorage` and :class:`BaseStateMachine` are abstract so the
algorithm stays testable without real disks or networks.  The production
implementation lives in :mod:`salt.cluster.consensus.storage`.
"""

import json
import logging
from typing import NamedTuple

log = logging.getLogger(__name__)


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
        self.max_log_size = kwargs.get("max_log_size")
        self.commit_index = -1
        self.last_applied = -1

        if self.storage:
            self.entries = self.storage.load_log()
            snapshot = self.storage.load_snapshot()
            if snapshot:
                self.last_included_index = snapshot["index"]
                self.last_included_term = snapshot["term"]
                if self.state_machine:
                    self.state_machine.restore_snapshot(snapshot["data"])
            state = self.storage.load_state()
            self._term = state.get("term", 0)

        self._update_cached_index()

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
        """Compact the log by creating a snapshot of the state machine."""
        if not self.entries:
            return
        last_entry = self.entries[-1]
        self.last_included_index = last_entry.index
        self.last_included_term = last_entry.term

        if self.state_machine:
            data = self.state_machine.get_snapshot()
            if self.storage:
                self.storage.save_snapshot(
                    data, self.last_included_index, self.last_included_term
                )

        # Discard entries up to last_included_index
        self.entries = []
        self._update_cached_index()

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
