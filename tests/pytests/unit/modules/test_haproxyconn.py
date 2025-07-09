"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.haproxyconn
"""

import pytest

import salt.modules.haproxyconn as haproxyconn


class Mockcmds:
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
        return "frontend-alpha\nfrontend-beta\nfrontend-gamma"

    @staticmethod
    def showBackends():
        """
        Mock of showBackends method
        """
        return "backend-alpha\nbackend-beta\nbackend-gamma"


class Mockhaproxy:
    """
    Mock of haproxy
    """

    def __init__(self):
        self.cmds = Mockcmds()


class MockHaConn:
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


@pytest.fixture
def configure_loader_modules():
    return {haproxyconn: {"haproxy": Mockhaproxy(), "_get_conn": MockHaConn}}


# 'list_servers' function tests: 1


def test_list_servers():
    """
    Test list_servers
    """
    assert haproxyconn.list_servers("mysql")


# 'enable_server' function tests: 1


def test_enable_server():
    """
    Test enable_server
    """
    assert haproxyconn.enable_server("web1.salt.com", "www")


# 'disable_server' function tests: 1


def test_disable_server():
    """
    Test disable_server
    """
    assert haproxyconn.disable_server("db1.salt.com", "mysql")


# 'get_weight' function tests: 1


def test_get_weight():
    """
    Test get the weight of a server
    """
    assert haproxyconn.get_weight("db1.salt.com", "mysql")


# 'set_weight' function tests: 1


def test_set_weight():
    """
    Test setting the weight of a given server
    """
    assert haproxyconn.set_weight("db1.salt.com", "mysql", weight=11)


# 'show_frontends' function tests: 1


def test_show_frontends():
    """
    Test print all frontends received from the HAProxy socket
    """
    assert haproxyconn.show_frontends()


def test_list_frontends():
    """
    Test listing all frontends
    """
    assert sorted(haproxyconn.list_frontends()) == sorted(
        ["frontend-alpha", "frontend-beta", "frontend-gamma"]
    )


# 'show_backends' function tests: 1


def test_show_backends():
    """
    Test print all backends received from the HAProxy socket
    """
    assert haproxyconn.show_backends()


def test_list_backends():
    """
    Test listing of all backends
    """
    assert sorted(haproxyconn.list_backends()) == sorted(
        ["backend-alpha", "backend-beta", "backend-gamma"]
    )


def test_get_backend():
    """
    Test get_backend and compare returned value
    """
    expected_data = {
        "server01": {"status": "UP", "weight": 1, "bin": 22, "bout": 12},
        "server02": {"status": "MAINT", "weight": 2, "bin": 0, "bout": 0},
    }
    assert haproxyconn.get_backend("test") == expected_data


def test_wait_state_true():
    """
    Test a successful wait for state
    """
    assert haproxyconn.wait_state("test", "server01")


def test_wait_state_false():
    """
    Test a failed wait for state, with a timeout of 0
    """
    assert not haproxyconn.wait_state("test", "server02", "up", 0)
