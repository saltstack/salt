"""
Runner module for managing and inspecting async batch jobs.

Provides commands for checking batch status, listing active batches,
and stopping running batch jobs.

.. code-block:: bash

    # Check status of an async batch job
    salt-run batch.status 20240610120000000000

    # List all active async batch jobs
    salt-run batch.list_active

    # Stop a running async batch job (graceful drain)
    salt-run batch.stop 20240610120000000000

    # Stop and kill in-flight minions too
    salt-run batch.stop 20240610120000000000 kill=True
"""

import logging
import time

import salt.client
import salt.utils.batch_output
import salt.utils.batch_state
import salt.utils.event

log = logging.getLogger(__name__)


__virtualname__ = "batch"


def status(jid):
    """
    Return the current status of an async batch job.

    Reads ``.batch.p`` from the job cache for the given JID and returns
    a summary dict.  Returns ``None`` if the JID does not exist or has
    no ``.batch.p`` (e.g. it was never an async batch, or the cache was
    cleaned).

    :param str jid: The batch JID to query.
    :returns: Summary dict or ``None``.
    :rtype: dict or None

    CLI Example:

    .. code-block:: bash

        salt-run batch.status 20240610120000000000
    """
    state = salt.utils.batch_state.read_batch_state(jid, __opts__)
    if state is None:
        return None
    return _summary(state)


def list_active():
    """
    Return a list of all active (non-halted) async batch jobs.

    Reads ``<cachedir>/batch_active.p`` and returns one summary dict
    per batch.  Entries whose ``.batch.p`` is missing or unreadable
    are silently dropped — Maintenance converges the index on its
    next pass.

    :returns: List of batch summary dicts.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt-run batch.list_active
    """
    jids = salt.utils.batch_state.read_active_index(__opts__)
    result = []
    for jid in sorted(jids):
        state = salt.utils.batch_state.read_batch_state(jid, __opts__)
        if state is None:
            continue
        result.append(_summary(state))
    return result


def stop(jid, kill=False):
    """
    Stop a running async batch job.

    Default (``kill=False``) is a graceful drain: halts further
    sub-batch publishes but leaves in-flight minion jobs running.
    Their returns are still recorded in the job cache via the normal
    ``salt/job/*/ret/*`` path.

    With ``kill=True``, also publishes ``saltutil.kill_job`` targeted
    at the batch's currently-active minions before firing the halt
    event.  Safe on minions that have already finished (no-op there).

    Returns ``False`` if the JID is unknown or already halted.

    :param str jid: The batch JID to stop.
    :param bool kill: When ``True``, also terminate in-flight minion
        jobs via ``saltutil.kill_job``.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt-run batch.stop 20240610120000000000
        salt-run batch.stop 20240610120000000000 kill=True
    """
    state = salt.utils.batch_state.read_batch_state(jid, __opts__)
    if state is None:
        log.warning("batch.stop: no batch state found for jid %s", jid)
        return False
    if state.get("halted"):
        log.info("batch.stop: batch %s is already halted", jid)
        return False

    reason = "stop"

    if kill and state.get("active"):
        _kill_active_minions(state)

    # Ask the BatchManager to finalize via its event-driven path; it
    # is the single writer for .batch.p on happy paths.  The manager
    # will perform the atomic halt write, fire salt/batch/<jid>/halted,
    # and retire the JID from the active index.
    with salt.utils.event.get_master_event(
        __opts__, __opts__["sock_dir"], listen=False
    ) as event:
        event.fire_event(
            {"jid": jid, "reason": reason},
            f"salt/batch/{jid}/stop",
        )

    return True


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _summary(state):
    """
    Build the user-facing summary dict for a :func:`status` /
    :func:`list_active` response.

    Deliberately a flat mapping — easy to consume from
    ``salt-run --out=json`` and stable across minor version changes.
    """
    return {
        "jid": state.get("jid"),
        "fun": state.get("fun"),
        "tgt": state.get("tgt"),
        "tgt_type": state.get("tgt_type"),
        "total": len(state.get("all_minions", [])),
        "completed": len(state.get("done", {})),
        "active": len(state.get("active", {})),
        "pending": len(state.get("pending", [])),
        "failed": len(state.get("failed", {})),
        "batch_size": state.get("batch_size"),
        "halted": bool(state.get("halted")),
        "halted_reason": state.get("halted_reason"),
        "driver": state.get("driver"),
        "user": state.get("user"),
        "created": state.get("created"),
        "last_progress": state.get("last_progress"),
        "age_seconds": (
            time.time() - state["last_progress"] if state.get("last_progress") else None
        ),
    }


def _kill_active_minions(state):
    """
    Publish ``saltutil.kill_job`` at the batch's in-flight minions.

    Composes the existing per-minion kill primitive — no new
    cancellation plumbing.  See
    ``salt/modules/saltutil.py:kill_job``.
    """
    minion_ids = sorted(state.get("active", {}).keys())
    if not minion_ids:
        return
    log.info(
        "batch.stop kill=True: publishing saltutil.kill_job on %d minion(s) for batch %s",
        len(minion_ids),
        state.get("jid"),
    )
    with salt.client.get_local_client(__opts__["conf_file"], listen=False) as local:
        try:
            local.cmd_async(
                list(minion_ids),
                "saltutil.kill_job",
                arg=[state["jid"]],
                tgt_type="list",
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "batch.stop kill=True failed to publish saltutil.kill_job for %s",
                state.get("jid"),
            )
