# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
import tempfile
import time

import salt.master
import salt.transport.client
import salt.utils.files
import salt.utils.platform
import salt.utils.user
from tests.support.case import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class ConfigMixin:
    @classmethod
    def setUpClass(cls):
        cls.master_config = AdaptedConfigurationTestCaseMixin.get_config("master")
        cls.minion_config = AdaptedConfigurationTestCaseMixin.get_temp_config(
            "minion",
            id="root",
            transport=cls.master_config["transport"],
            auth_tries=1,
            auth_timeout=5,
            master_ip="127.0.0.1",
            master_port=cls.master_config["ret_port"],
            master_uri="tcp://127.0.0.1:{}".format(cls.master_config["ret_port"]),
        )

        if not salt.utils.platform.is_windows():
            user = cls.master_config["user"]
        else:
            user = salt.utils.user.get_specific_user().replace("\\", "_")
            if user.startswith("sudo_"):
                user = user.split("sudo_")[-1]
        cls.user = user
        cls.keyfile = ".{}_key".format(cls.user)
        cls.keypath = os.path.join(cls.master_config["cachedir"], cls.keyfile)
        with salt.utils.files.fopen(cls.keypath) as keyfd:
            cls.key = keyfd.read()

    @classmethod
    def tearDownClass(cls):
        del cls.master_config
        del cls.minion_config
        del cls.key
        del cls.keyfile
        del cls.keypath


class ClearFuncsAuthTestCase(ConfigMixin, TestCase):
    def test_auth_info_not_allowed(self):
        assert hasattr(salt.master.ClearFuncs, "_prep_auth_info")
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )

        msg = {"cmd": "_prep_auth_info"}
        rets = clear_channel.send(msg, timeout=15)
        ret_key = None
        for ret in rets:
            try:
                ret_key = ret[self.user]
                break
            except (TypeError, KeyError):
                pass
        assert ret_key != self.key, "Able to retrieve user key"


class ClearFuncsPubTestCase(ConfigMixin, TestCase):
    def setUp(self):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, tempdir, ignore_errors=True)
        self.tmpfile = os.path.join(tempdir, "evil_file")

    def tearDown(self):
        self.tmpfile = None

    def test_pub_not_allowed(self):
        assert hasattr(salt.master.ClearFuncs, "_send_pub")
        assert not os.path.exists(self.tmpfile)
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )
        jid = "202003100000000001"
        msg = {
            "cmd": "_send_pub",
            "fun": "file.write",
            "jid": jid,
            "arg": [self.tmpfile, "evil contents"],
            "kwargs": {"show_jid": False, "show_timeout": False},
            "ret": "",
            "tgt": "minion",
            "tgt_type": "glob",
            "user": "root",
        }
        eventbus = salt.utils.event.get_event(
            "master",
            sock_dir=self.master_config["sock_dir"],
            transport=self.master_config["transport"],
            opts=self.master_config,
        )
        ret = clear_channel.send(msg, timeout=15)
        if salt.utils.platform.is_windows():
            time.sleep(30)
            timeout = 30
        else:
            timeout = 5
        ret_evt = None
        start = time.time()
        while time.time() - start <= timeout:
            raw = eventbus.get_event(timeout, auto_reconnect=True)
            if raw and "jid" in raw and raw["jid"] == jid:
                ret_evt = raw
                break
        assert not os.path.exists(self.tmpfile), "Evil file created"


class ClearFuncsConfigTest(ConfigMixin, TestCase):
    def setUp(self):
        self.evil_file_path = os.path.join(
            os.path.dirname(self.master_config["conf_file"]), "evil.conf"
        )

    def tearDown(self):
        try:
            os.remove(self.evil_file_path)
        except OSError:
            pass
        self.evil_file_path = None

    def test_clearfuncs_config(self):
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )

        msg = {
            "key": self.key,
            "cmd": "wheel",
            "fun": "config.update_config",
            "file_name": "../evil",
            "yaml_contents": "win",
        }
        ret = clear_channel.send(msg, timeout=5)
        assert not os.path.exists(
            self.evil_file_path
        ), "Wrote file via directory traversal"
        assert ret["data"]["return"] == "Invalid path"


class ClearFuncsFileRoots(ConfigMixin, TestCase):
    def setUp(self):
        self.file_roots_dir = self.master_config["file_roots"]["base"][0]
        self.target_dir = os.path.dirname(self.file_roots_dir)

    def tearDown(self):
        try:
            os.remove(os.path.join(self.target_dir, "pwn.txt"))
        except OSError:
            pass

    def test_fileroots_write(self):
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )

        msg = {
            "key": self.key,
            "cmd": "wheel",
            "fun": "file_roots.write",
            "data": "win",
            "path": os.path.join("..", "pwn.txt"),
            "saltenv": "base",
        }
        ret = clear_channel.send(msg, timeout=5)
        assert not os.path.exists(
            os.path.join(self.target_dir, "pwn.txt")
        ), "Wrote file via directory traversal"

    def test_fileroots_read(self):
        readpath = os.path.relpath(self.keypath, self.file_roots_dir)
        relative_key_path = os.path.join(self.file_roots_dir, readpath)
        log.debug("Master root_dir: %s", self.master_config["root_dir"])
        log.debug("File Root: %s", self.file_roots_dir)
        log.debug("Key Path: %s", self.keypath)
        log.debug("Read Path: %s", readpath)
        log.debug("Relative Key Path: %s", relative_key_path)
        log.debug("Absolute Read Path: %s", os.path.abspath(relative_key_path))
        # If this asserion fails the test may need to be re-written
        assert os.path.abspath(relative_key_path) == self.keypath
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )
        msg = {
            "key": self.key,
            "cmd": "wheel",
            "fun": "file_roots.read",
            "path": readpath,
            "saltenv": "base",
        }

        ret = clear_channel.send(msg, timeout=5)
        try:
            # When vulnerable this assertion will fail.
            assert (
                list(ret["data"]["return"][0].items())[0][1] != self.key
            ), "Read file via directory traversal"
        except IndexError:
            pass
        # If the vulnerability is fixed, no data will be returned.
        assert ret["data"]["return"] == []


class ClearFuncsTokenTest(ConfigMixin, TestCase):
    def test_token(self):
        tokensdir = os.path.join(self.master_config["cachedir"], "tokens")
        assert os.path.exists(tokensdir), tokensdir
        clear_channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )
        msg = {
            "arg": [],
            "cmd": "get_token",
            "token": os.path.join("..", "minions", "minion", "data.p"),
        }
        ret = clear_channel.send(msg, timeout=5)
        assert "pillar" not in ret, "Read minion data via directory traversal"
