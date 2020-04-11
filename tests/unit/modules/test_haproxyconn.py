# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.haproxyconn as haproxyconn

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class Mockcmds(object):
    """
    Mock of cmds
    """

    def __init__(self):
        self.backend = None
        self.server = None
        self.weight = None

    def listServers(self, backend):
        """
        Mock of listServers method
        """
        self.backend = backend
        return (
            "Name: server01 Status: UP Weight: 1 bIn: 22 bOut: 12\n"
            "Name: server02 Status: MAINT Weight: 2 bIn: 0 bOut: 0"
        )

    def enableServer(self, server, backend):
        """
        Mock of enableServer method
        """
        self.backend = backend
        self.server = server
        return "server enabled"

    def disableServer(self, server, backend):
        """
        Mock of disableServer method
        """
        self.backend = backend
        self.server = server
        return "server disabled"

    def getWeight(self, server, backend, weight=0):
        """
        Mock of getWeight method
        """
        self.backend = backend
        self.server = server
        self.weight = weight
        return "server weight"

    @staticmethod
    def showFrontends():
        """
        Mock of showFrontends method
        """
        return "frontend-alpha\n" "frontend-beta\n" "frontend-gamma"

    @staticmethod
    def showBackends():
        """
        Mock of showBackends method
        """
        return "backend-alpha\n" "backend-beta\n" "backend-gamma"


class Mockhaproxy(object):
    """
    Mock of haproxy
    """

    def __init__(self):
        self.cmds = Mockcmds()


class MockHaConn(object):
    """
    Mock of HaConn
    """

    def __init__(self, socket=None):
        self.ha_cmd = None

    def sendCmd(self, ha_cmd, objectify=False):
        """
        Mock of sendCmd method
        """
        self.ha_cmd = ha_cmd
        self.objectify = objectify
        return ha_cmd


class HaproxyConnTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.haproxyconn
    """

    def setup_loader_modules(self):
        return {haproxyconn: {"haproxy": Mockhaproxy(), "_get_conn": MockHaConn}}

    # 'list_servers' function tests: 1

    def test_list_servers(self):
        """
        Test list_servers
        """
        self.assertTrue(haproxyconn.list_servers("mysql"))

    # 'enable_server' function tests: 1

    def test_enable_server(self):
        """
        Test enable_server
        """
        self.assertTrue(haproxyconn.enable_server("web1.salt.com", "www"))

    # 'disable_server' function tests: 1

    def test_disable_server(self):
        """
        Test disable_server
        """
        self.assertTrue(haproxyconn.disable_server("db1.salt.com", "mysql"))

    # 'get_weight' function tests: 1

    def test_get_weight(self):
        """
        Test get the weight of a server
        """
        self.assertTrue(haproxyconn.get_weight("db1.salt.com", "mysql"))

    # 'set_weight' function tests: 1

    def test_set_weight(self):
        """
        Test setting the weight of a given server
        """
        self.assertTrue(haproxyconn.set_weight("db1.salt.com", "mysql", weight=11))

    # 'show_frontends' function tests: 1

    def test_show_frontends(self):
        """
        Test print all frontends received from the HAProxy socket
        """
        self.assertTrue(haproxyconn.show_frontends())

    def test_list_frontends(self):
        """
        Test listing all frontends
        """
        self.assertEqual(
            sorted(haproxyconn.list_frontends()),
            sorted(["frontend-alpha", "frontend-beta", "frontend-gamma"]),
        )

    # 'show_backends' function tests: 1

    def test_show_backends(self):
        """
        Test print all backends received from the HAProxy socket
        """
        self.assertTrue(haproxyconn.show_backends())

    def test_list_backends(self):
        """
        Test listing of all backends
        """
        self.assertEqual(
            sorted(haproxyconn.list_backends()),
            sorted(["backend-alpha", "backend-beta", "backend-gamma"]),
        )

    def test_get_backend(self):
        """
        Test get_backend and compare returned value
        """
        expected_data = {
            "server01": {"status": "UP", "weight": 1, "bin": 22, "bout": 12},
            "server02": {"status": "MAINT", "weight": 2, "bin": 0, "bout": 0},
        }
        self.assertDictEqual(haproxyconn.get_backend("test"), expected_data)

    def test_wait_state_true(self):
        """
        Test a successful wait for state
        """
        self.assertTrue(haproxyconn.wait_state("test", "server01"))

    def test_wait_state_false(self):
        """
        Test a failed wait for state, with a timeout of 0
        """
        self.assertFalse(haproxyconn.wait_state("test", "server02", "up", 0))
