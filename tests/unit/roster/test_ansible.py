# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.config
import salt.loader
import salt.roster.ansible as ansible
from tests.support import mixins

# Import Salt Testing Libs
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

EXPECTED = {
    "host1": {
        "host": "host1",
        "passwd": "test123",
        "minion_opts": {
            "escape_pods": 2,
            "halon_system_timeout": 30,
            "self_destruct_countdown": 60,
            "some_server": "foo.southeast.example.com",
        },
    },
    "host2": {
        "host": "host2",
        "passwd": "test123",
        "minion_opts": {
            "escape_pods": 2,
            "halon_system_timeout": 30,
            "self_destruct_countdown": 60,
            "some_server": "foo.southeast.example.com",
        },
    },
    "host3": {
        "host": "host3",
        "passwd": "test123",
        "minion_opts": {
            "escape_pods": 2,
            "halon_system_timeout": 30,
            "self_destruct_countdown": 60,
            "some_server": "foo.southeast.example.com",
        },
    },
}


@skipIf(
    not salt.utils.path.which("ansible-inventory"),
    "Skipping because ansible-inventory is not available",
)
class AnsibleRosterTestCase(TestCase, mixins.LoaderModuleMockMixin):
    @classmethod
    def setUpClass(cls):
        cls.roster_dir = os.path.join(
            RUNTIME_VARS.TESTS_DIR, "unit/files/rosters/ansible/"
        )
        cls.opts = {"roster_defaults": {"passwd": "test123"}}

    @classmethod
    def tearDownClass(cls):
        delattr(cls, "roster_dir")
        delattr(cls, "opts")

    def setup_loader_modules(self):
        opts = salt.config.master_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
        )
        utils = salt.loader.utils(opts, whitelist=["json", "stringutils"])
        runner = salt.loader.runner(opts, utils=utils, whitelist=["salt"])
        return {ansible: {"__utils__": utils, "__opts__": {}, "__runner__": runner}}

    def test_ini(self):
        self.opts["roster_file"] = os.path.join(self.roster_dir, "roster.ini")
        with patch.dict(ansible.__opts__, self.opts):
            ret = ansible.targets("*")
            assert ret == EXPECTED

    def test_yml(self):
        self.opts["roster_file"] = os.path.join(self.roster_dir, "roster.yml")
        with patch.dict(ansible.__opts__, self.opts):
            ret = ansible.targets("*")
            assert ret == EXPECTED

    def test_script(self):
        self.opts["roster_file"] = os.path.join(self.roster_dir, "roster.py")
        with patch.dict(ansible.__opts__, self.opts):
            ret = ansible.targets("*")
            assert ret == EXPECTED
