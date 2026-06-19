"""
Execute batch runs.

The sync CLI driver (``Batch``) is a thin shell around the shared
state machine in :mod:`salt.utils.batch_state` and the CLI output
adapter in :mod:`salt.utils.batch_output`.  The state machine owns
slot accounting, failhard, timeout, and ``batch_wait`` — the driver
only manages the iterator plumbing that turns master-side
``cmd_iter_no_block`` polling into ``new_returns`` inputs and
``timed_out`` signals.

The observable behavior (yield shape, stdout formatting, JID reuse,
failhard early-exit, ``batch_wait`` dispatch delay) is preserved
byte-for-byte against the pre-refactor implementation.  The async
``BatchManager`` uses the same state machine, so both drivers are
guaranteed to produce the same sequence of minion transitions given
the same inputs.
"""

import copy
import logging
import math
import time

import salt.client
import salt.exceptions
import salt.output
import salt.utils.batch_output
import salt.utils.batch_state
import salt.utils.jid
import salt.utils.stringutils

log = logging.getLogger(__name__)


class Batch:
    """
    Manage the execution of batch runs.
    """

    def __init__(self, opts, eauth=None, quiet=False, _parser=None):
        """
        :param dict opts: A config options dictionary.

        :param dict eauth: An eauth config to use.

                           The default is an empty dict.

        :param bool quiet: Suppress printing to stdout

                           The default is False.
        """
        self.opts = opts
        self.eauth = eauth if eauth else {}
        self.pub_kwargs = eauth if eauth else {}
        self.quiet = quiet
        self.options = _parser
        # Passing listen True to local client will prevent it from purging
        # cached events while iterating over the batches.
        self.local = salt.client.get_local_client(opts["conf_file"], listen=True)

    def gather_minions(self):
        """
        Return a list of minions to use for the batch run.
        """
        args = [
            self.opts["tgt"],
            "test.ping",
            [],
            self.opts["timeout"],
        ]

        selected_target_option = self.opts.get("selected_target_option", None)
        if selected_target_option is not None:
            args.append(selected_target_option)
        else:
            args.append(self.opts.get("tgt_type", "glob"))

        self.pub_kwargs["yield_pub_data"] = True
        ping_gen = self.local.cmd_iter(
            *args,
            gather_job_timeout=self.opts["gather_job_timeout"],
            **self.pub_kwargs,
        )

        fret = set()
        nret = set()
        for ret in ping_gen:
            if ("minions" and "jid") in ret:
                for minion in ret["minions"]:
                    nret.add(minion)
                continue
            else:
                try:
                    m = next(iter(ret.keys()))
                except StopIteration:
                    if not self.quiet:
                        salt.utils.stringutils.print_cli(
                            "No minions matched the target."
                        )
                    break
                if m is not None:
                    if "failed" in ret[m] and ret[m]["failed"] is True:
                        log.debug(
                            "minion '%s' failed test.ping - will be returned as a down minion",
                            m,
                        )
                    else:
                        fret.add(m)

        return (list(fret), ping_gen, nret.difference(fret))

    def get_bnum(self):
        """
        Return the active number of minions to maintain.

        Preserves the legacy return values (``None`` for invalid
        input, ``0`` for an empty minion list with a percentage spec,
        ``0`` for ``batch=0``) for backward compatibility with any
        callers that rely on them.  The shared state machine uses the
        hardened :func:`salt.utils.batch_state.get_batch_size` which
        always returns at least 1.
        """

        def partition(x):
            return float(x) / 100.0 * len(self.minions)

        try:
            if isinstance(self.opts["batch"], str) and "%" in self.opts["batch"]:
                res = partition(float(self.opts["batch"].strip("%")))
                if res < 1:
                    return int(math.ceil(res))
                return int(res)
            return int(self.opts["batch"])
        except ValueError:
            if not self.quiet:
                salt.utils.stringutils.print_cli(
                    "Invalid batch data sent: {}\nData must be in the "
                    "form of %10, 10% or 3".format(self.opts["batch"])
                )

    def run(self):
        """
        Execute the batch run.

        Generator.  For each minion return, yields
        ``({minion_id: ret_data}, retcode)`` (or the raw event envelope
        when ``raw=True``).  Minion returns carrying ``failed: True``
        (and ``failhard`` halt events) are recorded internally but not
        yielded, preserving the pre-Phase-2 yield shape.
        """
        self.minions, self.ping_gen, self.down_minions = self.gather_minions()

        if not self.minions:
            return

        batch_jid = salt.utils.jid.gen_jid(self.opts)
        state = salt.utils.batch_state.create_batch_state(
            self.opts, self.minions, batch_jid, driver="cli"
        )

        # The sync CLI driver does not write under the master's
        # ``cachedir`` itself.  ``cachedir`` is owned by the master
        # daemon's user (typically ``salt``); the CLI is normally
        # invoked as ``root``, so any direct write would pre-create
        # the JID directory with the wrong ownership and trip a
        # ``PermissionError`` in ``local_cache.prep_jid`` when the
        # master tries to write the ``jid`` file (issue #69418).
        #
        # Instead, we ship every state change to the master-side
        # ``BatchManager`` via ``salt/batch/<jid>/{new,progress,
        # complete,halted}`` events.  The manager — already running
        # as the master daemon's user — persists ``.batch.p`` and
        # maintains the active-batch index on the CLI's behalf.
        # ``batch.status`` / ``batch.list_active`` / ``batch.stop``
        # see sync batches because of that handoff.  All event ops
        # are best-effort: if the master event bus is unreachable
        # the CLI batch still completes correctly with no visibility.
        self._fire_event(
            salt.utils.batch_output.state_payload(state),
            salt.utils.batch_output.tag_new(batch_jid),
        )
        self._subscribe_to_halt(batch_jid)

        output = salt.utils.batch_output.CLIOutput(self.opts, quiet=self.quiet)
        for down_minion in self.down_minions:
            output.on_minion_down(down_minion)

        if self.options:
            show_jid = self.options.show_jid
            show_verbose = self.options.verbose
        else:
            show_jid = False
            show_verbose = False

        return_value = self.opts.get("return", self.opts.get("ret", ""))
        raw_mode = bool(self.opts.get("raw"))

        iters = []
        minion_tracker = {}  # iter -> {"minions": [...], "active": bool}
        # We retain the raw return objects (event envelopes in raw mode,
        # minion-return dicts otherwise) separately from the normalized
        # data fed to the state machine so display_output and the yield
        # shape can be reconstructed after progress_batch() has moved
        # the minion out of ``active``.
        raw_by_minion = {}

        try:
            while not salt.utils.batch_state.is_batch_done(state):
                new_returns, timed_out = self._poll_iterators(
                    iters, minion_tracker, raw_mode, raw_by_minion
                )
                self._discover_late_minions(state)

                # Observe halt requests from the master-side
                # ``batch.stop`` runner before deciding what to do
                # this tick.  The runner fires ``salt/batch/<jid>/
                # stop`` which the BatchManager translates into
                # ``salt/batch/<jid>/halted``; we subscribed to the
                # halted tag during startup.
                if self._consume_halt_event(batch_jid, state):
                    # progress_batch already short-circuits on a
                    # halted state, but we still want to fall
                    # through the existing failhard reporting path.
                    pass

                now = time.time()
                action = salt.utils.batch_state.progress_batch(
                    state, new_returns, now=now, timed_out=timed_out
                )

                if (
                    action.publish
                    or action.finished_minions
                    or action.timed_out_minions
                    or state["halted"]
                ):
                    self._fire_event(
                        salt.utils.batch_output.state_payload(state),
                        salt.utils.batch_output.tag_progress(batch_jid),
                    )

                if action.publish:
                    output.on_batch_start(action.publish)
                    args = [
                        list(action.publish),
                        self.opts["fun"],
                        self.opts["arg"],
                        self.opts["timeout"],
                        "list",
                    ]
                    new_iter = self.local.cmd_iter_no_block(
                        *args,
                        raw=raw_mode,
                        ret=return_value,
                        show_jid=show_jid,
                        verbose=show_verbose,
                        gather_job_timeout=self.opts["gather_job_timeout"],
                        jid=batch_jid,
                        **self.eauth,
                    )
                    iters.append(new_iter)
                    minion_tracker[new_iter] = {
                        "minions": list(action.publish),
                        "active": True,
                    }

                halted_mid_yield = False
                for minion_id, data in new_returns.items():
                    if data.get("failed") is True:
                        output.on_minion_failed(minion_id)
                    else:
                        retcode = salt.utils.batch_state._collapse_retcode(data)
                        if raw_mode:
                            yield raw_by_minion.get(minion_id, data), retcode
                        else:
                            yield {minion_id: data.get("ret")}, retcode
                        output.on_minion_return(
                            minion_id, raw_by_minion.get(minion_id, data)
                        )
                    if state["halted"]:
                        halted_mid_yield = True
                        break

                if halted_mid_yield:
                    log.error(
                        "Batch run stopped due to failhard",
                    )
                    break

                for minion_id in timed_out:
                    envelope = raw_by_minion.get(minion_id)
                    if raw_mode and envelope is not None:
                        yield envelope, 0
                    elif raw_mode:
                        yield {"data": {"id": minion_id, "return": {}, "retcode": 0}}, 0
                    else:
                        yield {minion_id: {}}, 0
                    output.on_minion_timeout(minion_id)

                # Prune finished iterators; progress_batch already
                # cleared their minions from state["active"].
                iters = [
                    queue
                    for queue in iters
                    if minion_tracker.get(queue, {}).get("active")
                ]

                # When neither a dispatch nor a poll happened, idle
                # briefly so we don't hot-spin waiting for batch_wait
                # to expire.
                if (
                    not action.publish
                    and not iters
                    and not new_returns
                    and not timed_out
                ):
                    if not salt.utils.batch_state.is_batch_done(state):
                        time.sleep(0.02)

            output.on_batch_done(state)
        finally:
            terminal_tag = (
                salt.utils.batch_output.tag_halted(batch_jid)
                if state.get("halted")
                else salt.utils.batch_output.tag_complete(batch_jid)
            )
            self._fire_event(
                salt.utils.batch_output.state_payload(state),
                terminal_tag,
            )
            self._unsubscribe_from_halt(batch_jid)
            # Tear the event handle down explicitly **before**
            # ``LocalClient.destroy``.  The new visibility code lazily
            # creates a ``SyncWrapper(ipc_publish_server)`` (and its
            # nested ``SyncWrapper(PubServerClient)``) the first time
            # we ``fire_event``; each wrapper owns its own asyncio
            # loop.  ``LocalClient.destroy`` will close them, but
            # leaving that to the implicit teardown means the
            # asyncio cleanup races interpreter shutdown — on Python
            # 3.14 / Windows that race drops post-``shutdown_asyncgens``
            # Handles from ``_ready`` before they're awaited and
            # spills ``RuntimeWarning: coroutine ... was never awaited``
            # onto the CLI's stderr.  Calling ``event.destroy`` here
            # (while we still control the loop) plus a deterministic
            # drain quiesces those warnings at the source.
            self._teardown_event_handle()
            self.local.destroy()

    def _poll_iterators(self, iters, minion_tracker, raw_mode, raw_by_minion):
        """
        Drain every active ``cmd_iter_no_block`` iterator once.

        Returns ``(new_returns, timed_out)`` — a dict of normalized
        minion returns and a list of minion IDs the iterator exhausted
        without yielding (i.e. ``cmd_iter_no_block``'s own timeout
        tripped).  ``raw_by_minion`` is populated with the raw
        payloads so the caller can preserve yield shape.

        Iterators that raise ``StopIteration`` are marked inactive in
        ``minion_tracker`` but not removed from ``iters`` — the caller
        filters them after the state-machine step so yields happen in
        iterator order.
        """
        new_returns = {}
        timed_out = []
        for queue in list(iters):
            try:
                ncnt = 0
                while True:
                    part = next(queue)
                    if part is None:
                        time.sleep(0.01)
                        ncnt += 1
                        if ncnt > 5:
                            break
                        continue
                    if raw_mode:
                        minion_id = part["data"]["id"]
                        raw_by_minion[minion_id] = part
                        new_returns[minion_id] = {
                            "ret": part["data"].get("return"),
                            "retcode": part["data"].get("retcode", 0),
                            "failed": part["data"].get("failed", False),
                        }
                        if minion_id in minion_tracker[queue]["minions"]:
                            minion_tracker[queue]["minions"].remove(minion_id)
                        else:
                            if not self.quiet:
                                salt.utils.stringutils.print_cli(
                                    "minion {} was already deleted from tracker,"
                                    " probably a duplicate key".format(minion_id)
                                )
                    else:
                        for minion_id, mret in part.items():
                            raw_by_minion[minion_id] = copy.copy(mret)
                            new_returns[minion_id] = mret
                            if minion_id in minion_tracker[queue]["minions"]:
                                minion_tracker[queue]["minions"].remove(minion_id)
                            else:
                                if not self.quiet:
                                    salt.utils.stringutils.print_cli(
                                        "minion {} was already deleted from tracker,"
                                        " probably a duplicate key".format(minion_id)
                                    )
            except StopIteration:
                if queue in minion_tracker:
                    minion_tracker[queue]["active"] = False
                    for minion_id in minion_tracker[queue]["minions"]:
                        if minion_id not in new_returns:
                            timed_out.append(minion_id)
        return new_returns, timed_out

    def _discover_late_minions(self, state):
        """
        Pull newly discovered minions off ``ping_gen`` and append them
        to ``state["pending"]`` so the state machine will schedule
        them.
        """
        for ping_ret in self.ping_gen:
            if ping_ret is None:
                break
            try:
                minion_id = next(iter(ping_ret.keys()))
            except StopIteration:
                break
            if minion_id not in state["all_minions"]:
                state["all_minions"].append(minion_id)
                state["pending"].append(minion_id)
                if minion_id not in self.minions:
                    self.minions.append(minion_id)

    # ------------------------------------------------------------------
    # Event-bus glue — best-effort visibility for ``batch.status`` /
    # ``batch.list_active`` / ``batch.stop``.  Every method here
    # swallows its own errors so a broken or absent event bus never
    # blocks the run; the worst case is "no visibility into the
    # batch from master-side runners," same as on 3007.x.
    # ------------------------------------------------------------------

    def _event(self):
        """Return the master event handle attached to our LocalClient."""
        return getattr(self.local, "event", None)

    def _fire_event(self, payload, tag):
        """Fire a batch lifecycle event; never raise."""
        event = self._event()
        if event is None:
            return
        try:
            event.fire_event(payload, tag)
        except Exception:  # pylint: disable=broad-except
            log.debug("Failed to fire %s; continuing without it", tag, exc_info=True)

    def _subscribe_to_halt(self, jid):
        """Subscribe to ``salt/batch/<jid>/halted`` so we observe stops."""
        event = self._event()
        if event is None:
            return
        try:
            event.subscribe(
                salt.utils.batch_output.tag_halted(jid), match_type="startswith"
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "Failed to subscribe to halted tag for %s; "
                "batch.stop will not be observable from this CLI",
                jid,
                exc_info=True,
            )

    def _unsubscribe_from_halt(self, jid):
        """Counterpart to ``_subscribe_to_halt``."""
        event = self._event()
        if event is None:
            return
        try:
            event.unsubscribe(
                salt.utils.batch_output.tag_halted(jid), match_type="startswith"
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "Failed to unsubscribe from halted tag for %s", jid, exc_info=True
            )

    def _teardown_event_handle(self):
        """
        Destroy the LocalClient's event handle in-place.

        Safe to call on a half-initialized or already-destroyed
        client.  Any failure is swallowed: the worst case is that
        ``LocalClient.destroy`` cleans up instead, and the
        Python 3.14 / Windows teardown warning resurfaces — never
        a functional regression.

        After ``event.destroy``, both wrappers' asyncio loops have
        been closed; a follow-on ``LocalClient.destroy`` call is a
        no-op (``SaltEvent.destroy`` is idempotent — it only acts
        when ``subscriber`` / ``pusher`` are still set).
        """
        local = getattr(self, "local", None)
        if local is None:
            return
        event = getattr(local, "event", None)
        if event is None:
            return
        try:
            event.destroy()
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "Failed to tear down event handle cleanly; deferring "
                "to LocalClient.destroy",
                exc_info=True,
            )

    def _consume_halt_event(self, jid, state):
        """
        Non-blocking poll for ``salt/batch/<jid>/halted``.

        Returns ``True`` when a halt event was observed (and mutates
        *state* in place to record it); ``False`` otherwise.  Spurious
        bus failures degrade silently to ``False``.
        """
        event = self._event()
        if event is None:
            return False
        try:
            payload = event.get_event(
                wait=0,
                tag=salt.utils.batch_output.tag_halted(jid),
                match_type="startswith",
                no_block=True,
            )
        except Exception:  # pylint: disable=broad-except
            log.debug("Failed to poll halted tag for %s", jid, exc_info=True)
            return False
        if not isinstance(payload, dict):
            return False
        if payload.get("jid") != jid:
            # Stray event (or a mock returning truthy garbage in
            # tests).  Ignore — only an explicit match counts.
            return False
        state["halted"] = True
        state["halted_reason"] = payload.get("reason") or "stop"
        return True
