"""
Batch state machine for async and sync batch execution.

This module contains the core batch logic, decoupled from all I/O.
``BatchState`` is a plain dict describing the current state of a batch
job.  ``progress_batch()`` advances the state machine given a set of
new minion returns, and returns an ``Action`` describing what the
caller should do next (publish, report, halt).

No file access, no network calls, no event bus interaction.  Callers
(the sync CLI driver, the BatchManager process, and the Maintenance
safety net) are responsible for reading/writing state and performing
I/O based on the returned Action.
"""

import collections
import logging
import math
import os
import time

import salt.exceptions
import salt.payload
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.jid

log = logging.getLogger(__name__)

Action = collections.namedtuple(
    "Action",
    [
        "publish",  # list of minion IDs to publish to next (may be empty)
        "finished_minions",  # dict of {minion_id: return_data} just processed
        "timed_out_minions",  # list of minion IDs that were timed out
        "halted",  # bool — True if the batch is done or failhard triggered
        "halted_reason",  # str or None
    ],
)


# ---------------------------------------------------------------------------
# Batch-size parsing
# ---------------------------------------------------------------------------


def get_batch_size(batch_spec, num_minions):
    """
    Parse a batch specification and return the integer batch size.

    Handles both absolute (``"10"``) and percentage (``"25%"``)
    specifications.  Always returns at least 1 when there is at least
    one minion; returns 1 for an empty minion list so callers can
    treat the "size" as a scalar without zero-guarding everywhere.

    :param batch_spec: The ``--batch-size`` value, e.g. ``"10"`` or
        ``"25%"``.  Accepts ``int`` or ``str``.
    :param int num_minions: Total number of targeted minions.
    :returns: Number of minions per sub-batch.
    :rtype: int
    :raises salt.exceptions.SaltInvocationError: If ``batch_spec`` is
        malformed.
    """
    if num_minions < 0:
        num_minions = 0
    try:
        if isinstance(batch_spec, str) and "%" in batch_spec:
            percent = float(batch_spec.strip("%"))
            res = percent / 100.0 * num_minions
            if res < 1:
                return max(1, int(math.ceil(res)))
            return int(res)
        return max(1, int(batch_spec))
    except (ValueError, TypeError) as exc:
        raise salt.exceptions.SaltInvocationError(
            f"Invalid batch specification {batch_spec!r}: must be an integer "
            "or percentage string like '10' or '25%'."
        ) from exc


# ---------------------------------------------------------------------------
# State construction
# ---------------------------------------------------------------------------


def create_batch_state(opts, minions, jid, driver="cli", now=None):
    """
    Build an initial BatchState dict from opts and a resolved minion list.

    :param dict opts: Salt opts dictionary.  The following keys are
        read: ``fun``, ``arg``, ``kwargs``, ``tgt``, ``tgt_type``,
        ``batch``, ``failhard``, ``batch_wait``, ``timeout``,
        ``gather_job_timeout``, ``ret`` / ``return``, ``user``.
    :param list minions: Resolved list of minion IDs (after ping/targeting).
    :param str jid: The JID for the entire batch run.
    :param str driver: ``"cli"`` for sync CLI-driven batches,
        ``"master"`` for async BatchManager-driven batches.
    :param float now: Unix timestamp used to stamp ``created`` and
        ``last_progress``.  Defaults to ``time.time()``.
    :returns: A BatchState dict ready to be written to ``.batch.p``.
    :rtype: dict
    """
    if now is None:
        now = time.time()
    minions = list(minions)
    batch_size = get_batch_size(opts.get("batch"), len(minions))
    return {
        "jid": jid,
        "all_minions": list(minions),
        "pending": list(minions),
        "active": {},
        "done": {},
        "failed": {},
        "wait": [],
        "batch_size": batch_size,
        "fun": opts.get("fun", ""),
        "arg": list(opts.get("arg") or []),
        "kwargs": dict(opts.get("kwargs") or {}),
        "tgt": opts.get("tgt", ""),
        "tgt_type": opts.get("tgt_type", "glob"),
        "failhard": bool(opts.get("failhard", False)),
        "batch_wait": opts.get("batch_wait", 0) or 0,
        "timeout": opts.get("timeout", 60),
        "gather_job_timeout": opts.get("gather_job_timeout", 10),
        "last_progress": now,
        "created": now,
        "halted": False,
        "halted_reason": None,
        "driver": driver,
        "ret": opts.get("ret") or opts.get("return") or "",
        "user": opts.get("user", "root"),
    }


def is_batch_done(state):
    """
    Return True when the batch has concluded — either abnormally
    halted or fully drained (no pending, no active).

    Callers use this to decide when to fire ``salt/batch/<jid>/complete``
    (if not halted) or ``salt/batch/<jid>/halted`` (if halted).

    :param dict state: A BatchState dict.
    :rtype: bool
    """
    if state.get("halted"):
        return True
    return not state.get("pending") and not state.get("active")


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def _collapse_retcode(data):
    """
    Return the effective retcode for a minion return.

    Mirrors the sync-batch behavior in ``salt/cli/batch.py``:

    - Missing ``retcode`` → 0.
    - Integer ``retcode`` → itself.
    - Dict ``retcode`` → max of its values, or 0 if empty.
    """
    retcode = data.get("retcode", 0)
    if isinstance(retcode, dict):
        try:
            return max(retcode.values())
        except ValueError:
            return 0
    try:
        return int(retcode)
    except (TypeError, ValueError):
        return 0


def _is_failhard_trigger(data):
    """
    Return True if *data* should trip failhard.

    Two cases, both preserved from sync batch:

    - ``data["failed"] is True`` — minion failed to respond to the
      job (distinct from an ordinary non-zero retcode).
    - ``retcode > 0`` after dict-collapse.
    """
    if data.get("failed") is True:
        return True
    return _collapse_retcode(data) > 0


def progress_batch(state, new_returns=None, *, now=None, timed_out=None):
    """
    Advance the batch state machine.

    Mutates *state* in place and returns an ``Action`` describing what
    the caller should do next.

    Logic:

    1. Move returned minions from ``active`` to ``done`` (or ``failed``
       if the return has ``failed: True``).
    2. Check failhard — if any return has ``retcode > 0`` or
       ``failed: True`` and ``state["failhard"]`` is True, set
       ``state["halted"] = True`` and
       ``state["halted_reason"] = "failhard"``.
    3. Process driver-reported timeouts (``timed_out`` kwarg) — move
       each minion from ``active`` to ``failed`` with reason
       ``"timeout"``.  The sync driver uses this to surface timeouts
       detected externally by ``cmd_iter_no_block``'s own clock.
    4. Internal timeout sweep — move minions whose ``active`` dispatch
       time exceeds ``now - (timeout + gather_job_timeout)`` to
       ``failed`` with reason ``"timeout"``.  The async driver relies
       on this; the sync driver reports the same minions externally,
       so this is idempotent in practice.
    5. Prune expired entries from ``state["wait"]`` (entries with
       timestamp ``<= now``).
    6. If not halted, pop from ``pending`` up to
       ``batch_size - len(active) - len(wait)`` and include them in
       ``Action.publish``; record their dispatch timestamp in
       ``active``.
    7. Update ``last_progress`` to ``now``.
    8. Return the ``Action``.

    ``halted`` is set only for *abnormal* termination (failhard today;
    stop/corrupt/stale in future).  Normal completion is observed by
    the caller via ``is_batch_done(state)`` (pending empty, active
    empty, not halted).

    :param dict state: Current BatchState dict (mutated in place).
    :param dict new_returns: ``{minion_id: return_data}`` from minions
        that just completed.  May be ``None`` or empty (e.g. for a
        pure timeout-check or batch_wait-expiry tick).
    :param float now: Unix timestamp used for timeout and batch_wait
        calculations.  Defaults to ``time.time()``.  Exposed so tests
        and recovery code can supply a deterministic clock.
    :param timed_out: Iterable of minion IDs the driver has detected
        as non-responsive externally (e.g. by exhausting a
        ``cmd_iter_no_block`` iterator).  Each is moved from ``active``
        to ``failed`` with reason ``"timeout"``; the corresponding
        ``batch_wait`` cooldown entry is appended.  Timeouts do not
        trigger failhard.
    :returns: An ``Action`` namedtuple.
    :rtype: Action
    """
    if now is None:
        now = time.time()
    new_returns = new_returns or {}

    bwait = state.get("batch_wait", 0) or 0
    finished_minions = {}
    timed_out_minions = []
    failhard_triggered = False

    # ---- 1/2. Process incoming returns ---------------------------------
    for minion_id, data in new_returns.items():
        if minion_id in state["done"] or minion_id in state["failed"]:
            log.debug(
                "Ignoring duplicate return for %s in batch %s",
                minion_id,
                state.get("jid"),
            )
            continue
        # Remove from active (idempotent; absent minion just means the
        # driver surfaced a late/unexpected return — still record it).
        state["active"].pop(minion_id, None)

        if data.get("failed") is True:
            state["failed"][minion_id] = "failed"
        else:
            state["done"][minion_id] = data
        finished_minions[minion_id] = data

        if bwait:
            state["wait"].append(now + bwait)

        if state.get("failhard") and _is_failhard_trigger(data):
            failhard_triggered = True

    # ---- 3. Driver-reported timeouts -----------------------------------
    if timed_out:
        for minion_id in timed_out:
            if minion_id in state["done"] or minion_id in state["failed"]:
                continue
            state["active"].pop(minion_id, None)
            state["failed"][minion_id] = "timeout"
            timed_out_minions.append(minion_id)
            if bwait:
                state["wait"].append(now + bwait)

    # ---- 4. Internal timeout sweep -------------------------------------
    timeout_window = state.get("timeout", 60) + state.get("gather_job_timeout", 10)
    for minion_id, dispatch_ts in list(state["active"].items()):
        if now - dispatch_ts >= timeout_window:
            del state["active"][minion_id]
            state["failed"][minion_id] = "timeout"
            timed_out_minions.append(minion_id)
            if bwait:
                state["wait"].append(now + bwait)

    # ---- 4. Prune expired wait stamps ----------------------------------
    if state["wait"]:
        state["wait"] = sorted(ts for ts in state["wait"] if ts > now)

    # ---- Failhard halt -------------------------------------------------
    if failhard_triggered:
        state["halted"] = True
        state["halted_reason"] = "failhard"

    # ---- 5. Dispatch next sub-batch ------------------------------------
    publish = []
    if not state["halted"]:
        free_slots = state["batch_size"] - len(state["active"]) - len(state["wait"])
        while free_slots > 0 and state["pending"]:
            minion_id = state["pending"].pop(0)
            state["active"][minion_id] = now
            publish.append(minion_id)
            free_slots -= 1

    # ---- 6. Housekeeping -----------------------------------------------
    state["last_progress"] = now

    return Action(
        publish=publish,
        finished_minions=finished_minions,
        timed_out_minions=timed_out_minions,
        halted=state["halted"],
        halted_reason=state["halted_reason"],
    )


# ---------------------------------------------------------------------------
# Persistence — ``.batch.p`` inside the JID directory
# ---------------------------------------------------------------------------


def _jid_dir(jid, opts):
    return salt.utils.jid.jid_dir(
        jid,
        os.path.join(opts["cachedir"], "jobs"),
        opts.get("hash_type", "sha256"),
    )


def _batch_state_path(jid, opts):
    return os.path.join(_jid_dir(jid, opts), ".batch.p")


def _active_index_path(opts):
    return os.path.join(opts["cachedir"], "batch_active.p")


def write_batch_state(jid, state, opts, *, best_effort=False):
    """
    Atomically write a BatchState dict to ``.batch.p`` in the JID
    directory.

    Uses ``salt.utils.atomicfile.atomic_open()`` so readers never see
    partial data.

    :param str jid: The batch JID.
    :param dict state: The BatchState dict to serialize.
    :param dict opts: Salt opts (needed for ``cachedir``, ``hash_type``).
    :param bool best_effort: If True, log and return ``False`` on any
        error (missing ``cachedir``, filesystem errors) instead of
        raising.  Used by the sync CLI driver so persistence failures
        don't break in-memory execution.
    :returns: ``True`` on successful write, ``False`` if ``best_effort``
        was set and the write failed.
    :rtype: bool
    """
    try:
        path = _batch_state_path(jid, opts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = salt.payload.dumps(state)
        with salt.utils.atomicfile.atomic_open(path, "wb") as fp:
            fp.write(payload)
        return True
    except Exception:  # pylint: disable=broad-except
        if not best_effort:
            raise
        log.debug("best-effort write_batch_state for %s failed", jid, exc_info=True)
        return False


def read_batch_state(jid, opts):
    """
    Read a BatchState dict from ``.batch.p`` in the JID directory.

    :param str jid: The batch JID.
    :param dict opts: Salt opts (needed for ``cachedir``, ``hash_type``).
    :returns: The BatchState dict, or ``None`` if the file doesn't
        exist or is corrupt.
    :rtype: dict or None
    """
    path = _batch_state_path(jid, opts)
    if not os.path.exists(path):
        return None
    try:
        with salt.utils.files.fopen(path, "rb") as fp:
            data = fp.read()
        if not data:
            return None
        return salt.payload.loads(data)
    except Exception:  # pylint: disable=broad-except
        # Corrupt .batch.p — callers treat None as "not recoverable."
        # Maintenance is expected to eventually clean these up.
        log.exception("Failed to read batch state from %s", path)
        return None


def write_active_index(jids, opts):
    """
    Atomically write the set of active batch JIDs to
    ``<cachedir>/batch_active.p``.

    :param set jids: Set of JID strings.
    :param dict opts: Salt opts (needed for ``cachedir``).
    """
    path = _active_index_path(opts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = salt.payload.dumps(sorted(jids))
    with salt.utils.atomicfile.atomic_open(path, "wb") as fp:
        fp.write(payload)


def read_active_index(opts):
    """
    Read the set of active batch JIDs from ``<cachedir>/batch_active.p``.

    :param dict opts: Salt opts (needed for ``cachedir``).
    :returns: Set of JID strings, or empty set if file is missing/corrupt.
    :rtype: set
    """
    path = _active_index_path(opts)
    if not os.path.exists(path):
        return set()
    try:
        with salt.utils.files.fopen(path, "rb") as fp:
            data = fp.read()
        if not data:
            return set()
        jids = salt.payload.loads(data)
        return set(jids)
    except Exception:  # pylint: disable=broad-except
        log.exception("Failed to read active batch index from %s", path)
        return set()


def add_to_active_index(jid, opts, *, best_effort=False):
    """
    Add a JID to the active batch index file.

    Reads the current index, adds *jid*, and writes it back atomically.

    This is a read-modify-write; in normal operation BatchManager is
    the single writer so the race window is irrelevant.  Maintenance
    recovery is the only other writer, and it tolerates transient
    inconsistency (it'll converge on the next pass).

    :param str jid: The batch JID to add.
    :param dict opts: Salt opts (needed for ``cachedir``).
    :param bool best_effort: If True, swallow errors and return
        ``False`` instead of raising.
    :returns: ``True`` on success, ``False`` on best-effort failure.
    :rtype: bool
    """
    try:
        jids = read_active_index(opts)
        jids.add(jid)
        write_active_index(jids, opts)
        return True
    except Exception:  # pylint: disable=broad-except
        if not best_effort:
            raise
        log.debug("best-effort add_to_active_index for %s failed", jid, exc_info=True)
        return False


def remove_from_active_index(jid, opts, *, best_effort=False):
    """
    Remove a JID from the active batch index file.

    Reads the current index, removes *jid*, and writes it back
    atomically.  No-op if *jid* is not in the index.

    :param str jid: The batch JID to remove.
    :param dict opts: Salt opts (needed for ``cachedir``).
    :param bool best_effort: If True, swallow errors and return
        ``False`` instead of raising.
    :returns: ``True`` on success, ``False`` on best-effort failure.
    :rtype: bool
    """
    try:
        jids = read_active_index(opts)
        jids.discard(jid)
        write_active_index(jids, opts)
        return True
    except Exception:  # pylint: disable=broad-except
        if not best_effort:
            raise
        log.debug(
            "best-effort remove_from_active_index for %s failed", jid, exc_info=True
        )
        return False
