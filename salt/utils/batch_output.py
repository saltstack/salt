"""
Output adapters for batch execution.

Each adapter is called after ``progress_batch()`` returns to report
what happened.  The adapter chosen depends on the execution mode:

- ``CLIOutput`` — prints to stdout (today's sync batch behavior).
- ``EventOutput`` — fires events on the master event bus (async mode,
  BatchManager).
- ``SilentOutput`` — no output; job cache only (programmatic use).
"""

import logging

log = logging.getLogger(__name__)


class CLIOutput:
    """
    Print batch progress to stdout.

    This reproduces the output behavior of today's ``Batch.run()``
    using ``salt.output.display_output()`` and
    ``salt.utils.stringutils.print_cli()``.
    """

    def __init__(self, opts):
        """
        :param dict opts: Salt opts dictionary (needed for output
            format selection).
        """
        self.opts = opts

    def on_batch_start(self, minion_ids):
        """
        Called when a new sub-batch is dispatched.

        Prints "Executing run on [minion1, minion2, ...]" to stdout.

        :param list minion_ids: Minion IDs in this sub-batch.
        """

    def on_minion_return(self, minion_id, data):
        """
        Called when a minion returns data.

        Formats and prints the return data using
        ``salt.output.display_output()``.

        :param str minion_id: The minion that returned.
        :param dict data: The return data (contains ``ret``, ``out``,
            ``retcode``, etc.).
        """

    def on_minion_timeout(self, minion_id):
        """
        Called when a minion is timed out without responding.

        Prints a message indicating the minion did not respond.

        :param str minion_id: The unresponsive minion.
        """

    def on_batch_done(self, state):
        """
        Called when the batch is complete (all minions done or halted).

        For CLI output this is typically a no-op — the CLI just exits.

        :param dict state: The final BatchState.
        """


class EventOutput:
    """
    Fire events on the master event bus for batch progress.

    Used by the BatchManager process in async mode.  Individual minion
    returns already fire ``salt/job/<jid>/ret/<minion>`` via the normal
    return path; this adapter fires higher-level batch lifecycle events.
    """

    def __init__(self, opts, event):
        """
        :param dict opts: Salt opts dictionary.
        :param salt.utils.event.SaltEvent event: Master event bus handle.
        """
        self.opts = opts
        self.event = event

    def on_batch_start(self, minion_ids, jid=None, iteration=None):
        """
        Fire ``salt/batch/<jid>/iter/<n>`` when a sub-batch is dispatched.

        :param list minion_ids: Minion IDs in this sub-batch.
        :param str jid: The batch JID.
        :param int iteration: The sub-batch iteration number.
        """

    def on_minion_return(self, minion_id, data):
        """
        Optionally fire a batch-progress event.

        Individual returns are already on the bus via the normal path.
        This could fire a ``salt/batch/<jid>/progress`` summary event
        periodically.

        :param str minion_id: The minion that returned.
        :param dict data: The return data.
        """

    def on_minion_timeout(self, minion_id, jid=None):
        """
        Fire an event indicating a minion timed out within a batch.

        :param str minion_id: The unresponsive minion.
        :param str jid: The batch JID.
        """

    def on_batch_done(self, state, jid=None):
        """
        Fire ``salt/batch/<jid>/done`` when the batch is complete.

        :param dict state: The final BatchState.
        :param str jid: The batch JID.
        """


class SilentOutput:
    """
    No output.  Job cache only.

    Used for programmatic batch execution where the caller doesn't
    need real-time output.
    """

    def on_batch_start(self, minion_ids, **kwargs):
        """No-op."""

    def on_minion_return(self, minion_id, data, **kwargs):
        """No-op."""

    def on_minion_timeout(self, minion_id, **kwargs):
        """No-op."""

    def on_batch_done(self, state, **kwargs):
        """No-op."""
