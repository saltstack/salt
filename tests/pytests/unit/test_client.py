"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import copy
import logging

import pytest

import salt.utils.platform
from salt import client
from salt.exceptions import (
    EauthAuthenticationError,
    SaltClientError,
    SaltInvocationError,
    SaltReqTimeoutError,
)
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def test_job_result_return_success(master_opts):
    """
    Should return the `expected_return`, since there is a job with the right jid.
    """
    minions = ()
    jid = "0815"
    raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
    expected_return = {"fake-id": {"ret": "fake-return"}}
    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.event.get_event = MagicMock(return_value=raw_return)
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        val = next(ret)
        assert val == expected_return


def test_job_result_return_failure(master_opts):
    """
    We are _not_ getting a job return, because the jid is different. Instead we should
    get a StopIteration exception.
    """
    minions = ()
    jid = "0815"
    raw_return = {
        "id": "fake-id",
        "jid": "0816",
        "data": "",
        "return": "fake-return",
    }
    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.event.get_event = MagicMock()
        local_client.event.get_event.side_effect = [raw_return, None]
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        with pytest.raises(StopIteration):
            next(ret)


def test_create_local_client(master_opts):
    with client.LocalClient(mopts=master_opts) as local_client:
        assert isinstance(
            local_client, client.LocalClient
        ), "LocalClient did not create a LocalClient instance"


def test_check_pub_data(salt_master_factory):
    just_minions = {"minions": ["m1", "m2"]}
    jid_no_minions = {"jid": "1234", "minions": []}
    valid_pub_data = {"minions": ["m1", "m2"], "jid": "1234"}

    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    pytest.raises(EauthAuthenticationError, salt_local_client._check_pub_data, "")
    assert {} == salt_local_client._check_pub_data(
        just_minions
    ), "Did not handle lack of jid correctly"

    assert {} == salt_local_client._check_pub_data(
        {"jid": "0"}
    ), "Passing JID of zero is not handled gracefully"

    with patch.dict(salt_local_client.opts, {}):
        salt_local_client._check_pub_data(jid_no_minions)

    assert valid_pub_data == salt_local_client._check_pub_data(valid_pub_data)


def test_cmd_subset(salt_master_factory):
    salt_local_client = salt.client.get_local_client(mopts=salt_master_factory.config)

    with patch(
        "salt.client.LocalClient.cmd",
        return_value={
            "minion1": ["first.func", "second.func"],
            "minion2": ["first.func", "second.func"],
        },
    ):
        with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
            salt_local_client.cmd_subset("*", "first.func", subset=1, cli=True)
            try:
                cmd_cli_mock.assert_called_with(
                    ["minion2"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )
            salt_local_client.cmd_subset("*", "first.func", subset=10, cli=True)
            try:
                cmd_cli_mock.assert_called_with(
                    ["minion2", "minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1", "minion2"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )

            ret = salt_local_client.cmd_subset(
                "*", "first.func", subset=1, cli=True, full_return=True
            )
            try:
                cmd_cli_mock.assert_called_with(
                    ["minion2"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=True,
                    ret="",
                )
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=True,
                    ret="",
                )


@pytest.mark.skip_on_windows(reason="Not supported on Windows")
def test_pub(salt_master_factory):
    """
    Tests that the client cleanly returns when the publisher is not running

    Note: Requires ZeroMQ's IPC transport which is not supported on windows.
    """
    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    if salt_local_client.opts.get("transport") != "zeromq":
        pytest.skip("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(SaltClientError, lambda: salt_local_client.pub("*", "test.ping"))

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            salt_local_client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                salt_local_client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )


@pytest.mark.skip_unless_on_windows(reason="Windows only test")
@pytest.mark.slow_test
def test_pub_win32(salt_master_factory):
    """
    Tests that the client raises a timeout error when using ZeroMQ's TCP
    transport and publisher is not running.

    Note: Requires ZeroMQ's TCP transport, this is only the default on Windows.
    """
    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    if salt_local_client.opts.get("transport") != "zeromq":
        pytest.skip("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(
            SaltReqTimeoutError, lambda: salt_local_client.pub("*", "test.ping")
        )

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            salt_local_client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                salt_local_client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )


def test_invalid_event_tag_65727(master_opts, caplog):
    """
    LocalClient.get_iter_returns handles non return event tags.
    """
    minions = ()
    jid = "0815"
    raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
    expected_return = {"fake-id": {"ret": "fake-return"}}

    def returns_iter():
        # Invalid return
        yield {
            "tag": "salt/job/0815/return/",
            "data": {
                "return": "fpp",
                "id": "fake-id",
            },
        }
        # Valid return
        yield {
            "tag": "salt/job/0815/ret/",
            "data": {
                "return": "fpp",
                "id": "fake-id",
            },
        }

    with client.LocalClient(mopts=master_opts) as local_client:
        # Returning a truthy value, the real method returns a salt returner but it's not used.
        local_client.returns_for_job = MagicMock(return_value=True)
        # Mock iter returns, we'll return one invalid and one valid return event.
        local_client.get_returns_no_block = MagicMock(return_value=returns_iter())
        with caplog.at_level(logging.DEBUG):
            # Validate we don't choke on the bad return, the method returns a
            # valid respons and the invalid event tag is getting logged to
            # debug.
            for ret in local_client.get_iter_returns(jid, {"fake-id"}):
                assert ret == {"fake-id": {"ret": "fpp"}}
            assert "Skipping non return event: salt/job/0815/return/" in caplog.text
