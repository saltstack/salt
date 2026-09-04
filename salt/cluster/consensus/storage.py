"""
SaltStorage — ``salt.cache``-backed persistence for the Raft node.

Implements :class:`salt.cluster.consensus.raft.BaseStorage` using the
``salt.cache.Cache`` abstraction so that whatever ``cache_driver`` the
operator has configured (``localfs`` today, ``mmapcache`` tomorrow) is used
automatically.

Bank layout::

    cluster/consensus/<node_id>/<ring_id>/        — state + snapshot
        state     — {"term": int, "voted_for": str|None}
        snapshot  — {"data": base64-str, "index": int, "term": int}

    cluster/consensus/<node_id>/<ring_id>/log/    — one cache key per log entry
        <index>   — LogEntry.info() tuple

The ``<ring_id>`` segment exists so multiple Raft groups can coexist
on the same master.  The default ``"cluster"`` value is the main
cluster Raft group; named rings (e.g. ``"jobs"``) get their own
sibling directory and run an independent Raft node out of one Salt
master process.

Per-entry log keys keep ``append_log`` O(1) on a backend whose store
primitive is O(1) (mmap_cache).  ``save_log`` (used for truncation and
recovery) flushes the log bank and re-writes each entry.
"""

import base64
import logging
import os
import threading

import salt.cache
import salt.syspaths
from salt.cluster.consensus.raft.log import BaseStorage, LogEntry, LogEntryType

log = logging.getLogger(__name__)

# Keys written into the meta bank (state + snapshot share one bank so a
# single ``flush`` of the meta bank wipes all metadata; the log lives in
# its own bank so we can flush it independently for truncation).
_KEY_STATE = "state"
_KEY_SNAPSHOT = "snapshot"


class SaltStorage(BaseStorage):
    """
    Raft persistence backed by ``salt.cache.Cache``.

    ``state`` and ``snapshot`` share the bank
    ``cluster/consensus/<node_id>``; log entries live in
    ``cluster/consensus/<node_id>/log`` with one cache key per entry,
    keyed by stringified Raft index.

    :param node_id: Raft node identifier (the master's interface address).
    :param opts:    Salt master opts dict — passed straight to
                    :class:`salt.cache.Cache`.
    :param ring_id: Identifier of the Raft group this storage belongs
                    to.  ``"cluster"`` (default) is the main cluster
                    Raft log; per-ring Raft groups pass their ring
                    name to isolate state on disk.
    """

    def __init__(self, node_id, opts, ring_id="cluster"):
        self._node_id = node_id
        self._ring_id = ring_id
        self._meta_bank = f"cluster/consensus/{node_id}/{ring_id}"
        self._log_bank = f"cluster/consensus/{node_id}/{ring_id}/log"
        self._cache = salt.cache.Cache(opts)
        # Retained so the localfs fsync helper can resolve the on-disk
        # path of each bank/key.  Cluster Raft consensus is correctness-
        # critical and infrequent, so we always fsync committed writes;
        # a knob would just invite a wrong setting.  See _fsync_bank_key.
        self._cachedir = opts.get("cachedir") or salt.syspaths.CACHE_DIR
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Durability helper
    # ------------------------------------------------------------------

    def _fsync_bank_key(self, bank, key):
        """
        Force the just-written ``cache.store(bank, key, ...)`` to disk.

        The cluster Raft log is correctness-critical (a voter that
        crashes after voting must not re-vote in the same term; an
        entry the leader has acked must survive a power loss).  Write
        volume is low, so we always fsync — there is no opt to flip.

        Currently only the ``localfs`` cache driver is supported here;
        other drivers fall through silently (their durability profile
        is up to the driver).  ``localfs`` writes
        ``<cachedir>/<bank>/<key>.p`` via temp-file + atomic rename, so
        we fsync the file (its data) and the parent directory (the
        rename's metadata).  Directory fsync is a no-op on Windows;
        the OSError is swallowed there.
        """
        if getattr(self._cache, "driver", None) != "localfs":
            return
        bank_dir = os.path.join(self._cachedir, *bank.split("/"))
        file_path = os.path.join(bank_dir, f"{key}.p")
        try:
            fd = os.open(file_path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            log.warning("SaltStorage: file fsync(%s) failed: %s", file_path, exc)
        try:
            dfd = os.open(bank_dir, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError as exc:
            # Directory fsync is unsupported on Windows; data fsync above
            # is the load-bearing call there.
            log.debug("SaltStorage: dir fsync(%s) skipped: %s", bank_dir, exc)

    # ------------------------------------------------------------------
    # BaseStorage implementation
    # ------------------------------------------------------------------

    def save_state(self, term, voted_for, leader_id=None):
        """
        Persist currentTerm and votedFor (Raft §5.2), plus the optional
        ``leader_id`` of the most recently observed leader for this term.

        ``leader_id`` is not required for Raft safety — it's an
        observability hint so a read-only consumer (``cluster.members``)
        can answer "who is the leader" without IPC into the publish
        daemon.  Stored alongside ``term`` so it can be interpreted
        relative to the most recent term.
        """
        with self._lock:
            payload = {"term": term, "voted_for": voted_for}
            if leader_id is not None:
                payload["leader_id"] = leader_id
            self._cache.store(self._meta_bank, _KEY_STATE, payload)
            self._fsync_bank_key(self._meta_bank, _KEY_STATE)

    def load_state(self):
        """Return persisted state, or defaults if not yet written."""
        with self._lock:
            data = self._cache.fetch(self._meta_bank, _KEY_STATE)
        if not data:
            return {"term": 0, "voted_for": None, "leader_id": None}
        # Older state records may not have leader_id; default to None.
        data.setdefault("leader_id", None)
        return data

    def save_log(self, entries):
        """
        Rewrite the entire log.

        Used by :class:`~salt.cluster.consensus.raft.log.Log` during
        truncation (conflict resolution) and after :meth:`Log.clear`.  We
        flush the log bank to drop any indices not in *entries* and then
        store each entry under its own key.
        """
        with self._lock:
            self._cache.flush(self._log_bank)
            for entry in entries:
                self._cache.store(self._log_bank, str(entry.index), entry.info())
                self._fsync_bank_key(self._log_bank, str(entry.index))

    def append_log(self, entry):
        """
        Append a single entry — O(1) on per-key backends.

        Stores under ``log_bank/<entry.index>`` so the hot append path
        does not read or rewrite any other entry.  Re-appending the same
        index (rare; only happens on a leader-side overwrite that does
        not also drive ``save_log``) is a benign overwrite.
        """
        with self._lock:
            self._cache.store(self._log_bank, str(entry.index), entry.info())
            self._fsync_bank_key(self._log_bank, str(entry.index))

    def load_log(self):
        """Return all persisted log entries as :class:`~.LogEntry` objects."""
        with self._lock:
            keys = self._cache.list(self._log_bank)
        if not keys:
            return []
        try:
            indices = sorted(int(k) for k in keys)
        except (TypeError, ValueError):
            log.warning(
                "SaltStorage: ignoring non-integer keys in %s: %r",
                self._log_bank,
                keys,
            )
            return []
        entries = []
        for idx in indices:
            with self._lock:
                raw = self._cache.fetch(self._log_bank, str(idx))
            if not raw:
                log.warning(
                    "SaltStorage: log entry %d missing from %s",
                    idx,
                    self._log_bank,
                )
                continue
            entry = self._decode_entry(raw)
            if entry is not None:
                entries.append(entry)
        return entries

    @staticmethod
    def _decode_entry(raw):
        """Reconstruct a :class:`LogEntry` from a cached ``info()`` payload."""
        if isinstance(raw, (list, tuple)):
            term = raw[0]
            idx = raw[1]
            cmd = raw[2]
            node_id = raw[3] if len(raw) > 3 else None
            entry_type = raw[4] if len(raw) > 4 else LogEntryType.COMMAND
            client_id = raw[5] if len(raw) > 5 else None
            sequence_num = raw[6] if len(raw) > 6 else None
            return LogEntry(
                term, idx, cmd, node_id, entry_type, client_id, sequence_num
            )
        if isinstance(raw, dict):
            return LogEntry(
                raw["term"],
                raw["index"],
                raw["cmd"],
                raw.get("node_id"),
                raw.get("type", LogEntryType.COMMAND),
                raw.get("client_id"),
                raw.get("sequence_num"),
            )
        return None

    def save_snapshot(self, data, index, term):
        """Persist a state-machine snapshot and its metadata."""
        if not isinstance(data, (bytes, memoryview)):
            import json  # pylint: disable=import-outside-toplevel

            data = json.dumps(data).encode("utf-8")
        encoded = base64.b64encode(bytes(data)).decode("utf-8")
        with self._lock:
            self._cache.store(
                self._meta_bank,
                _KEY_SNAPSHOT,
                {"data": encoded, "index": index, "term": term},
            )
            self._fsync_bank_key(self._meta_bank, _KEY_SNAPSHOT)

    def load_snapshot(self):
        """Return the latest snapshot dict, or ``None`` if none exists."""
        with self._lock:
            raw = self._cache.fetch(self._meta_bank, _KEY_SNAPSHOT)
        if not raw or "data" not in raw:
            return None
        raw = dict(raw)
        raw["data"] = base64.b64decode(raw["data"])
        return raw
