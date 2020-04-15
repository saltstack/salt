# -*- coding: utf-8 -*-
"""
Test salt-call --proxyid commands

tests.integration.proxy.test_shell
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import json
import logging
import sys

# Import Salt Libs
import salt.ext.six as six
import salt.utils.json as json

# Import salt tests libs
from tests.support.case import ShellCase

log = logging.getLogger(__name__)


class ProxyCallerSimpleTestCase(ShellCase):
    """
    Test salt-call --proxyid <proxyid> commands
    """

    @staticmethod
    def _load_return(ret):
        try:
            return json.loads("\n".join(ret))
        except ValueError:
            log.warning("Failed to JSON decode: '%s'", ret)
            six.reraise(*sys.exc_info())

    def test_can_it_ping(self):
        """
        Ensure the proxy can ping
        """
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json test.ping")
        )
        self.assertEqual(ret["local"], True)

    def test_list_pkgs(self):
        """
        Package test 1, really just tests that the virtual function capability
        is working OK.
        """
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json pkg.list_pkgs")
        )
        self.assertIn("coreutils", ret["local"])
        self.assertIn("apache", ret["local"])
        self.assertIn("redbull", ret["local"])

    def test_upgrade(self):
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json pkg.upgrade")
        )
        self.assertEqual(ret["local"]["coreutils"]["new"], "2.0")
        self.assertEqual(ret["local"]["redbull"]["new"], "1000.99")

    def test_service_list(self):
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json service.list")
        )
        self.assertIn("ntp", ret["local"])

    def test_service_start(self):
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json service.start samba")
        )
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json service.status samba")
        )
        self.assertTrue(ret)

    def test_service_get_all(self):
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json service.get_all")
        )
        self.assertIn("samba", ret["local"])

    def test_grains_items(self):
        ret = self._load_return(
            self.run_call("--proxyid proxytest --out=json grains.items")
        )
        self.assertEqual(ret["local"]["kernel"], "proxy")
        self.assertEqual(ret["local"]["kernelrelease"], "proxy")
