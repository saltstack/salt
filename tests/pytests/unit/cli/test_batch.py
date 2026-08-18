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
    batch.local.cmd_iter_no_block.assert_called_with(
        ["baz", "bar", "foo"],
        "test",
        "foo",
        5,
        "list",
        raw=False,
        ret="my_return",
        show_jid=False,
        verbose=False,
        gather_job_timeout=5,
    )


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
    batch.local.cmd_iter_no_block.assert_called_with(
        ["baz", "bar", "foo"],
        "test",
        "foo",
        5,
        "list",
        raw=False,
        ret="my_return",
        show_jid=False,
        verbose=False,
        gather_job_timeout=5,
    )


def test_gather_minions_ignores_error_payload(batch):
    """
    Transport-level error payloads (e.g. ``{"error": "...", "jid": "..."}``
    or ``{"error": "Authentication failure"}``) must not be treated as
    minion IDs in gather_minions().

    Regression for issues #46876, #48509, #50238, #60724.
    """
    ping_returns = [
        # Transport-level error payload — must be ignored
        {"error": "Authentication failure", "jid": "20260101000000"},
        # Legit discovery payload — emitted before individual pings
        {"minions": ["minion1"], "jid": "20260101000001"},
        # Individual minion ping reply
        {"minion1": {"ret": True}},
    ]

    batch.local.cmd_iter = MagicMock(return_value=iter(ping_returns))

    batch.opts.update(
        {
            "tgt": "*",
            "tgt_type": "glob",
            "timeout": 5,
            "gather_job_timeout": 5,
        }
    )

    minions, _, _ = batch.gather_minions()

    assert "error" not in minions
    assert minions == ["minion1"]


def test_gather_minions_fixes_minions_jid_check(batch):
    """
    The Python expression ``("minions" and "jid") in ret`` evaluates to
    ``"jid" in ret`` — a bug that causes the discovery payload to be
    processed as a minion return rather than skipped.

    The fix replaces it with ``"minions" in ret and "jid" in ret`` so
    the full-list discovery packet is handled correctly.
    """
    # A payload that has "jid" but NOT "minions" — the old buggy check
    # would have treated it as a discovery payload; the fixed check must
    # fall through to the else branch.
    ping_returns = [
        {"jid": "20260101000000"},  # has "jid", no "minions" — old code would skip
        {"minion1": {"ret": True}},
    ]

    batch.local.cmd_iter = MagicMock(return_value=iter(ping_returns))

    batch.opts.update(
        {
            "tgt": "*",
            "tgt_type": "glob",
            "timeout": 5,
            "gather_job_timeout": 5,
        }
    )

    minions, _, _ = batch.gather_minions()

    # minion1 must be discovered; the jid-only dict must not be treated as a
    # discovery packet that feeds "minion1" into nret (it has no "minions" key).
    assert "minion1" in minions


def test_run_ignores_error_payload_in_cmd_returns(batch):
    """
    When ``cmd_iter_no_block`` yields a transport-level error dict
    (keyed by ``"error"`` instead of a real minion ID) the batch run
    must silently skip it rather than treating ``"error"`` as a minion.

    Regression for the ``KeyError: 'ret'`` crash described in #46876.
    """
    batch.opts = {
        "batch": "1",
        "timeout": 5,
        "fun": "test.ping",
        "arg": [],
        "gather_job_timeout": 5,
    }
    batch.gather_minions = MagicMock(return_value=[["minion1"], [], []])

    def _make_iter(*args, **kwargs):
        # First yield is a transport-level error payload
        yield {"error": "Publish failed", "failed": True}
        # Second yield is the real minion return
        yield {"minion1": {"ret": True, "retcode": 0}}

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_make_iter)
    batch.local.event.get_event = MagicMock(return_value=None)

    results = list(Batch.run(batch))

    returned_minions = [next(iter(d.keys())) for d, _rc in results]
    assert "error" not in returned_minions
    assert "minion1" in returned_minions
