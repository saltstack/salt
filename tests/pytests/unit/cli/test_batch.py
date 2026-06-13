"""
Unit Tests for the salt.cli.batch module
"""

import pytest

from salt.cli.batch import Batch
from tests.support.mock import MagicMock, patch


@pytest.fixture
def batch():
    opts = {
        "batch": "",
        "conf_file": {},
        "tgt": "",
        "transport": "",
        "timeout": 5,
        "gather_job_timeout": 5,
    }

    mock_client = MagicMock()
    with patch("salt.client.get_local_client", MagicMock(return_value=mock_client)):
        with patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
            yield Batch(opts, quiet="quiet")


def test_get_bnum_str(batch):
    """
    Tests passing batch value as a number(str)
    """
    batch.opts = {"batch": "2", "timeout": 5}
    batch.minions = ["foo", "bar"]
    assert Batch.get_bnum(batch) == 2


def test_get_bnum_int(batch):
    """
    Tests passing batch value as a number(int)
    """
    batch.opts = {"batch": 2, "timeout": 5}
    batch.minions = ["foo", "bar"]
    assert Batch.get_bnum(batch) == 2


def test_get_bnum_percentage(batch):
    """
    Tests passing batch value as percentage
    """
    batch.opts = {"batch": "50%", "timeout": 5}
    batch.minions = ["foo"]
    assert Batch.get_bnum(batch) == 1


def test_get_bnum_high_percentage(batch):
    """
    Tests passing batch value as percentage over 100%
    """
    batch.opts = {"batch": "160%", "timeout": 5}
    batch.minions = ["foo", "bar", "baz"]
    assert Batch.get_bnum(batch) == 4


def test_get_bnum_invalid_batch_data(batch):
    """
    Tests when an invalid batch value is passed
    """
    ret = Batch.get_bnum(batch)
    assert ret is None


def test_return_value_in_run_for_ret(batch):
    """
    cmd_iter_no_block should have been called with a return no matter if
    the return value was in ret or return.
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test",
        "arg": "foo",
        "gather_job_timeout": 5,
        "ret": "my_return",
    }
    batch.gather_minions = MagicMock(
        return_value=[["foo", "bar", "baz"], [], []],
    )
    batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))
    ret = Batch.run(batch)
    # We need to fetch at least one object to trigger the relevant code path.
    x = next(ret)
    batch.local.cmd_iter_no_block.assert_called_once()
    call_kwargs = batch.local.cmd_iter_no_block.call_args
    assert call_kwargs.kwargs["ret"] == "my_return"
    assert call_kwargs.kwargs["show_jid"] is False
    assert call_kwargs.kwargs["verbose"] is False
    assert call_kwargs.kwargs["gather_job_timeout"] == 5


def test_return_value_in_run_for_return(batch):
    """
    cmd_iter_no_block should have been called with a return no matter if
    the return value was in ret or return.
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test",
        "arg": "foo",
        "gather_job_timeout": 5,
        "return": "my_return",
    }
    batch.gather_minions = MagicMock(
        return_value=[["foo", "bar", "baz"], [], []],
    )
    batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))
    ret = Batch.run(batch)
    # We need to fetch at least one object to trigger the relevant code path.
    x = next(ret)
    batch.local.cmd_iter_no_block.assert_called_once()
    call_kwargs = batch.local.cmd_iter_no_block.call_args
    assert call_kwargs.kwargs["ret"] == "my_return"
    assert call_kwargs.kwargs["show_jid"] is False
    assert call_kwargs.kwargs["verbose"] is False
    assert call_kwargs.kwargs["gather_job_timeout"] == 5


def test_single_jid_across_batch_iterations(batch):
    """
    With 4 minions and batch size 2, cmd_iter_no_block should be called
    twice with the same jid kwarg.
    """
    batch.opts = {
        "batch": "2",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2", "m3", "m4"], [], []],
    )

    def _make_iter(*args, **kwargs):
        """Return an iterator that yields results for targeted minions."""
        minions = args[0]
        for m in minions:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    ret = list(Batch.run(batch))

    assert batch.local.cmd_iter_no_block.call_count == 2
    jids = [call.kwargs["jid"] for call in batch.local.cmd_iter_no_block.call_args_list]
    assert jids[0] == jids[1]
    assert jids[0] != ""
    # Every minion should yield a real return (ret=True), not a
    # placeholder ({}) from the "didn't respond" branch.  If the
    # sub-batch target list were aliased with the tracker, a return
    # arriving here would prune the list mid-iteration and cause the
    # generator to StopIteration early, leaving later minions stuck in
    # the placeholder path.
    assert len(ret) == 4
    assert sorted(next(iter(d.keys())) for d, _rc in ret) == ["m1", "m2", "m3", "m4"]
    assert all(next(iter(d.values())) is True for d, _rc in ret)


def test_single_jid_passed_to_cmd_iter_no_block(batch):
    """
    Verify cmd_iter_no_block receives a non-empty jid string kwarg.
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2"], [], []],
    )
    batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))
    ret = Batch.run(batch)
    next(ret)
    call_kwargs = batch.local.cmd_iter_no_block.call_args
    assert "jid" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["jid"], str)
    assert len(call_kwargs.kwargs["jid"]) > 0


def test_single_jid_with_failhard(batch):
    """
    With failhard=True and first minion returning error, verify early
    termination and that JID was passed to the single cmd_iter_no_block call.
    """
    batch.opts = {
        "batch": "2",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
        "failhard": True,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2", "m3", "m4"], [], []],
    )

    def _make_iter(*args, **kwargs):
        minions = args[0]
        for m in minions:
            yield {m: {"ret": True, "retcode": 1}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    ret = list(Batch.run(batch))

    # failhard should stop after first batch
    assert batch.local.cmd_iter_no_block.call_count == 1
    call_kwargs = batch.local.cmd_iter_no_block.call_args
    assert "jid" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["jid"], str)
    assert len(call_kwargs.kwargs["jid"]) > 0
    # Only the first processed minion should yield; failhard halts the
    # run before the second sub-batch minion's entry in parts.items()
    # is reached.
    assert len(ret) == 1
    data, retcode = ret[0]
    assert next(iter(data.values())) is True
    assert retcode == 1


def test_single_jid_single_batch(batch):
    """
    All minions fit in one batch (batch="100%"). Verify cmd_iter_no_block
    called once with jid kwarg.
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2", "m3"], [], []],
    )

    def _make_iter(*args, **kwargs):
        minions = args[0]
        for m in minions:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    ret = list(Batch.run(batch))

    assert batch.local.cmd_iter_no_block.call_count == 1
    call_kwargs = batch.local.cmd_iter_no_block.call_args
    assert "jid" in call_kwargs.kwargs
    assert len(ret) == 3
    assert sorted(next(iter(d.keys())) for d, _rc in ret) == ["m1", "m2", "m3"]
    assert all(next(iter(d.values())) is True for d, _rc in ret)


def test_get_bnum_100_percentage_exact(batch):
    """
    batch="100%" with N minions must return exactly N (no off-by-one).
    """
    batch.opts = {"batch": "100%", "timeout": 5}
    batch.minions = ["a", "b", "c", "d"]
    assert Batch.get_bnum(batch) == 4


def test_get_bnum_low_percentage_rounds_up(batch):
    """
    A percentage that works out to less than one minion must round up
    via math.ceil so at least one minion is dispatched per batch.
    """
    batch.opts = {"batch": "1%", "timeout": 5}
    batch.minions = [f"m{i}" for i in range(10)]
    assert Batch.get_bnum(batch) == 1


def test_get_bnum_zero(batch):
    """
    An explicit batch=0 returns 0.  The caller is responsible for
    deciding what to do with "no minions per batch".
    """
    batch.opts = {"batch": 0, "timeout": 5}
    batch.minions = ["a", "b"]
    assert Batch.get_bnum(batch) == 0


def test_get_bnum_percentage_no_minions(batch):
    """
    A percentage of an empty minion list returns 0, not a divide-by-zero
    or a negative number.
    """
    batch.opts = {"batch": "50%", "timeout": 5}
    batch.minions = []
    assert Batch.get_bnum(batch) == 0


def test_get_bnum_fractional_percentage(batch):
    """
    A fractional percentage must be truncated (not rounded) once it
    exceeds one minion.  33.3% of 10 is 3.33 → 3.
    """
    batch.opts = {"batch": "33.3%", "timeout": 5}
    batch.minions = [f"m{i}" for i in range(10)]
    assert Batch.get_bnum(batch) == 3


def test_run_no_minions_returns_early(batch):
    """
    When gather_minions yields no targets, run() must exit immediately
    without publishing anything.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[[], [], []])
    batch.local.cmd_iter_no_block = MagicMock(return_value=iter([]))

    ret = list(Batch.run(batch))

    assert ret == []
    batch.local.cmd_iter_no_block.assert_not_called()


def test_run_passes_show_jid_and_verbose_from_options():
    """
    When a parser is attached with show_jid and verbose set, those flags
    are forwarded to cmd_iter_no_block (complement of the default-None
    case already covered by test_return_value_in_run_for_ret).
    """
    opts = {
        "batch": "1",
        "conf_file": {},
        "tgt": "",
        "transport": "",
        "timeout": 5,
        "gather_job_timeout": 5,
        "fun": "test.ping",
        "arg": [],
    }
    parser = MagicMock()
    parser.show_jid = True
    parser.verbose = True

    mock_client = MagicMock()
    with patch("salt.client.get_local_client", MagicMock(return_value=mock_client)):
        with patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
            b = Batch(opts, quiet=True, _parser=parser)

    b.gather_minions = MagicMock(return_value=[["m1"], [], []])
    b.local.cmd_iter_no_block = MagicMock(return_value=iter([]))

    gen = Batch.run(b)
    next(gen)

    kwargs = b.local.cmd_iter_no_block.call_args.kwargs
    assert kwargs["show_jid"] is True
    assert kwargs["verbose"] is True


def test_run_raw_mode_yield_shape(batch):
    """
    In raw mode, cmd_iter_no_block yields the raw event envelope with
    the minion id at part["data"]["id"], and Batch.run yields that
    envelope directly (rather than data["ret"]).  raw=True must also
    propagate to cmd_iter_no_block.
    """
    batch.opts = {
        "batch": "2",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
        "raw": True,
    }
    batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {"data": {"id": m, "return": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    ret = list(Batch.run(batch))

    assert len(ret) == 2
    ids = set()
    for envelope, _retcode in ret:
        # The raw envelope is yielded verbatim — not the unwrapped "ret".
        assert "data" in envelope
        ids.add(envelope["data"]["id"])
    assert ids == {"m1", "m2"}
    assert batch.local.cmd_iter_no_block.call_args.kwargs["raw"] is True


def test_run_retcode_dict_takes_max(batch):
    """
    When running multiple modules in a single batch call, retcode is a
    dict keyed by module name.  Batch.run must collapse it to the max
    value so a single non-zero module propagates through the yield.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping,test.retcode",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1"], [], []])

    def _make_iter(*args, **kwargs):
        yield {
            "m1": {
                "ret": True,
                "retcode": {"test.ping": 0, "test.retcode": 42},
            }
        }

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    ret = list(Batch.run(batch))

    assert len(ret) == 1
    _data, retcode = ret[0]
    assert retcode == 42


def test_run_retcode_empty_dict_is_zero(batch):
    """
    An empty retcode dict (no modules reported a retcode) collapses to
    zero rather than raising from max()'s ValueError.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1"], [], []])

    def _make_iter(*args, **kwargs):
        yield {"m1": {"ret": True, "retcode": {}}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    ret = list(Batch.run(batch))

    assert len(ret) == 1
    _data, retcode = ret[0]
    assert retcode == 0


def test_run_failed_to_respond_failhard(batch):
    """
    A return marked failed=True is recorded in the internal `ret` dict
    but is NOT yielded to the caller; with failhard set, the run stops
    immediately after the first such return.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
        "failhard": True,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2", "m3"], [], []],
    )

    def _make_iter(*args, **kwargs):
        yield {args[0][0]: {"failed": True}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    ret = list(Batch.run(batch))

    # Only one sub-batch was dispatched before failhard halted the run.
    assert batch.local.cmd_iter_no_block.call_count == 1
    # The failed-to-respond path does not yield; run() records and halts.
    assert ret == []


def test_run_batch_wait_delays_next_dispatch(batch):
    """
    With batch_wait > 0, after a sub-batch completes the next dispatch
    is held back until the wait window elapses.  Four minions at batch=2
    produce two dispatches; while the wait list is populated, the main
    loop idles on time.sleep(0.02).  We assert both that every minion
    still ran and that at least one idle spin occurred.
    """
    batch.opts = {
        "batch": "2",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
        "batch_wait": 3600,
    }
    batch.gather_minions = MagicMock(
        return_value=[["m1", "m2", "m3", "m4"], [], []],
    )

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    # Controlled clock: the first few time.time() calls stay before
    # the batch_wait entry expires so the loop idles; later calls jump
    # past it so dispatch resumes.  We return the same value on each
    # invocation to keep the state machine deterministic.
    t0 = 1_700_000_000.0
    now_calls = [0]

    def _fake_time():
        now_calls[0] += 1
        if now_calls[0] <= 4:
            return t0
        return t0 + 7200

    spin_sleeps = [0]

    def _fake_sleep(duration):
        if duration == 0.02:
            spin_sleeps[0] += 1

    with patch("salt.cli.batch.time.time", side_effect=_fake_time):
        with patch("salt.cli.batch.time.sleep", side_effect=_fake_sleep):
            ret = list(Batch.run(batch))

    assert len(ret) == 4
    assert batch.local.cmd_iter_no_block.call_count == 2
    # At least one idle spin confirms the wait window actually blocked
    # dispatch.  Without batch_wait, the second dispatch would happen
    # immediately and no 0.02s sleeps would be issued.
    assert spin_sleeps[0] >= 1


def test_run_does_not_write_to_master_cachedir(batch):
    """
    Regression test for issue #69418.

    The sync CLI batch driver must not write batch-state persistence
    files (``.batch.p``, ``batch_active.p``) under the master's
    ``cachedir`` from the CLI process.  The salt-master daemon is the
    sole owner of that directory tree.  When the CLI is invoked as
    ``root`` against a master running as user ``salt``, any
    CLI-initiated write (or directory creation) under the master's
    cachedir produces root-owned files that the master cannot
    subsequently update — which surfaces as a ``PermissionError`` in
    ``local_cache.prep_jid`` and ultimately as
    ``SaltClientError: Some exception handling minion payload`` on
    the user's terminal.

    Assert that ``write_batch_state`` and ``add_to_active_index`` /
    ``remove_from_active_index`` are not called by ``Batch.run()``.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)

    with patch("salt.utils.batch_state.write_batch_state") as write_state, patch(
        "salt.utils.batch_state.add_to_active_index"
    ) as add_index, patch(
        "salt.utils.batch_state.remove_from_active_index"
    ) as remove_index:
        list(Batch.run(batch))

    write_state.assert_not_called()
    add_index.assert_not_called()
    remove_index.assert_not_called()


def test_run_fires_new_progress_and_complete_events(batch):
    """
    The sync CLI batch driver replaces direct disk writes with
    event-bus emissions to the master-side ``BatchManager``.  Every
    state transition gets a ``salt/batch/<jid>/{new,progress,complete,
    halted}`` event carrying the full state in ``data["state"]``;
    the manager persists ``.batch.p`` / updates the active index on
    the CLI's behalf so ``batch.list_active`` and ``batch.status``
    have something to read.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    # Halted-event poll must return None for the batch to actually
    # run (MagicMock's default truthy return would short-circuit the
    # loop into the halt path).
    batch.local.event.get_event = MagicMock(return_value=None)

    list(Batch.run(batch))

    fire_calls = batch.local.event.fire_event.call_args_list
    tags = [c.args[1] for c in fire_calls]
    assert any(t.startswith("salt/batch/") and t.endswith("/new") for t in tags)
    assert any(t.startswith("salt/batch/") and t.endswith("/progress") for t in tags)
    assert any(t.startswith("salt/batch/") and t.endswith("/complete") for t in tags)
    # /halted only fires when the run halts.
    assert not any(t.endswith("/halted") for t in tags)

    # Every payload should embed the full state dict so the manager
    # can persist it without having to read its own disk.
    new_call = next(c for c in fire_calls if c.args[1].endswith("/new"))
    assert "state" in new_call.args[0]
    assert new_call.args[0]["state"]["driver"] == "cli"


def test_run_subscribes_and_unsubscribes_to_halted(batch):
    """
    The CLI subscribes to ``salt/batch/<jid>/halted`` for the run's
    duration so it can react to a ``batch.stop`` request from the
    runner; on teardown it unsubscribes.
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    batch.local.event.get_event = MagicMock(return_value=None)

    list(Batch.run(batch))

    sub_args = batch.local.event.subscribe.call_args.args
    unsub_args = batch.local.event.unsubscribe.call_args.args
    assert sub_args[0].endswith("/halted")
    assert unsub_args[0].endswith("/halted")
    # Same tag both ways.
    assert sub_args[0] == unsub_args[0]


def test_run_halts_when_stop_event_arrives(batch):
    """
    When ``batch.stop <jid>`` is invoked, the master-side
    ``BatchManager._handle_stop`` fires ``salt/batch/<jid>/halted``.
    The CLI polls for that tag every loop iteration and halts the
    run when one arrives — and the teardown event must be the
    ``/halted`` variant, not ``/complete``.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1", "m2", "m3", "m4"], [], []])

    # Iterator that never returns; the run can only end via halt.
    batch.local.cmd_iter_no_block = MagicMock(side_effect=lambda *a, **k: iter([None]))

    # First poll → no halt; second poll → halt event for our jid.
    poll_box = {"n": 0, "captured_jid": None}

    def _capture_jid(payload, tag):
        if tag.endswith("/new"):
            poll_box["captured_jid"] = payload["jid"]

    batch.local.event.fire_event = MagicMock(side_effect=_capture_jid)

    def _get_event(*args, **kwargs):
        poll_box["n"] += 1
        if poll_box["n"] < 2:
            return None
        return {"jid": poll_box["captured_jid"], "reason": "stop"}

    batch.local.event.get_event = MagicMock(side_effect=_get_event)

    list(Batch.run(batch))

    fire_calls = batch.local.event.fire_event.call_args_list
    tags = [c.args[1] for c in fire_calls]
    assert any(t.endswith("/halted") for t in tags)
    assert not any(t.endswith("/complete") for t in tags)


def test_run_event_failures_are_swallowed(batch):
    """
    The CLI batch must remain functional even when the master event
    bus is broken or unreachable: every fire / subscribe / poll path
    must catch and log instead of propagating.  This preserves the
    3007.x behavior of "no visibility but the batch still works."
    """
    batch.opts = {
        "batch": "100%",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["m1"], [], []])

    def _make_iter(*args, **kwargs):
        for m in args[0]:
            yield {m: {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    batch.local.event.fire_event = MagicMock(side_effect=OSError("bus down"))
    batch.local.event.subscribe = MagicMock(side_effect=OSError("bus down"))
    batch.local.event.unsubscribe = MagicMock(side_effect=OSError("bus down"))
    batch.local.event.get_event = MagicMock(side_effect=OSError("bus down"))

    # Should not raise; should yield m1's return.
    results = list(Batch.run(batch))
    assert len(results) == 1
    assert next(iter(results[0][0].values())) is True
