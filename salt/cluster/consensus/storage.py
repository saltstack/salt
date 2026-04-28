"""
SaltStorage — ``salt.cache``-backed persistence for the Raft node.

Implements :class:`salt.cluster.consensus.raft.BaseStorage` using the
``salt.cache.Cache`` abstraction so that whatever ``cache_driver`` the
operator has configured (``localfs`` today, ``mmapcache`` tomorrow) is used
automatically.

Bank layout under ``cluster/consensus/<node_id>/``::

    state     — {"term": int, "voted_for": str|None}
    log       — [LogEntry.info() tuple, ...]
    snapshot  — {"data": base64-str, "index": int, "term": int}
"""

import base64
import logging
import threading

import salt.cache
from salt.cluster.consensus.raft.log import BaseStorage, LogEntry, LogEntryType

log = logging.getLogger(__name__)

# Keys written into the cache bank.
_KEY_STATE = "state"
_KEY_LOG = "log"
_KEY_SNAPSHOT = "snapshot"


class SaltStorage(BaseStorage):
    """
    Raft persistence backed by ``salt.cache.Cache``.

    All three durable documents (state, log, snapshot) are stored in the
    bank ``cluster/consensus/<node_id>`` so they share the operator's
    configured ``cache_driver`` and are co-located with other cluster data.

    :param node_id: Raft node identifier (the master's interface address).
    :param opts:    Salt master opts dict — passed straight to
                    :class:`salt.cache.Cache`.
    """

    def __init__(self, node_id, opts):
        self._bank = f"cluster/consensus/{node_id}"
        self._cache = salt.cache.Cache(opts)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # BaseStorage implementation
    # ------------------------------------------------------------------

    def save_state(self, term, voted_for):
        """Persist currentTerm and votedFor (Raft §5.2)."""
        with self._lock:
            self._cache.store(
                self._bank, _KEY_STATE, {"term": term, "voted_for": voted_for}
            )

    def load_state(self):
        """Return persisted state, or defaults if not yet written."""
        with self._lock:
            data = self._cache.fetch(self._bank, _KEY_STATE)
        if not data:
            return {"term": 0, "voted_for": None}
        return data

    def save_log(self, entries):
        """Rewrite the entire log (used during truncation and recovery)."""
        with self._lock:
            self._cache.store(self._bank, _KEY_LOG, [e.info() for e in entries])

    def append_log(self, entry):
        """
        Append a single entry.

        ``salt.cache`` has no efficient append primitive, so we do a
        read-modify-write under the lock.  For the membership-only log that
        Salt consensus tracks this is fine; the log stays small.
        """
        with self._lock:
            raw = self._cache.fetch(self._bank, _KEY_LOG)
            existing = raw if isinstance(raw, list) else []
            existing.append(entry.info())
            self._cache.store(self._bank, _KEY_LOG, existing)

    def load_log(self):
        """Return all persisted log entries as :class:`~.LogEntry` objects."""
        with self._lock:
            raw = self._cache.fetch(self._bank, _KEY_LOG)
        if not raw or not isinstance(raw, list):
            return []
        entries = []
        for e in raw:
            if isinstance(e, (list, tuple)):
                term = e[0]
                idx = e[1]
                cmd = e[2]
                node_id = e[3] if len(e) > 3 else None
                entry_type = e[4] if len(e) > 4 else LogEntryType.COMMAND
                client_id = e[5] if len(e) > 5 else None
                sequence_num = e[6] if len(e) > 6 else None
                entries.append(
                    LogEntry(
                        term, idx, cmd, node_id, entry_type, client_id, sequence_num
                    )
                )
            else:
                # dict format (defensive — cache backends may return dicts)
                entries.append(
                    LogEntry(
                        e["term"],
                        e["index"],
                        e["cmd"],
                        e.get("node_id"),
                        e.get("type", LogEntryType.COMMAND),
                        e.get("client_id"),
                        e.get("sequence_num"),
                    )
                )
        return entries

    def save_snapshot(self, data, index, term):
        """Persist a state-machine snapshot and its metadata."""
        if not isinstance(data, (bytes, memoryview)):
            import json  # pylint: disable=import-outside-toplevel

            data = json.dumps(data).encode("utf-8")
        encoded = base64.b64encode(bytes(data)).decode("utf-8")
        with self._lock:
            self._cache.store(
                self._bank,
                _KEY_SNAPSHOT,
                {"data": encoded, "index": index, "term": term},
            )

    def load_snapshot(self):
        """Return the latest snapshot dict, or ``None`` if none exists."""
        with self._lock:
            raw = self._cache.fetch(self._bank, _KEY_SNAPSHOT)
        if not raw or "data" not in raw:
            return None
        raw = dict(raw)
        raw["data"] = base64.b64decode(raw["data"])
        return raw
