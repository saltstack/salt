# encoding: utf-8
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
import os
import time

import salt.config
import salt.netapi
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto

# Import Salt Testing libs
from tests.support.paths import TMP_CONF_DIR, TMP
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch
from tests.support.case import ModuleCase, SSHCase
from salt.exceptions import EauthAuthenticationError
from tests.support.helpers import (
    Webserver,
    SaveRequestsPostHandler,
    requires_sshd_server
)


from salt.exceptions import (
    EauthAuthenticationError
)

log = logging.getLogger(__name__)


class NetapiClientTest(TestCase):
    eauth_creds = {
        'username': 'saltdev_auto',
        'password': 'saltdev',
        'eauth': 'auto',
    }

    def setUp(self):
        '''
        Set up a NetapiClient instance
        '''
        opts = salt.config.client_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        self.netapi = salt.netapi.NetapiClient(opts)

    def tearDown(self):
        del self.netapi

    def test_local(self):
        low = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'timeout': 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test
        # runner's proxy minion is running, and we're not testing proxy
        # minions here anyway, just remove it from the response.
        ret.pop('proxytest', None)
        self.assertEqual(ret, {'minion': True, 'sub_minion': True})

    def test_local_batch(self):
        low = {'client': 'local_batch', 'tgt': '*', 'fun': 'test.ping', 'timeout': 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        rets = []
        for _ret in ret:
            rets.append(_ret)
        self.assertIn({'sub_minion': True}, rets)
        self.assertIn({'minion': True}, rets)

    def test_local_async(self):
        low = {'client': 'local_async', 'tgt': '*', 'fun': 'test.ping'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn('jid', ret)
        ret.pop('jid', None)
        ret['minions'] = sorted(ret['minions'])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret['minions'].remove('proxytest')
        except ValueError:
            pass
        self.assertEqual(ret, {'minions': sorted(['minion', 'sub_minion'])})

    def test_local_unauthenticated(self):
        low = {'client': 'local', 'tgt': '*', 'fun': 'test.ping'}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    def test_wheel(self):
        low = {'client': 'wheel', 'fun': 'key.list_all'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn('tag', ret)
        ret.pop('tag')

        data = ret.get('data', {})
        self.assertIn('jid', data)
        data.pop('jid', None)

        self.assertIn('tag', data)
        data.pop('tag', None)

        ret.pop('_stamp', None)
        data.pop('_stamp', None)

        self.maxDiff = None
        self.assertTrue(set(['master.pem', 'master.pub']).issubset(set(ret['data']['return']['local'])))

    def test_wheel_async(self):
        # Give this test a little breathing room
        time.sleep(3)
        timeout = 60
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        with salt.utils.event.get_event("master", opts=opts) as event:
            low = {"client": "wheel_async", "fun": "key.list_all"}
            low.update(self.eauth_creds)

            ret = self.netapi.run(low)
            self.assertIn("jid", ret)
            self.assertIn("tag", ret)
            jid = ret['jid']
            start = time.time()
            found_return = False
            while time.time() - start <= timeout:
                evt = event.get_event(tag=ret['tag'])
                if evt is None:
                    continue
                assert 'error' not in evt
                if 'return' in evt:
                    found_return = True
                    assert evt['success'] is True
                    break
            assert found_return is True

    def test_wheel_async_unauthenticated(self):
        """
        This is a test for CVE-2021-25281
        """
        # Give this test a little breathing room
        time.sleep(3)
        opts = salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        with salt.utils.event.get_event("master", opts=opts) as event:
            low = {"client": "wheel_async", "fun": "key.list_all"}
            low.update({
                "eauth": "pam",
                "username": "notvalid",
                "password": "notvalid",
            })
            ret = self.netapi.run(low)
            self.assertIn("jid", ret)
            self.assertIn("tag", ret)
            jid = ret['jid']
            evt = event.get_event(tag=ret['tag'])
            assert 'error' in evt
            assert evt['error'] == {
                'name': 'EauthAuthenticationError',
                'message': 'Authentication failure of type "eauth" occurred for user notvalid.'
            }

    def test_wheel_unauthenticated(self):
        low = {'client': 'wheel', 'tgt': '*', 'fun': 'test.ping'}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    @skipIf(True, 'This is not testing anything. Skipping for now.')
    def test_runner(self):
        # TODO: fix race condition in init of event-- right now the event class
        # will finish init even if the underlying zmq socket hasn't connected yet
        # this is problematic for the runnerclient's master_call method if the
        # runner is quick
        #low = {'client': 'runner', 'fun': 'cache.grains'}
        low = {'client': 'runner', 'fun': 'test.sleep', 'arg': [2]}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    @skipIf(True, 'This is not testing anything. Skipping for now.')
    def test_runner_async(self):
        low = {'client': 'runner', 'fun': 'cache.grains'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    def test_runner_unauthenticated(self):
        low = {'client': 'runner', 'tgt': '*', 'fun': 'test.ping'}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)


@requires_sshd_server
class NetapiSSHClientTest(SSHCase):
    eauth_creds = {
        'username': 'saltdev_auto',
        'password': 'saltdev',
        'eauth': 'auto',
    }

    def setUp(self):
        '''
        Set up a NetapiClient instance
        '''
        opts = salt.config.client_config(os.path.join(TMP_CONF_DIR, 'master'))
        self.netapi = salt.netapi.NetapiClient(opts)
        opts = salt.config.client_config(os.path.join(TMP_CONF_DIR, "master"))
        naopts = copy.deepcopy(opts)
        naopts["ignore_host_keys"] = True
        self.netapi = salt.netapi.NetapiClient(naopts)

        self.priv_file = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'key_test')
        self.rosters = os.path.join(RUNTIME_VARS.TMP_CONF_DIR)
        self.roster_file = os.path.join(self.rosters, "roster")

        # Initialize salt-ssh
        self.run_function('test.ping')

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

    def test_ssh(self):
        low = {'client': 'ssh',
               'tgt': 'localhost',
               'fun': 'test.ping',
               'ignore_host_keys': True,
               'roster_file': 'roster',
               'rosters': [self.rosters],
               'ssh_priv': self.priv_file}

        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        self.assertIn('localhost', ret)
        self.assertIn('return', ret['localhost'])
        self.assertEqual(ret['localhost']['return'], True)
        self.assertEqual(ret['localhost']['id'], 'localhost')
        self.assertEqual(ret['localhost']['fun'], 'test.ping')

    def test_ssh_unauthenticated(self):
        low = {'client': 'ssh', 'tgt': 'localhost', 'fun': 'test.ping'}

        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

    def test_ssh_unauthenticated_raw_shell_curl(self):

        fun = '-o ProxyCommand curl {0}'.format(self.post_web_root)
        low = {'client': 'ssh',
               'tgt': 'localhost',
               'fun': fun,
               'raw_shell': True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(self.post_web_handler.received_requests, [])
        self.assertEqual(ret, None)

    def test_ssh_unauthenticated_raw_shell_touch(self):

        badfile = os.path.join(TMP, 'badfile.txt')
        fun = '-o ProxyCommand touch {0}'.format(badfile)
        low = {'client': 'ssh',
               'tgt': 'localhost',
               'fun': fun,
               'raw_shell': True}

        ret = None
        with self.assertRaises(EauthAuthenticationError) as excinfo:
            ret = self.netapi.run(low)

        self.assertEqual(ret, None)
        self.assertFalse(os.path.exists('badfile.txt'))

    def test_ssh_authenticated_raw_shell_disabled(self):

        badfile = os.path.join(TMP, 'badfile.txt')
        fun = '-o ProxyCommand touch {0}'.format(badfile)
        low = {'client': 'ssh',
               'tgt': 'localhost',
               'fun': fun,
               'raw_shell': True}

        low.update(self.eauth_creds)

        ret = None
        with patch.dict(self.netapi.opts,
                        {'netapi_allow_raw_shell': False}):
            with self.assertRaises(EauthAuthenticationError) as excinfo:
                ret = self.netapi.run(low)

        self.assertEqual(ret, None)
        self.assertFalse(os.path.exists('badfile.txt'))

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
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "www.zerodayinitiative.com",
            "ssh_priv": "aaa|id>{} #".format(path),
            "fun": "test.ping",
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
        }
        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))

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
            "roster_file": "/tmp/salt-tests-tmpdir/config/roster",
            "rosters": "/",
            "fun": "test.ping",
            "eauth": "auto",
            "username": "saltdev_auto",
            "password": "saltdev",
        }
        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))

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
        self.assertFalse(os.path.exists(path))

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
        }
        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))

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
        }
        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))


@requires_sshd_server
class NetapiSSHClientAuthTest(SSHCase, ModuleCase):

    USERA = "saltdev"
    USERA_PWD = "saltdev"

    def setUp(self):
        """
        Set up a NetapiClient instance
        """
        opts = salt.config.client_config(os.path.join(TMP_CONF_DIR, "master"))
        naopts = copy.deepcopy(opts)
        naopts["ignore_host_keys"] = True
        self.netapi = salt.netapi.NetapiClient(naopts)

        self.priv_file = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "key_test")
        self.rosters = os.path.join(RUNTIME_VARS.TMP_CONF_DIR)
        self.roster_file = os.path.join(self.rosters, "roster")
        # Initialize salt-ssh
        self.run_function("test.ping")
        try:
            add_user = ModuleCase.run_function(self,
                "user.add", [self.USERA], createhome=False
            )
            self.assertTrue(add_user)
            if salt.utils.platform.is_darwin():
                hashed_password = self.USERA_PWD
            else:
                hashed_password = salt.utils.pycrypto.gen_hash(password=self.USERA_PWD)
            add_pwd = ModuleCase.run_function(self,
                "shadow.set_password", [self.USERA, hashed_password],
            )
            self.assertTrue(add_pwd)
        except AssertionError:
            ModuleCase.run_function(self, "user.delete", [self.USERA], remove=True)
            self.skipTest("Could not add user or password, skipping test")
        self.expfile = os.path.join(RUNTIME_VARS.TMP, "exploited")

    def tearDown(self):
        try:
            os.remove(self.expfile)
        except OSError:
            pass
        del self.expfile
        del self.netapi
        ModuleCase.run_function(self, "user.delete", [self.USERA], remove=True)

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

    @staticmethod
    def cleanup_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

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
            "thin_extra_mods": "';touch {0};'".format(path)
        }

        ret = self.netapi.run(low)
        self.assertFalse(os.path.exists(path))

    def test_ssh_auth_bypass(self):
        """
        CVE-2020-25592 - Bogus eauth raises exception.
        """
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": "127.0.0.1",
            "renderer": "cheetah",
            "fun": "test.ping",
            "roster_file": self.roster_file,
            "rosters": "/",
            "eauth": "xx",
        }
        with self.assertRaises(salt.exceptions.EauthAuthenticationError):
            ret = self.netapi.run(low)

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
            'ssh_options': ['ProxyCommand="touch {}"'.format(self.expfile),]
        }
        ret = self.netapi.run(low)
        assert not os.path.exists(self.expfile)

