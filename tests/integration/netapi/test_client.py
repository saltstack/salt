import copy
import logging
import os
import time

import pytest
import salt.config
import salt.netapi
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
from salt.exceptions import EauthAuthenticationError
from tests.support.case import ModuleCase, SSHCase
from tests.support.helpers import SaveRequestsPostHandler, Webserver
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
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
        self.roster_file = os.path.join(self.rosters, "roster")

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

    @pytest.mark.slow_test
    def test_ssh(self):
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "ignore_host_keys": True,
            "roster_file": self.roster_file,
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

    @pytest.mark.slow_test
    def test_ssh_unauthenticated(self):
        low = {"client": "ssh", "tgt": "localhost", "fun": "test.ping"}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    @pytest.mark.slow_test
    def test_ssh_unauthenticated_raw_shell_curl(self):

        fun = "-o ProxyCommand curl {}".format(self.post_web_root)
        low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(self.post_web_handler.received_requests, [])
        self.assertEqual(ret, None)

    @pytest.mark.slow_test
    def test_ssh_unauthenticated_raw_shell_touch(self):

        badfile = os.path.join(RUNTIME_VARS.TMP, "badfile.txt")
        fun = "-o ProxyCommand touch {}".format(badfile)
        low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(ret, None)
        self.assertFalse(os.path.exists("badfile.txt"))

    @pytest.mark.slow_test
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

    @staticmethod
    def cleanup_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def cleanup_dir(path):
        try:
            salt.utils.files.rm_rf(path)
        except OSError:
            pass

    @pytest.mark.slow_test
    def test_shell_inject_ssh_priv(self):
        """
        Verify CVE-2020-16846 for ssh_priv variable
        """
        # ZDI-CAN-11143
        path = "/tmp/test-11143"
        self.addCleanup(self.cleanup_file, path)
        self.addCleanup(self.cleanup_file, "aaa")
        self.addCleanup(self.cleanup_file, "aaa.pub")
        self.addCleanup(self.cleanup_dir, "aaa|id>")
        tgts = ["repo.saltproject.io", "www.zerodayinitiative.com"]
        for tgt in tgts:
            low = {
                "roster": "cache",
                "client": "ssh",
                "tgt": tgt,
                "ssh_priv": "aaa|id>{} #".format(path),
                "fun": "test.ping",
                "eauth": "auto",
                "username": "saltdev_auto",
                "password": "saltdev",
                "roster_file": self.roster_file,
                "rosters": self.rosters,
            }
            ret = self.netapi.run(low)
            if ret.get(tgt):
                break
        self.assertFalse(ret[tgt]["stdout"])
        self.assertTrue(ret[tgt]["stderr"])
        self.assertFalse(os.path.exists(path))

    @pytest.mark.slow_test
    def test_shell_inject_tgt(self):
        """
        Verify CVE-2020-16846 for tgt variable
        """
        # ZDI-CAN-11167
        path = "/tmp/test-11167"
        self.addCleanup(self.cleanup_file, path)
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "root|id>{} #@127.0.0.1".format(path),
            "roster_file": self.roster_file,
            "rosters": "/",
            "fun": "test.ping",
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
            "ignore_host_keys": True,
        }
        ret = self.netapi.run(low)
        self.assertFalse(ret["127.0.0.1"]["stdout"])
        self.assertTrue(ret["127.0.0.1"]["stderr"])
        self.assertFalse(os.path.exists(path))

    @pytest.mark.slow_test
    def test_shell_inject_ssh_options(self):
        """
        Verify CVE-2020-16846 for ssh_options
        """
        # ZDI-CAN-11169
        path = "/tmp/test-11169"
        self.addCleanup(self.cleanup_file, path)
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "127.0.0.1",
            "renderer": "jinja|yaml",
            "fun": "test.ping",
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
            "roster_file": self.roster_file,
            "rosters": "/",
            "ssh_options": ["|id>{} #".format(path), "lol"],
        }
        ret = self.netapi.run(low)
        self.assertFalse(ret["127.0.0.1"]["stdout"])
        self.assertTrue(ret["127.0.0.1"]["stderr"])
        self.assertFalse(os.path.exists(path))

    @pytest.mark.slow_test
    def test_shell_inject_ssh_port(self):
        """
        Verify CVE-2020-16846 for ssh_port variable
        """
        # ZDI-CAN-11172
        path = "/tmp/test-11172"
        self.addCleanup(self.cleanup_file, path)
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "127.0.0.1",
            "renderer": "jinja|yaml",
            "fun": "test.ping",
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
            "roster_file": self.roster_file,
            "rosters": "/",
            "ssh_port": "hhhhh|id>{} #".format(path),
            "ignore_host_keys": True,
        }
        ret = self.netapi.run(low)
        self.assertFalse(ret["127.0.0.1"]["stdout"])
        self.assertTrue(ret["127.0.0.1"]["stderr"])
        self.assertFalse(os.path.exists(path))

    @pytest.mark.slow_test
    def test_shell_inject_remote_port_forwards(self):
        """
        Verify CVE-2020-16846 for remote_port_forwards variable
        """
        # ZDI-CAN-11173
        path = "/tmp/test-1173"
        self.addCleanup(self.cleanup_file, path)
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "127.0.0.1",
            "renderer": "jinja|yaml",
            "fun": "test.ping",
            "roster_file": self.roster_file,
            "rosters": "/",
            "ssh_remote_port_forwards": "hhhhh|id>{} #, lol".format(path),
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
            "ignore_host_keys": True,
        }
        ret = self.netapi.run(low)
        self.assertFalse(ret["127.0.0.1"]["stdout"])
        self.assertTrue(ret["127.0.0.1"]["stderr"])
        self.assertFalse(os.path.exists(path))


@pytest.mark.requires_sshd_server
class NetapiSSHClientAuthTest(SSHCase):

    USERA = "saltdev-auth"
    USERA_PWD = "saltdev"

    def setUp(self):
        """
        Set up a NetapiClient instance
        """
        opts = salt.config.client_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
        )
        naopts = copy.deepcopy(opts)
        naopts["ignore_host_keys"] = True
        self.netapi = salt.netapi.NetapiClient(naopts)

        self.priv_file = os.path.join(RUNTIME_VARS.TMP_SSH_CONF_DIR, "client_key")
        self.rosters = os.path.join(RUNTIME_VARS.TMP_CONF_DIR)
        self.roster_file = os.path.join(self.rosters, "roster")
        # Initialize salt-ssh
        self.run_function("test.ping")
        self.mod_case = ModuleCase()
        try:
            add_user = self.mod_case.run_function(
                "user.add", [self.USERA], createhome=False
            )
            self.assertTrue(add_user)
            if salt.utils.platform.is_darwin():
                hashed_password = self.USERA_PWD
            else:
                hashed_password = salt.utils.pycrypto.gen_hash(password=self.USERA_PWD)
            add_pwd = self.mod_case.run_function(
                "shadow.set_password",
                [self.USERA, hashed_password],
            )
            self.assertTrue(add_pwd)
        except AssertionError:
            self.mod_case.run_function("user.delete", [self.USERA], remove=True)
            self.skipTest("Could not add user or password, skipping test")
        self.expfile = os.path.join(RUNTIME_VARS.TMP, "exploited")

    def tearDown(self):
        try:
            os.remove(self.expfile)
        except OSError:
            pass
        del self.expfile
        del self.netapi
        self.mod_case.run_function("user.delete", [self.USERA], remove=True)

    @staticmethod
    def cleanup_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @pytest.mark.slow_test
    def test_extra_mods(self):
        """
        validate input from extra_mods
        """
        path = os.path.join(RUNTIME_VARS.TMP, "test_extra_mods")
        self.addCleanup(self.cleanup_file, path)
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
            "eauth": "pam",
            "username": self.USERA,
            "password": self.USERA_PWD,
            "regen_thin": True,
            "thin_extra_mods": "';touch {};'".format(path),
        }

        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))

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

    @pytest.mark.slow_test
    def test_ssh_auth_bypass(self):
        """
        CVE-2020-25592 - Bogus eauth raises exception.
        """
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "127.0.0.1",
            "renderer": "jinja|yaml",
            "fun": "test.ping",
            "roster_file": self.roster_file,
            "rosters": "/",
            "eauth": "xx",
            "ignore_host_keys": True,
        }
        with self.assertRaises(salt.exceptions.EauthAuthenticationError):
            ret = self.netapi.run(low)

    @pytest.mark.slow_test
    def test_ssh_auth_valid(self):
        """
        CVE-2020-25592 - Valid eauth works as expected.
        """
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
            "eauth": "pam",
            "username": self.USERA,
            "password": self.USERA_PWD,
        }
        ret = self.netapi.run(low)
        assert "localhost" in ret
        assert ret["localhost"]["return"] is True

    @pytest.mark.slow_test
    def test_ssh_auth_invalid(self):
        """
        CVE-2020-25592 - Wrong password raises exception.
        """
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
            "eauth": "pam",
            "username": self.USERA,
            "password": "notvalidpassword",
        }
        with self.assertRaises(salt.exceptions.EauthAuthenticationError):
            ret = self.netapi.run(low)

    @pytest.mark.slow_test
    def test_ssh_auth_invalid_acl(self):
        """
        CVE-2020-25592 - Eauth ACL enforced.
        """
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "at.at",
            "args": ["12:05am", "echo foo"],
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
            "eauth": "pam",
            "username": self.USERA,
            "password": "notvalidpassword",
        }
        with self.assertRaises(salt.exceptions.EauthAuthenticationError):
            ret = self.netapi.run(low)

    @pytest.mark.slow_test
    def test_ssh_auth_token(self):
        """
        CVE-2020-25592 - Eauth tokens work as expected.
        """
        low = {
            "eauth": "pam",
            "username": self.USERA,
            "password": self.USERA_PWD,
        }
        ret = self.netapi.loadauth.mk_token(low)
        assert "token" in ret and ret["token"]
        low = {
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "roster_file": "roster",
            "rosters": [self.rosters],
            "ssh_priv": self.priv_file,
            "token": ret["token"],
        }
        ret = self.netapi.run(low)
        assert "localhost" in ret
        assert ret["localhost"]["return"] is True

    def test_ssh_cve_2021_3197_a(self):
        assert not os.path.exists(self.expfile)
        low = {
            "eauth": "auto",
            "username": self.USERA,
            "password": self.USERA_PWD,
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "ssh_port": '22 -o ProxyCommand="touch {}"'.format(self.expfile),
            "ssh_priv": self.priv_file,
            "roster_file": "roster",
            "rosters": [self.rosters],
        }
        ret = self.netapi.run(low)
        assert not os.path.exists(self.expfile)

    def test_ssh_cve_2021_3197_b(self):
        assert not os.path.exists(self.expfile)
        low = {
            "eauth": "auto",
            "username": self.USERA,
            "password": self.USERA_PWD,
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "ssh_port": 22,
            "ssh_priv": self.priv_file,
            "ssh_options": ['ProxyCommand="touch {}"'.format(self.expfile)],
            "roster_file": "roster",
            "rosters": [self.rosters],
        }
        ret = self.netapi.run(low)
        assert not os.path.exists(self.expfile)
