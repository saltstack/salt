# -*- coding: utf-8 -*-
"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform

# Import Salt libs
from salt import client
from salt.exceptions import (
    EauthAuthenticationError,
    SaltClientError,
    SaltInvocationError,
    SaltReqTimeoutError,
)

# Import Salt Testing libs
from tests.support.mixins import SaltClientTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


class LocalClientTestCase(TestCase, SaltClientTestCaseMixin):
    def test_job_result_return_success(self):
        """
        Should return the `expected_return`, since there is a job with the right jid.
        """
        minions = ()
        jid = "0815"
        raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
        expected_return = {"fake-id": {"ret": "fake-return"}}
        local_client = client.LocalClient(mopts=self.get_temp_config("master"))
        local_client.event.get_event = MagicMock(return_value=raw_return)
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        val = next(ret)
        self.assertEqual(val, expected_return)

    def test_job_result_return_failure(self):
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
        local_client = client.LocalClient(mopts=self.get_temp_config("master"))
        local_client.event.get_event = MagicMock()
        local_client.event.get_event.side_effect = [raw_return, None]
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        with self.assertRaises(StopIteration):
            next(ret)

    def test_create_local_client(self):
        local_client = client.LocalClient(mopts=self.get_temp_config("master"))
        self.assertIsInstance(
            local_client,
            client.LocalClient,
            "LocalClient did not create a LocalClient instance",
        )

    def test_check_pub_data(self):
        just_minions = {"minions": ["m1", "m2"]}
        jid_no_minions = {"jid": "1234", "minions": []}
        valid_pub_data = {"minions": ["m1", "m2"], "jid": "1234"}

        self.assertRaises(EauthAuthenticationError, self.client._check_pub_data, "")
        self.assertDictEqual(
            {},
            self.client._check_pub_data(just_minions),
            "Did not handle lack of jid correctly",
        )

        self.assertDictEqual(
            {},
            self.client._check_pub_data({"jid": "0"}),
            "Passing JID of zero is not handled gracefully",
        )

        with patch.dict(self.client.opts, {}):
            self.client._check_pub_data(jid_no_minions)

        self.assertDictEqual(
            valid_pub_data, self.client._check_pub_data(valid_pub_data)
        )

    def test_cmd_subset(self):
        with patch(
            "salt.client.LocalClient.cmd",
            return_value={
                "minion1": ["first.func", "second.func"],
                "minion2": ["first.func", "second.func"],
            },
        ):
            with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
                self.client.cmd_subset("*", "first.func", sub=1, cli=True)
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
                self.client.cmd_subset("*", "first.func", sub=10, cli=True)
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

                ret = self.client.cmd_subset(
                    "*", "first.func", sub=1, cli=True, full_return=True
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

    @skipIf(salt.utils.platform.is_windows(), "Not supported on Windows")
    def test_pub(self):
        """
        Tests that the client cleanly returns when the publisher is not running

        Note: Requires ZeroMQ's IPC transport which is not supported on windows.
        """
        if self.get_config("minion")["transport"] != "zeromq":
            self.skipTest("This test only works with ZeroMQ")
        # Make sure we cleanly return if the publisher isn't running
        with patch("os.path.exists", return_value=False):
            self.assertRaises(
                SaltClientError, lambda: self.client.pub("*", "test.ping")
            )

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
                self.assertRaises(
                    SaltInvocationError,
                    self.client.pub,
                    "non_existent_group",
                    "test.ping",
                    tgt_type="nodegroup",
                )

    @skipIf(not salt.utils.platform.is_windows(), "Windows only test")
    def test_pub_win32(self):
        """
        Tests that the client raises a timeout error when using ZeroMQ's TCP
        transport and publisher is not running.

        Note: Requires ZeroMQ's TCP transport, this is only the default on Windows.
        """
        if self.get_config("minion")["transport"] != "zeromq":
            self.skipTest("This test only works with ZeroMQ")
        # Make sure we cleanly return if the publisher isn't running
        with patch("os.path.exists", return_value=False):
            self.assertRaises(
                SaltReqTimeoutError, lambda: self.client.pub("*", "test.ping")
            )

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
                self.assertRaises(
                    SaltInvocationError,
                    self.client.pub,
                    "non_existent_group",
                    "test.ping",
                    tgt_type="nodegroup",
                )
