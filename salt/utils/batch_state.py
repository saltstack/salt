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


def create_batch_state(
    opts,
    minions,
    jid,
    driver="cli",
):
    """
    Build an initial BatchState dict from opts and a resolved minion list.

    :param dict opts: Salt opts dictionary.  The following keys are read:
        ``fun``, ``arg``, ``kwargs``, ``tgt``, ``tgt_type``, ``batch``,
        ``failhard``, ``batch_wait``, ``timeout``, ``gather_job_timeout``,
        ``return``/``ret``, ``eauth``.
    :param list minions: Resolved list of minion IDs (after ping/targeting).
    :param str jid: The JID for the entire batch run.
    :param str driver: ``"cli"`` for sync CLI-driven batches,
        ``"master"`` for async BatchManager-driven batches.
    :returns: A BatchState dict ready to be written to ``.batch.p``.
    :rtype: dict
    """


def progress_batch(state, new_returns):
    """
    Advance the batch state machine.

    Mutates *state* in place and returns an ``Action`` describing what
    the caller should do next.

    Logic:

    1. Move returned minions from ``active`` to ``done`` (or ``failed``).
    2. Check failhard — if any return has ``retcode > 0`` and
       ``failhard is True``, set ``halted = True``.
    3. Check timeouts — move minions whose ``active`` dispatch time
       exceeds ``timeout + gather_job_timeout`` to ``failed``.
    4. If not halted and ``active`` slots are available, pop from
       ``pending`` up to ``batch_size - len(active)``, respecting
       ``batch_wait`` (timestamp-based, no sleeping).
    5. Update ``last_progress`` timestamp.
    6. If ``pending`` is empty and ``active`` is empty, the batch is
       complete — set ``halted = True``.
    7. Return the ``Action``.

    :param dict state: Current BatchState dict (mutated in place).
    :param dict new_returns: ``{minion_id: return_data}`` from minions
        that just completed.  May be empty (e.g. timeout-check call).
    :returns: An ``Action`` namedtuple.
    :rtype: Action
    """


def get_batch_size(batch_spec, num_minions):
    """
    Parse a batch specification and return the integer batch size.

    Handles both absolute (``"10"``) and percentage (``"25%"``)
    specifications.  Always returns at least 1.

    :param str batch_spec: The ``--batch-size`` value, e.g. ``"10"``
        or ``"25%"``.
    :param int num_minions: Total number of targeted minions.
    :returns: Number of minions per sub-batch.
    :rtype: int
    """


def write_batch_state(jid, state, opts):
    """
    Atomically write a BatchState dict to ``.batch.p`` in the JID
    directory.

    Uses ``salt.utils.atomicfile.atomic_open()`` so readers never see
    partial data.

    :param str jid: The batch JID.
    :param dict state: The BatchState dict to serialize.
    :param dict opts: Salt opts (needed for ``cachedir``, ``hash_type``).
    """


def read_batch_state(jid, opts):
    """
    Read a BatchState dict from ``.batch.p`` in the JID directory.

    :param str jid: The batch JID.
    :param dict opts: Salt opts (needed for ``cachedir``, ``hash_type``).
    :returns: The BatchState dict, or ``None`` if the file doesn't
        exist or is corrupt.
    :rtype: dict or None
    """


def write_active_index(jids, opts):
    """
    Atomically write the set of active batch JIDs to
    ``<cachedir>/batch_active.p``.

    :param set jids: Set of JID strings.
    :param dict opts: Salt opts (needed for ``cachedir``).
    """


def read_active_index(opts):
    """
    Read the set of active batch JIDs from ``<cachedir>/batch_active.p``.

    :param dict opts: Salt opts (needed for ``cachedir``).
    :returns: Set of JID strings, or empty set if file is missing/corrupt.
    :rtype: set
    """


def add_to_active_index(jid, opts):
    """
    Add a JID to the active batch index file.

    Reads the current index, adds *jid*, and writes it back atomically.

    :param str jid: The batch JID to add.
    :param dict opts: Salt opts (needed for ``cachedir``).
    """


def remove_from_active_index(jid, opts):
    """
    Remove a JID from the active batch index file.

    Reads the current index, removes *jid*, and writes it back
    atomically.  No-op if *jid* is not in the index.

    :param str jid: The batch JID to remove.
    :param dict opts: Salt opts (needed for ``cachedir``).
    """
