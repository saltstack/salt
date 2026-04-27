"""
BatchManager — the master-side driver for async batch jobs.

A ``SignalHandlingProcess`` started by the master's
``ProcessManager`` alongside ``Maintenance``, the Reactor engine, and
the rest of the master process tree.  Idles on ``get_event(wait=...)``
when no async batches are active; wakes on minion returns for adopted
batch JIDs and on ``salt/batch/*`` lifecycle events.

Layering:

- :mod:`salt.utils.batch_state` owns the pure state machine.
- :mod:`salt.utils.batch_output` owns the event tag vocabulary and
  payload shapes.
- This module composes them with Salt's event bus and ``LocalClient``.

The class is deliberately driven by small public-ish methods
(``_handle_event``, ``_progress_one``, ``_tick``, ``_handle_new``,
``_handle_stop``, ``_handle_recover``) so unit tests can step through
a scenario without a real master or multiprocessing fork.
"""

import logging
import re
import time

import salt.client
import salt.utils.batch_output
import salt.utils.batch_state
import salt.utils.event
import salt.utils.process

log = logging.getLogger(__name__)


_BATCH_LIFECYCLE_TAG = re.compile(r"^salt/batch/([^/]+)/(new|stop|recover)$")
_JOB_RETURN_TAG = re.compile(r"^salt/job/([^/]+)/ret/([^/]+)$")

DEFAULT_LOOP_INTERVAL = 5


class BatchManager(salt.utils.process.SignalHandlingProcess):
    """
    Master-side driver for async batch jobs.

    Listens for:

    - ``salt/job/<jid>/ret/<minion>`` — minion returns for active batches.
    - ``salt/batch/<jid>/new`` — new async batch registration from the CLI.
    - ``salt/batch/<jid>/stop`` — manual batch stop request from the
      ``batch.stop`` runner.
    - ``salt/batch/<jid>/recover`` — recovery request from the
      Maintenance safety net.

    On each relevant event, reads ``BatchState`` from ``.batch.p``,
    calls :func:`salt.utils.batch_state.progress_batch` to advance the
    state machine, publishes the next sub-batch if needed, writes the
    updated state back, and fires lifecycle events via the
    :class:`salt.utils.batch_output.EventOutput` adapter.

    Maintains an in-memory ``set`` of active batch JIDs so non-batch
    return events can be filtered with a single dict lookup — zero
    disk I/O on the hot path.
    """

    def __init__(self, opts, **kwargs):
        """
        :param dict opts: The salt master options dictionary.
        """
        super().__init__(**kwargs)
        self.opts = opts
        # Populated in _post_fork_init():
        self.event = None
        self.local = None
        self.output = None
        self.active_batches = set()

    # ------------------------------------------------------------------
    # Lifecycle — forked-process initialization and main loop
    # ------------------------------------------------------------------

    def _post_fork_init(self):
        """
        Initialize resources that must be created after the fork.

        Opens the master event bus with ``listen=True``, instantiates a
        ``LocalClient`` for sub-batch publishes, loads the active-batch
        index from disk, and builds the ``EventOutput`` adapter.
        """
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=True
        )
        self.local = salt.client.get_local_client(
            self.opts.get("conf_file"), listen=False
        )
        self.active_batches = salt.utils.batch_state.read_active_index(self.opts)
        self.output = salt.utils.batch_output.EventOutput(self.opts, self.event)
        log.info(
            "BatchManager initialized with %d active batch(es) in the index",
            len(self.active_batches),
        )

    def run(self):
        """
        Main event loop.

        Blocks on ``get_event(wait=N)`` with N set by
        ``batch_manager_loop_interval`` (default 5s).  On every
        iteration — whether or not an event arrived — runs a housekeeping
        ``_tick()`` pass so timeout detection and batch_wait expiry
        progress even when the bus is quiet.
        """
        self._post_fork_init()
        loop_interval = self.opts.get(
            "batch_manager_loop_interval", DEFAULT_LOOP_INTERVAL
        )
        while True:
            try:
                event = self.event.get_event(
                    wait=loop_interval, full=True, no_block=False
                )
            except Exception:  # pylint: disable=broad-except
                log.exception("BatchManager failed to read from the event bus")
                event = None

            if event is not None:
                try:
                    self._handle_event(event)
                except Exception:  # pylint: disable=broad-except
                    log.exception(
                        "BatchManager failed to handle event %r", event.get("tag")
                    )
            try:
                self._tick()
            except Exception:  # pylint: disable=broad-except
                log.exception("BatchManager housekeeping tick failed")

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def _handle_event(self, event):
        """
        Dispatch an event from the master bus to the right handler.

        :param dict event: Event dict with ``tag`` and ``data`` keys,
            as produced by ``SaltEvent.get_event(full=True)``.
        """
        tag = event.get("tag", "") if isinstance(event, dict) else ""
        data = event.get("data", {}) if isinstance(event, dict) else {}

        lifecycle = _BATCH_LIFECYCLE_TAG.match(tag)
        if lifecycle:
            jid, action = lifecycle.group(1), lifecycle.group(2)
            if action == "new":
                self._handle_new(jid)
            elif action == "stop":
                self._handle_stop(jid, data)
            elif action == "recover":
                self._handle_recover(jid)
            return

        ret = _JOB_RETURN_TAG.match(tag)
        if ret:
            jid, minion_id = ret.group(1), ret.group(2)
            if jid in self.active_batches:
                self._handle_batch_return(jid, minion_id, data)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_new(self, jid):
        """
        Adopt a new async batch.

        The CLI writes ``.batch.p`` before firing ``salt/batch/<jid>/new``,
        so this handler reads the on-disk state to confirm and registers
        the JID in the in-memory active set.  Sync batches
        (``driver="cli"``) are ignored.
        """
        if jid in self.active_batches:
            return
        state = salt.utils.batch_state.read_batch_state(jid, self.opts)
        if state is None:
            log.warning("salt/batch/%s/new received but .batch.p is not readable", jid)
            return
        if state.get("driver") != "master":
            log.debug(
                "Ignoring salt/batch/%s/new — driver=%s is not master-driven",
                jid,
                state.get("driver"),
            )
            return
        self._adopt(jid)
        log.info("Adopted async batch %s on behalf of %s", jid, state.get("user"))

    def _handle_stop(self, jid, data):
        """
        Halt an active batch gracefully.

        Sets ``halted=True`` / ``halted_reason="stop"`` (or the reason
        carried in *data*) and fires ``salt/batch/<jid>/halted``.  The
        runner is responsible for the ``kill=True`` variant — that path
        publishes ``saltutil.kill_job`` against active minions *before*
        emitting ``salt/batch/<jid>/stop``.
        """
        state = salt.utils.batch_state.read_batch_state(jid, self.opts)
        if state is None:
            self._retire(jid)
            return
        if state.get("halted"):
            self._retire(jid)
            return
        state["halted"] = True
        state["halted_reason"] = data.get("reason") or "stop"
        state["last_progress"] = time.time()
        salt.utils.batch_state.write_batch_state(jid, state, self.opts)
        if self.output is not None:
            self.output.on_batch_halted(state)
        self._retire(jid)

    def _handle_recover(self, jid):
        """
        Re-adopt a batch that the Maintenance safety net flagged as stale.

        Reads the state from disk (since we may have crashed since it
        was last in-memory), adds it back to the active set, and forces
        a progress tick so any free slots dispatch immediately.
        """
        state = salt.utils.batch_state.read_batch_state(jid, self.opts)
        if state is None:
            self._retire(jid)
            return
        if state.get("halted"):
            self._retire(jid)
            return
        if state.get("driver") != "master":
            return
        self._adopt(jid)
        self._progress_one(jid, {})

    def _handle_batch_return(self, jid, minion_id, data):
        """
        Process a minion return event for an active batch.

        Translates the ``salt/job/<jid>/ret/<minion>`` event payload to
        the ``{minion: return_data}`` shape the state machine expects,
        then delegates to :meth:`_progress_one`.
        """
        self._progress_one(jid, {minion_id: _event_to_return(data)})

    # ------------------------------------------------------------------
    # Progress core — one step through the state machine for a given JID
    # ------------------------------------------------------------------

    def _progress_one(self, jid, new_returns, now=None):
        """
        Read ``.batch.p``, advance the state machine, persist the
        result, publish any new sub-batch, and fire progress events.
        """
        state = salt.utils.batch_state.read_batch_state(jid, self.opts)
        if state is None:
            log.warning(
                "Batch %s has no readable .batch.p; retiring from active set",
                jid,
            )
            self._retire(jid)
            return
        if state.get("halted"):
            self._retire(jid)
            return

        action = salt.utils.batch_state.progress_batch(state, new_returns, now=now)

        if action.publish:
            self._publish_sub_batch(state, action.publish)

        salt.utils.batch_state.write_batch_state(jid, state, self.opts)

        if action.publish or action.finished_minions or action.timed_out_minions:
            if self.output is not None:
                self.output.on_batch_progress(state)

        if salt.utils.batch_state.is_batch_done(state):
            if self.output is not None:
                self.output.on_batch_done(state)
            self._retire(jid)

    def _tick(self, now=None):
        """
        Housekeeping pass over every active batch.

        Three things happen, in order:

        1. Reconcile the in-memory active set with the on-disk index.
           Batches registered by other processes (the CLI at
           batch-creation time, the ``batch.stop`` runner, a previously
           crashed manager) can be adopted without requiring an
           event.  This closes the race where a ``salt/batch/<jid>/new``
           event is lost before we're listening.
        2. Advance each active batch by one tick — drives timeout
           detection and ``batch_wait`` expiry when no return events
           are arriving.
        3. ``_progress_one`` retires JIDs that are halted or missing
           from disk.
        """
        on_disk = salt.utils.batch_state.read_active_index(self.opts)
        for jid in on_disk - self.active_batches:
            log.info(
                "BatchManager adopting batch %s discovered via active index",
                jid,
            )
            self.active_batches.add(jid)
        for jid in list(self.active_batches):
            self._progress_one(jid, {}, now=now)

    # ------------------------------------------------------------------
    # Side effects
    # ------------------------------------------------------------------

    def _publish_sub_batch(self, state, minion_ids):
        """
        Publish the next sub-batch via ``LocalClient.run_job``.

        ``jid`` is forced to the batch JID so every sub-batch publish
        accumulates under the same job directory (the single-JID
        foundation from PR #68941).  ``user`` is carried from
        ``BatchState`` so publisher-ACL enforcement and audit still
        attribute the publish to the original operator.
        """
        log.info(
            "Dispatching sub-batch of %d minion(s) for batch %s on behalf of %s",
            len(minion_ids),
            state.get("jid"),
            state.get("user"),
        )
        if self.local is None:
            log.error(
                "BatchManager has no LocalClient; cannot publish sub-batch for %s",
                state.get("jid"),
            )
            return
        try:
            self.local.run_job(
                tgt=list(minion_ids),
                fun=state["fun"],
                arg=list(state.get("arg") or []),
                tgt_type="list",
                ret=state.get("ret") or "",
                timeout=state.get("timeout", 60),
                jid=state["jid"],
                kwarg=dict(state.get("kwargs") or {}),
                listen=False,
                user=state.get("user", "root"),
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("Failed to publish sub-batch for %s", state.get("jid"))

    # ------------------------------------------------------------------
    # Active-set management
    # ------------------------------------------------------------------

    def _adopt(self, jid):
        """Add *jid* to the active set and persist the index."""
        self.active_batches.add(jid)
        salt.utils.batch_state.add_to_active_index(jid, self.opts)

    def _retire(self, jid):
        """Remove *jid* from the active set and persist the index."""
        self.active_batches.discard(jid)
        salt.utils.batch_state.remove_from_active_index(jid, self.opts)


# ---------------------------------------------------------------------------
# Event → return-payload translation
# ---------------------------------------------------------------------------


def _event_to_return(event_data):
    """
    Map a ``salt/job/<jid>/ret/<minion>`` event payload to the dict
    shape that :func:`salt.utils.batch_state.progress_batch` expects
    (identical to sync batch's ``parts[minion]``).

    The return-event schema uses ``return`` for the payload; the state
    machine follows sync batch and calls the key ``ret``.  ``retcode``
    is passed through unchanged (the state machine handles dict vs int
    collapse internally).
    """
    if not isinstance(event_data, dict):
        return {"ret": event_data, "retcode": 0}
    return {
        "ret": event_data.get("return"),
        "retcode": event_data.get("retcode", 0),
    }
