# -*- coding: utf-8 -*-
"""
Test salt-call --proxyid commands

tests.integration.proxy.test_shell
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import json
import logging
import sys

import salt.ext.six as six
import salt.utils.json as json
from tests.support.case import ShellCase
from tests.support.helpers import slowTest
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class ProxyCallerSimpleTestCase(ShellCase):
    """
    Test salt-call --proxyid <proxyid> commands
    """

    RUN_TIMEOUT = 300

    @staticmethod
    def _load_return(ret):
        try:
            return json.loads("\n".join(ret))
        except ValueError:
            log.warning("Failed to JSON decode: '%s'", ret)
            six.reraise(*sys.exc_info())

    @slowTest
    def test_can_it_ping(self):
        """
        Ensure the proxy can ping
        """
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json test.ping",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertEqual(ret["local"], True)

    @slowTest
    def test_list_pkgs(self):
        """
        Package test 1, really just tests that the virtual function capability
        is working OK.
        """
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json pkg.list_pkgs",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertIn("coreutils", ret["local"])
        self.assertIn("apache", ret["local"])
        self.assertIn("redbull", ret["local"])

    @slowTest
    def test_upgrade(self):
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json pkg.upgrade",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertEqual(ret["local"]["coreutils"]["new"], "2.0")
        self.assertEqual(ret["local"]["redbull"]["new"], "1000.99")

    @slowTest
    def test_service_list(self):
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json service.list",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertIn("ntp", ret["local"])

    @slowTest
    def test_service_start(self):
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json service.start samba",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json service.status samba",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertTrue(ret)

    @slowTest
    def test_service_get_all(self):
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json service.get_all",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertIn("samba", ret["local"])

    @slowTest
    def test_grains_items(self):
        ret = self._load_return(
            self.run_call(
                "--proxyid proxytest --out=json grains.items",
                config_dir=RUNTIME_VARS.TMP_PROXY_CONF_DIR,
            )
        )
        self.assertEqual(ret["local"]["kernel"], "proxy")
        self.assertEqual(ret["local"]["kernelrelease"], "proxy")
