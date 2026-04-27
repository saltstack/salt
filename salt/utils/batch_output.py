"""
Output adapters for batch execution.

Each adapter is called after ``progress_batch()`` returns to report
what happened.  The adapter chosen depends on the execution mode:

- ``CLIOutput`` — prints to stdout (Phase 2: today's sync batch behavior).
- ``EventOutput`` — fires events on the master event bus (async mode,
  BatchManager).
- ``SilentOutput`` — no output; job cache only (programmatic use).

This module also owns the batch event tag vocabulary.  Nothing else
in the codebase should format a ``salt/batch/*`` tag by hand.
"""

import logging
import time

import salt.output
import salt.utils.stringutils

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event tag vocabulary.  Nothing else in the codebase should format a
# ``salt/batch/*`` tag by hand; go through the helpers below.
# ---------------------------------------------------------------------------

_BATCH_NEW = "salt/batch/{jid}/new"
_BATCH_PROGRESS = "salt/batch/{jid}/progress"
_BATCH_COMPLETE = "salt/batch/{jid}/complete"
_BATCH_HALTED = "salt/batch/{jid}/halted"
_BATCH_RECOVER = "salt/batch/{jid}/recover"


def tag_new(jid):
    """Tag fired when a new async batch is registered."""
    return _BATCH_NEW.format(jid=jid)


def tag_progress(jid):
    """Tag fired on each state change and on the idle heartbeat."""
    return _BATCH_PROGRESS.format(jid=jid)


def tag_complete(jid):
    """Tag fired when all minions are accounted for and no halt occurred."""
    return _BATCH_COMPLETE.format(jid=jid)


def tag_halted(jid):
    """Tag fired on abnormal termination (failhard / stop / corrupt / stale)."""
    return _BATCH_HALTED.format(jid=jid)


def tag_recover(jid):
    """Tag fired by Maintenance when a batch appears stale."""
    return _BATCH_RECOVER.format(jid=jid)


# ---------------------------------------------------------------------------
# Payload builders — keep event bodies consistent between drivers.
# ---------------------------------------------------------------------------


def _base_payload(state):
    """Fields present in every batch event."""
    return {
        "jid": state.get("jid"),
        "fun": state.get("fun"),
        "tgt": state.get("tgt"),
        "tgt_type": state.get("tgt_type"),
        "user": state.get("user"),
    }


def new_payload(state):
    """Payload for ``salt/batch/<jid>/new``."""
    payload = _base_payload(state)
    payload.update(
        {
            "total_minions": len(state.get("all_minions", [])),
            "batch_size": state.get("batch_size"),
            "driver": state.get("driver"),
            "created": state.get("created"),
        }
    )
    return payload


def progress_payload(state, iteration=None):
    """Payload for ``salt/batch/<jid>/progress``."""
    payload = _base_payload(state)
    payload.update(
        {
            "total": len(state.get("all_minions", [])),
            "completed": len(state.get("done", {})),
            "active": len(state.get("active", {})),
            "pending": len(state.get("pending", [])),
            "failed": len(state.get("failed", {})),
            "iter": iteration,
            "last_progress": state.get("last_progress"),
        }
    )
    return payload


def complete_payload(state, now=None):
    """Payload for ``salt/batch/<jid>/complete``."""
    if now is None:
        now = time.time()
    payload = _base_payload(state)
    payload.update(
        {
            "completed": len(state.get("done", {})),
            "failed": len(state.get("failed", {})),
            "total_minions": len(state.get("all_minions", [])),
            "duration": now - state.get("created", now),
        }
    )
    return payload


def halted_payload(state, now=None):
    """Payload for ``salt/batch/<jid>/halted``."""
    if now is None:
        now = time.time()
    payload = _base_payload(state)
    payload.update(
        {
            "reason": state.get("halted_reason"),
            "completed": len(state.get("done", {})),
            "failed": len(state.get("failed", {})),
            "abandoned_active": sorted(state.get("active", {}).keys()),
            "abandoned_pending": list(state.get("pending", [])),
            "duration": now - state.get("created", now),
        }
    )
    return payload


def recover_payload(state, age_seconds, now=None):
    """Payload for ``salt/batch/<jid>/recover``."""
    payload = _base_payload(state)
    payload.update(
        {
            "reason": "stale",
            "age_seconds": age_seconds,
            "driver": state.get("driver"),
        }
    )
    return payload


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class CLIOutput:
    """
    Print batch progress to stdout.

    Replaces the stdout formatting previously inlined in
    ``salt/cli/batch.py:Batch.run()``.  Every hook honors ``quiet``
    — if it's truthy nothing is printed.  The observable output of a
    batch run with the refactored ``Batch.run()`` is byte-identical
    to the pre-Phase-2 implementation.
    """

    def __init__(self, opts, quiet=False):
        self.opts = opts
        self.quiet = quiet

    def on_minion_down(self, minion_id, **kwargs):
        """Announce a minion that failed the initial ping."""
        if self.quiet:
            return
        salt.utils.stringutils.print_cli(
            f"Minion {minion_id} did not respond. No job will be sent."
        )

    def on_batch_start(self, minion_ids, **kwargs):
        """Announce the minion list for a new sub-batch."""
        if self.quiet:
            return
        salt.utils.stringutils.print_cli(f"\nExecuting run on {sorted(minion_ids)}\n")

    def on_minion_return(self, minion_id, data, **kwargs):
        """
        Render a minion return via ``salt.output.display_output``.

        ``data`` is the minion's return dict as produced by
        ``LocalClient.cmd_iter_no_block`` — ``{"ret": ..., "retcode": ..., ...}``.
        The display shape matches the legacy sync formatter: the
        ``ret`` key is re-mapped under the minion id and ``out`` (if
        present) selects the outputter.
        """
        if self.quiet:
            return
        reshaped = dict(data)
        if "ret" in reshaped:
            reshaped[minion_id] = reshaped.pop("ret")
        out = reshaped.pop("out", None)
        salt.output.display_output(reshaped, out, self.opts)

    def on_minion_failed(self, minion_id, **kwargs):
        """Announce a minion whose return carried ``failed: True``."""
        if self.quiet:
            return
        salt.utils.stringutils.print_cli(
            f"Minion '{minion_id}' failed to respond to job sent"
        )

    def on_minion_timeout(self, minion_id, **kwargs):
        """No-op in CLI mode: timeouts surface through empty returns."""

    def on_batch_done(self, state, **kwargs):
        """No-op in CLI mode: the caller prints summaries at top level."""


class EventOutput:
    """
    Fire events on the master event bus for batch progress.

    Used by the BatchManager process in async mode.  Individual minion
    returns already fire ``salt/job/<jid>/ret/<minion>`` via the normal
    return path; this adapter fires higher-level batch lifecycle events
    only.

    Callers are expected to hold a reference to a
    ``salt.utils.event.MasterEvent`` (or equivalent) and hand it in at
    construction time.
    """

    def __init__(self, opts, event):
        """
        :param dict opts: Salt opts dictionary.
        :param event: Master event bus handle with a
            ``fire_event(data, tag)`` method.
        """
        self.opts = opts
        self.event = event

    def on_batch_new(self, state):
        """Fire ``salt/batch/<jid>/new``."""
        self.event.fire_event(new_payload(state), tag_new(state["jid"]))

    def on_batch_progress(self, state, iteration=None):
        """Fire ``salt/batch/<jid>/progress``."""
        self.event.fire_event(
            progress_payload(state, iteration=iteration),
            tag_progress(state["jid"]),
        )

    def on_batch_complete(self, state, now=None):
        """Fire ``salt/batch/<jid>/complete``."""
        self.event.fire_event(
            complete_payload(state, now=now), tag_complete(state["jid"])
        )

    def on_batch_halted(self, state, now=None):
        """Fire ``salt/batch/<jid>/halted``."""
        self.event.fire_event(halted_payload(state, now=now), tag_halted(state["jid"]))

    def on_batch_recover(self, state, age_seconds, now=None):
        """Fire ``salt/batch/<jid>/recover`` from the Maintenance safety net."""
        self.event.fire_event(
            recover_payload(state, age_seconds, now=now),
            tag_recover(state["jid"]),
        )

    # Per-minion hooks — kept as no-ops so the same adapter shape works
    # for drivers that want to surface per-minion detail in the future.
    # Per-minion returns are already on the bus via salt/job/*/ret/*.

    def on_batch_start(self, minion_ids, **kwargs):
        """No-op in Phase 1 — sub-batch publishes already fire ``salt/job/<jid>/new``."""

    def on_minion_return(self, minion_id, data, **kwargs):
        """No-op; minion returns are already on the bus via salt/job/*."""

    def on_minion_timeout(self, minion_id, **kwargs):
        """No-op; timeout visibility lives in the progress payload."""

    def on_batch_done(self, state, now=None, **kwargs):
        """
        Dispatch to ``on_batch_complete`` or ``on_batch_halted`` based
        on ``state["halted"]``.  Convenience wrapper so drivers don't
        have to branch.
        """
        if state.get("halted"):
            self.on_batch_halted(state, now=now)
        else:
            self.on_batch_complete(state, now=now)


class SilentOutput:
    """
    No output.  Job cache only.

    Used for programmatic batch execution where the caller doesn't
    need real-time reporting.  Every hook is a no-op.
    """

    def on_batch_new(self, state, **kwargs):
        """No-op."""

    def on_batch_progress(self, state, **kwargs):
        """No-op."""

    def on_batch_complete(self, state, **kwargs):
        """No-op."""

    def on_batch_halted(self, state, **kwargs):
        """No-op."""

    def on_batch_recover(self, state, **kwargs):
        """No-op."""

    def on_batch_start(self, minion_ids, **kwargs):
        """No-op."""

    def on_minion_return(self, minion_id, data, **kwargs):
        """No-op."""

    def on_minion_timeout(self, minion_id, **kwargs):
        """No-op."""

    def on_batch_done(self, state, **kwargs):
        """No-op."""
