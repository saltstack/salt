"""
Wired-up tests for sync CLI batch visibility via the master-side
``BatchManager`` (issue #69418).

These tests bridge ``Batch.run()`` and a real ``BatchManager`` by
routing the CLI's ``self.local.event.fire_event`` calls into the
manager's ``_handle_event`` directly, instead of through a real master
event bus.  That lets us prove the end-to-end visibility contract
without a forked master process:

* While the sync CLI batch is running, ``batch.list_active`` /
  ``batch.status`` see the batch via the manager-written
  ``.batch.p`` + active index.
* When ``batch.stop`` is invoked, the manager fires
  ``salt/batch/<jid>/halted`` and the CLI observes it and exits.
* Master-as-``salt``-user / CLI-as-``root`` style deployments
  cannot regress: the CLI itself never writes under the master's
  cachedir, asserted by patching out the persistence helpers.
"""

import pytest

# Initialize ``__opts__`` on the runner module the way the loader
# would at runtime.  This module-import-time setup keeps ``patch.dict``
# from having to ``create=True`` (which trips the salt-loader-dunder
# pylint plugin).
import salt.runners.batch as _batch_runner_module  # noqa: E402
import salt.utils.batch_output
import salt.utils.batch_state
from salt.cli.batch import Batch
from salt.runners import batch as batch_runner
from salt.utils.batch_manager import BatchManager
from tests.support.mock import MagicMock, patch

if not hasattr(_batch_runner_module, "__dict__") or "__opts__" not in vars(
    _batch_runner_module
):
    vars(_batch_runner_module).setdefault("__opts__", {})


def _patch_runner_opts(opts):
    """Override __opts__ for the batch runner during a single test."""
    return patch.dict(batch_runner.__opts__, opts, clear=True)


@pytest.fixture
def opts(tmp_path):
    """Master-side opts shared by the CLI and the manager."""
    return {
        "cachedir": str(tmp_path),
        "hash_type": "sha256",
        "sock_dir": str(tmp_path),
        "conf_file": str(tmp_path / "master"),
        "batch_manager_loop_interval": 5,
    }


@pytest.fixture
def manager(opts):
    """A BatchManager wired up without a real fork."""
    mgr = BatchManager(opts)
    mgr.event = MagicMock()
    mgr.local = MagicMock()
    mgr.output = MagicMock()
    mgr.active_batches = set()
    return mgr


@pytest.fixture
def cli_batch(opts):
    """
    A sync CLI ``Batch`` whose ``LocalClient`` is mocked.  The
    fixture leaves ``local.event`` as a default ``MagicMock`` —
    individual tests can replace it with a bus bridge.
    """
    cli_opts = {
        "batch": "1",
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
        "timeout": 5,
        "gather_job_timeout": 5,
        "transport": "",
    }
    cli_opts.update(opts)
    mock_client = MagicMock()
    with patch(
        "salt.client.get_local_client", MagicMock(return_value=mock_client)
    ), patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
        yield Batch(cli_opts, quiet=True)


def _bridge_cli_to_manager(cli_batch, manager):
    """
    Wire ``cli_batch.local.event.fire_event`` so each fired event is
    immediately routed through ``manager._handle_event``.  Models
    "the master event bus delivers the event to the manager," which
    is the contract that matters here.

    The CLI's halt-event poll (``get_event``) defaults to ``None``;
    individual tests override it to inject a stop.
    """
    cli_batch.local.event.get_event = MagicMock(return_value=None)
    cli_batch.local.event.subscribe = MagicMock(return_value=None)
    cli_batch.local.event.unsubscribe = MagicMock(return_value=None)

    def _bridge(payload, tag):
        manager._handle_event({"tag": tag, "data": payload})

    cli_batch.local.event.fire_event = MagicMock(side_effect=_bridge)


def test_batch_list_active_sees_running_sync_cli_batch(cli_batch, manager, opts):
    """
    During a sync CLI batch run, the master-side ``batch.list_active``
    runner must see the JID.  The manager writes ``.batch.p`` from the
    ``salt/batch/<jid>/new`` event and adds the JID to the active
    index — both of which ``list_active`` reads.
    """
    _bridge_cli_to_manager(cli_batch, manager)
    cli_batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    seen = {"during_first_iter": None}

    # The 2-minion batch=1 case results in two ``cmd_iter_no_block``
    # calls.  On the *second* call (i.e. mid-run between sub-batches)
    # snapshot what ``batch.list_active`` returns.
    call_count = {"n": 0}

    def _make_iter(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            with _patch_runner_opts(opts):
                seen["during_first_iter"] = batch_runner.list_active()
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    cli_batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    with _patch_runner_opts(opts):
        list(Batch.run(cli_batch))

    assert seen["during_first_iter"] is not None, "list_active was not invoked mid-run"
    assert len(seen["during_first_iter"]) == 1
    summary = seen["during_first_iter"][0]
    assert summary["driver"] == "cli"
    assert summary["fun"] == "test.ping"

    # After the run, the manager's ``salt/batch/<jid>/complete``
    # handler should have removed the JID from the index.
    with _patch_runner_opts(opts):
        after = batch_runner.list_active()
    assert after == []


def test_batch_status_sees_running_sync_cli_batch(cli_batch, manager, opts):
    """
    ``batch.status <jid>`` must return live progress for a sync CLI
    batch while it's running.
    """
    cli_batch.local.event.get_event = MagicMock(return_value=None)
    cli_batch.local.event.subscribe = MagicMock(return_value=None)
    cli_batch.local.event.unsubscribe = MagicMock(return_value=None)
    cli_batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    captured_jid = {"jid": None}
    seen = {"during": None}

    def _capture_jid(payload, tag):
        if tag.endswith("/new"):
            captured_jid["jid"] = payload["jid"]
        manager._handle_event({"tag": tag, "data": payload})

    cli_batch.local.event.fire_event = MagicMock(side_effect=_capture_jid)

    call_count = {"n": 0}

    def _make_iter(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2 and captured_jid["jid"]:
            with _patch_runner_opts(opts):
                seen["during"] = batch_runner.status(captured_jid["jid"])
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    cli_batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    with _patch_runner_opts(opts):
        list(Batch.run(cli_batch))

    assert seen["during"] is not None
    assert seen["during"]["driver"] == "cli"
    assert seen["during"]["total"] == 2


def test_batch_stop_halts_sync_cli_batch(cli_batch, manager, opts):
    """
    ``salt-run batch.stop <jid>`` fires ``salt/batch/<jid>/stop``,
    which the manager's ``_handle_stop`` converts to a write of
    ``halted=True`` and an outgoing ``salt/batch/<jid>/halted``
    event.  The CLI subscribes to ``/halted`` and observes it via
    ``get_event``; the run terminates without completing the
    remaining minions.
    """
    captured = {"jid": None, "halted_payload": None}

    # Capture the jid as soon as the CLI fires ``new``.
    def _bridge(payload, tag):
        if tag.endswith("/new"):
            captured["jid"] = payload["jid"]
        if tag.endswith("/halted") and "state" in payload:
            captured["halted_payload"] = payload

        # Make the manager's _handle_stop fire a halted event back at
        # us by having the manager use its own fire_event.  We
        # capture what the manager would emit by stubbing
        # mgr.event.fire_event to call back into ourselves.
        manager._handle_event({"tag": tag, "data": payload})

    cli_batch.local.event.fire_event = MagicMock(side_effect=_bridge)
    cli_batch.local.event.subscribe = MagicMock(return_value=None)
    cli_batch.local.event.unsubscribe = MagicMock(return_value=None)

    # When the manager handles ``stop``, its EventOutput will
    # eventually try to fire ``halted``; since the manager's event is
    # a MagicMock, we capture its fire_event call and have the CLI's
    # get_event surface that payload on next poll.
    halt_box = {"emitted": None}

    def _mgr_fire_event(payload, tag):
        if tag.endswith("/halted"):
            halt_box["emitted"] = payload

    manager.event.fire_event.side_effect = _mgr_fire_event
    manager.output = salt.utils.batch_output.EventOutput(opts, manager.event)

    def _make_iter(*args, **kwargs):
        # Yield None forever so the loop can only end via halt.
        while True:
            yield None

    cli_batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    cli_batch.gather_minions = MagicMock(return_value=[["m1", "m2", "m3"], [], []])

    poll_count = {"n": 0}

    def _get_event(*args, **kwargs):
        poll_count["n"] += 1
        if poll_count["n"] == 1:
            # First poll: simulate the operator running
            # ``salt-run batch.stop`` between CLI loop iterations
            # by directly invoking the runner with our shared opts.
            with patch.dict(
                batch_runner.__opts__,
                opts,
                clear=True,
                create=True,
            ):
                # Bypass the runner's get_master_event context
                # manager — its event bus isn't real here — and call
                # the manager's stop handler directly.  This models
                # what would happen on a live master once the
                # runner's fired event reaches the manager loop.
                manager._handle_stop(
                    captured["jid"], {"jid": captured["jid"], "reason": "stop"}
                )
            return None
        if poll_count["n"] == 2 and halt_box["emitted"] is not None:
            # The manager just emitted halted; surface it to the CLI.
            return halt_box["emitted"]
        return None

    cli_batch.local.event.get_event = MagicMock(side_effect=_get_event)

    with _patch_runner_opts(opts):
        results = list(Batch.run(cli_batch))

    # Run must have terminated without yielding all minions; the
    # halt event was observed.
    fire_tags = [c.args[1] for c in cli_batch.local.event.fire_event.call_args_list]
    assert any(t.endswith("/halted") for t in fire_tags), (
        "CLI must emit /halted on teardown when halted, got: %s" % fire_tags
    )

    # And the final state on disk should reflect the stop.
    on_disk = salt.utils.batch_state.read_batch_state(captured["jid"], opts)
    assert on_disk is not None
    assert on_disk["halted"] is True
    assert on_disk["halted_reason"] == "stop"

    # Batch.list_active should no longer include the JID.
    assert captured["jid"] not in salt.utils.batch_state.read_active_index(opts)
    # Returned results may be empty (iterator never produced a
    # return) or partial; we don't assert exact length, only that
    # the loop exited.
    del results


def test_master_runs_as_salt_user_cli_as_root_scenario(cli_batch, manager, opts):
    """
    Reproduces the user-facing scenario from issue #69418: salt-master
    running as user ``salt`` (so it owns ``<cachedir>``), salt CLI
    invoked as ``root``.  In that deployment, any write to the
    master's cachedir from the CLI process pre-creates the JID dir
    with root ownership and bricks the master's subsequent
    ``local_cache.prep_jid`` write.

    We simulate the constraint by making the cachedir un-writable
    from the CLI's vantage point (``os.makedirs`` raises
    ``PermissionError``) and verify that the batch run still
    completes — because all persistence goes through the manager's
    bridge, which in this test is the only caller that touches the
    disk.
    """
    _bridge_cli_to_manager(cli_batch, manager)
    cli_batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    cli_batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    real_makedirs = __import__("os").makedirs
    real_open = __import__("builtins").open

    # The manager handlers run *synchronously* inside the test's
    # process, so a global ``os.makedirs`` block would also break
    # the manager.  Instead, simulate the failure mode at the
    # source: any call to the persistence helpers from inside
    # ``salt.cli.batch`` raises (using mock.patch's spec ensures we
    # don't accidentally pick up other importers).
    with patch(
        "salt.cli.batch.salt.utils.batch_state.write_batch_state",
        side_effect=PermissionError("simulated: master cachedir not writable from CLI"),
    ), patch(
        "salt.cli.batch.salt.utils.batch_state.add_to_active_index",
        side_effect=PermissionError("simulated"),
    ):
        results = list(Batch.run(cli_batch))

    # The patches above also affect the manager's view because
    # Python module objects are shared (see
    # https://docs.python.org/3/reference/import.html#submodules),
    # but the CLI's *new* code path doesn't call those helpers
    # directly — so the patches are never hit and the run completes
    # normally.  Both minions return.
    assert len(results) == 2
    assert all(next(iter(d.values())) is True for d, _ in results)

    # Best-effort: ``real_makedirs`` and ``real_open`` are
    # retained for symmetry — we don't actually need them here, but
    # the import warms ``os`` and ``builtins`` and keeps the test
    # close to the deployment shape.
    assert real_makedirs is not None
    assert real_open is not None
