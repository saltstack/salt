"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

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
from tests.support.mixins import SaltClientTestCaseMixin
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def master_config():
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["__role"] = "master"
    return opts


def test_job_result_return_success(master_config):
    """
    Should return the `expected_return`, since there is a job with the right jid.
    """
    minions = ()
    jid = "0815"
    raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
    expected_return = {"fake-id": {"ret": "fake-return"}}
    with client.LocalClient(mopts=master_config) as local_client:
        local_client.event.get_event = MagicMock(return_value=raw_return)
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        val = next(ret)
        assert val == expected_return


def test_job_result_return_failure(master_config):
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
    with client.LocalClient(mopts=master_config) as local_client:
        local_client.event.get_event = MagicMock()
        local_client.event.get_event.side_effect = [raw_return, None]
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        with pytest.raises(StopIteration):
            next(ret)


def test_create_local_client(master_config):
    with client.LocalClient(mopts=master_config) as local_client:
        assert isinstance(
            local_client, client.LocalClient
        ), "LocalClient did not create a LocalClient instance"


def test_check_pub_data():
    just_minions = {"minions": ["m1", "m2"]}
    jid_no_minions = {"jid": "1234", "minions": []}
    valid_pub_data = {"minions": ["m1", "m2"], "jid": "1234"}

    pytest.raises(EauthAuthenticationError, self.client._check_pub_data, "")
    assert {} == self.client._check_pub_data(
        just_minions
    ), "Did not handle lack of jid correctly"

    assert {} == self.client._check_pub_data(
        {"jid": "0"}
    ), "Passing JID of zero is not handled gracefully"

    with patch.dict(self.client.opts, {}):
        self.client._check_pub_data(jid_no_minions)

    assert valid_pub_data == self.client._check_pub_data(valid_pub_data)


def test_cmd_subset(salt_cli):
    with patch(
        "salt.client.LocalClient.cmd",
        return_value={
            "minion1": ["first.func", "second.func"],
            "minion2": ["first.func", "second.func"],
        },
    ):
        with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
            salt_cli.run("first.func", minion_tgt="*", subset=1, cli=True)
            log.debug("=== cmd_cli_mock %s ===", cmd_cli_mock.__dict__)
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
            salt_cli.run("first.func", minion_tgt="*", sub=1, cli=True)
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
            salt_cli.run("first.func", minion_tgt="*", subset=10, cli=True)
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

            ret = salt_cli.run(
                "first.func", minion_tgt="*", subset=1, cli=True, full_return=True
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
def test_pub():
    """
    Tests that the client cleanly returns when the publisher is not running

    Note: Requires ZeroMQ's IPC transport which is not supported on windows.
    """
    if self.get_config("minion")["transport"] != "zeromq":
        self.skipTest("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(SaltClientError, lambda: self.client.pub("*", "test.ping"))

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            self.client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                self.client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )


@pytest.mark.skip_unless_on_windows(reason="Windows only test")
@pytest.mark.slow_test
def test_pub_win32():
    """
    Tests that the client raises a timeout error when using ZeroMQ's TCP
    transport and publisher is not running.

    Note: Requires ZeroMQ's TCP transport, this is only the default on Windows.
    """
    if self.get_config("minion")["transport"] != "zeromq":
        self.skipTest("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(SaltReqTimeoutError, lambda: self.client.pub("*", "test.ping"))

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            self.client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                self.client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )
