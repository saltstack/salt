# -*- coding: utf-8 -*-
"""
unittests for terraform roster
"""
# Import Python libs
from __future__ import absolute_import, unicode_literals

import os.path

# Import Salt Libs
import salt.config
import salt.loader
from salt.roster import terraform

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class TerraformTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.roster.terraform
    """

    def setup_loader_modules(self):
        opts = salt.config.master_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
        )
        utils = salt.loader.utils(opts, whitelist=["roster_matcher"])
        return {terraform: {"__utils__": utils, "__opts__": {}}}

    def test_default_output(self):
        """
        Test the output of a fixture tfstate file wich contains libvirt
        resources.
        """
        tfstate = os.path.join(
            os.path.dirname(__file__), "terraform.data", "terraform.tfstate"
        )
        pki_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "terraform.data")
        )

        with patch.dict(
            terraform.__opts__, {"roster_file": tfstate, "pki_dir": pki_dir}
        ):
            expected_result = {
                "db0": {
                    "host": "192.168.122.174",
                    "user": "root",
                    "passwd": "dbpw",
                    "tty": True,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
                "db1": {
                    "host": "192.168.122.190",
                    "user": "root",
                    "passwd": "dbpw",
                    "tty": True,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
                "web0": {
                    "host": "192.168.122.106",
                    "user": "root",
                    "passwd": "linux",
                    "timeout": 22,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
                "web1": {
                    "host": "192.168.122.235",
                    "user": "root",
                    "passwd": "linux",
                    "timeout": 22,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
            }

            ret = terraform.targets("*")
            self.assertDictEqual(expected_result, ret)

    def test_default_matching(self):
        """
        Test the output of a fixture tfstate file wich contains libvirt
        resources using matching
        """
        tfstate = os.path.join(
            os.path.dirname(__file__), "terraform.data", "terraform.tfstate"
        )
        pki_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "terraform.data")
        )

        with patch.dict(
            terraform.__opts__, {"roster_file": tfstate, "pki_dir": pki_dir}
        ):
            expected_result = {
                "web0": {
                    "host": "192.168.122.106",
                    "user": "root",
                    "passwd": "linux",
                    "timeout": 22,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
                "web1": {
                    "host": "192.168.122.235",
                    "user": "root",
                    "passwd": "linux",
                    "timeout": 22,
                    "priv": os.path.join(pki_dir, "ssh", "salt-ssh.rsa"),
                },
            }

            ret = terraform.targets("*web*")
            self.assertDictEqual(expected_result, ret)
