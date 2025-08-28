"""
Unit Tests for the salt.cli.batch module
"""

import pytest

from salt.cli.batch import Batch, batch_get_opts
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


def test_batch_presence_ping(batch):
    """
    Tests passing batch_presence_ping_timeout and batch_presence_ping_gather_job_timeout
    """
    ret = batch_get_opts("", "test.ping", "2", {}, timeout=20, gather_job_timeout=120)
    assert ret["batch_presence_ping_timeout"] == 20
    assert ret["batch_presence_ping_gather_job_timeout"] == 120
    ret = batch_get_opts(
        "",
        "test.ping",
        "2",
        {},
        timeout=20,
        gather_job_timeout=120,
        batch_presence_ping_timeout=4,
        batch_presence_ping_gather_job_timeout=360,
    )
    assert ret["batch_presence_ping_timeout"] == 4
    assert ret["batch_presence_ping_gather_job_timeout"] == 360


def test_gather_minions_with_batch_presence_ping(batch):
    """
    Tests __gather_minions with batch_presence_ping options
    """
    opts_no_pp = {
        "batch": "2",
        "conf_file": {},
        "tgt": "",
        "transport": "",
        "timeout": 5,
        "gather_job_timeout": 20,
    }
    opts_with_pp = {
        "batch": "2",
        "conf_file": {},
        "tgt": "",
        "transport": "",
        "timeout": 5,
        "gather_job_timeout": 20,
        "batch_presence_ping_timeout": 3,
        "batch_presence_ping_gather_job_timeout": 4,
    }
    local_client_mock = MagicMock()
    with patch(
        "salt.client.get_local_client", MagicMock(return_value=local_client_mock)
    ), patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
        Batch(opts_no_pp).gather_minions()
        Batch(opts_with_pp).gather_minions()
        assert local_client_mock.mock_calls[0][1][3] == opts_no_pp["timeout"]
        assert (
            local_client_mock.mock_calls[0][2]["gather_job_timeout"]
            == opts_no_pp["gather_job_timeout"]
        )
        assert (
            local_client_mock.mock_calls[2][1][3]
            == opts_with_pp["batch_presence_ping_timeout"]
        )
        assert (
            local_client_mock.mock_calls[2][2]["gather_job_timeout"]
            == opts_with_pp["batch_presence_ping_gather_job_timeout"]
        )
