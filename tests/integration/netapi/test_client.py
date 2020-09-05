import logging
import os
import time

import pytest
import salt.config
import salt.netapi
from salt.exceptions import EauthAuthenticationError
from tests.support.case import SSHCase
from tests.support.helpers import SaveRequestsPostHandler, Webserver, slowTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


@pytest.mark.usefixtures("salt_master", "salt_sub_minion")
class NetapiClientTest(TestCase):
    eauth_creds = {
        "username": "saltdev_auto",
        "password": "saltdev",
        "eauth": "auto",
    }

    def setUp(self):
        """
        Set up a NetapiClient instance
        """
        opts = AdaptedConfigurationTestCaseMixin.get_config("client_config").copy()
        self.netapi = salt.netapi.NetapiClient(opts)

    def tearDown(self):
        del self.netapi

    @slowTest
    def test_local(self):
        low = {"client": "local", "tgt": "*", "fun": "test.ping", "timeout": 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test
        # runner's proxy minion is running, and we're not testing proxy
        # minions here anyway, just remove it from the response.
        ret.pop("proxytest", None)
        self.assertEqual(ret, {"minion": True, "sub_minion": True})

    @slowTest
    def test_local_batch(self):
        low = {"client": "local_batch", "tgt": "*", "fun": "test.ping", "timeout": 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        rets = []
        for _ret in ret:
            rets.append(_ret)
        self.assertIn({"sub_minion": True}, rets)
        self.assertIn({"minion": True}, rets)

    def test_local_async(self):
        low = {"client": "local_async", "tgt": "*", "fun": "test.ping"}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn("jid", ret)
        ret.pop("jid", None)
        ret["minions"] = sorted(ret["minions"])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret["minions"].remove("proxytest")
        except ValueError:
            pass
        self.assertEqual(ret, {"minions": sorted(["minion", "sub_minion"])})

    def test_local_unauthenticated(self):
        low = {"client": "local", "tgt": "*", "fun": "test.ping"}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    @slowTest
    def test_wheel(self):
        low = {"client": "wheel", "fun": "key.list_all"}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn("tag", ret)
        ret.pop("tag")

        data = ret.get("data", {})
        self.assertIn("jid", data)
        data.pop("jid", None)

        self.assertIn("tag", data)
        data.pop("tag", None)

        ret.pop("_stamp", None)
        data.pop("_stamp", None)

        self.maxDiff = None
        self.assertTrue(
            {"master.pem", "master.pub"}.issubset(set(ret["data"]["return"]["local"]))
        )

    @slowTest
    def test_wheel_async(self):
        # Give this test a little breathing room
        time.sleep(3)
        low = {"client": "wheel_async", "fun": "key.list_all"}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        self.assertIn("jid", ret)
        self.assertIn("tag", ret)

    def test_wheel_unauthenticated(self):
        low = {"client": "wheel", "tgt": "*", "fun": "test.ping"}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    @skipIf(True, "This is not testing anything. Skipping for now.")
    def test_runner(self):
        # TODO: fix race condition in init of event-- right now the event class
        # will finish init even if the underlying zmq socket hasn't connected yet
        # this is problematic for the runnerclient's master_call method if the
        # runner is quick
        # low = {'client': 'runner', 'fun': 'cache.grains'}
        low = {"client": "runner", "fun": "test.sleep", "arg": [2]}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    @skipIf(True, "This is not testing anything. Skipping for now.")
    def test_runner_async(self):
        low = {"client": "runner", "fun": "cache.grains"}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    def test_runner_unauthenticated(self):
        low = {"client": "runner", "tgt": "*", "fun": "test.ping"}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)


@pytest.mark.requires_sshd_server
class NetapiSSHClientTest(SSHCase):
    eauth_creds = {
        "username": "saltdev_auto",
        "password": "saltdev",
        "eauth": "auto",
    }

    def setUp(self):
        """
        Set up a NetapiClient instance
        """
        opts = AdaptedConfigurationTestCaseMixin.get_config("client_config").copy()
        self.netapi = salt.netapi.NetapiClient(opts)

        self.priv_file = os.path.join(RUNTIME_VARS.TMP_SSH_CONF_DIR, "client_key")
        self.rosters = os.path.join(RUNTIME_VARS.TMP_CONF_DIR)

        # Initialize salt-ssh
        self.run_function("test.ping")

    def tearDown(self):
        del self.netapi

    @classmethod
    def setUpClass(cls):
        cls.post_webserver = Webserver(handler=SaveRequestsPostHandler)
        cls.post_webserver.start()
        cls.post_web_root = cls.post_webserver.web_root
        cls.post_web_handler = cls.post_webserver.handler

    @classmethod
    def tearDownClass(cls):
        cls.post_webserver.stop()
        del cls.post_webserver

    @slowTest
    def test_ssh(self):
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "ignore_host_keys": True,
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
        }

        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        self.assertIn("localhost", ret)
        self.assertIn("return", ret["localhost"])
        self.assertEqual(ret["localhost"]["return"], True)
        self.assertEqual(ret["localhost"]["id"], "localhost")
        self.assertEqual(ret["localhost"]["fun"], "test.ping")

    @slowTest
    def test_ssh_unauthenticated(self):
        low = {"client": "ssh", "tgt": "localhost", "fun": "test.ping"}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    @slowTest
    def test_ssh_unauthenticated_raw_shell_curl(self):

        fun = "-o ProxyCommand curl {}".format(self.post_web_root)
        low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(self.post_web_handler.received_requests, [])
        self.assertEqual(ret, None)

    @slowTest
    def test_ssh_unauthenticated_raw_shell_touch(self):

        badfile = os.path.join(RUNTIME_VARS.TMP, "badfile.txt")
        fun = "-o ProxyCommand touch {}".format(badfile)
        low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(ret, None)
        self.assertFalse(os.path.exists("badfile.txt"))

    @slowTest
    def test_ssh_authenticated_raw_shell_disabled(self):

        badfile = os.path.join(RUNTIME_VARS.TMP, "badfile.txt")
        fun = "-o ProxyCommand touch {}".format(badfile)
        low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

        low.update(self.eauth_creds)

        ret = None
        with patch.dict(self.netapi.opts, {"netapi_allow_raw_shell": False}):
            with self.assertRaises(EauthAuthenticationError) as excinfo:
                ret = self.netapi.run(low)

        self.assertEqual(ret, None)
        self.assertFalse(os.path.exists("badfile.txt"))
