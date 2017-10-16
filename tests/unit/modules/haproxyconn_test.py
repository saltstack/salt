# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import haproxyconn

# Globals
haproxyconn.__opts__ = {}


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
        return 'salt'

    def enableServer(self, server, backend):
        """
        Mock of enableServer method
        """
        self.backend = backend
        self.server = server
        return 'server enabled'

    def disableServer(self, server, backend):
        """
        Mock of disableServer method
        """
        self.backend = backend
        self.server = server
        return 'server disabled'

    def getWeight(self, server, backend, weight=0):
        """
        Mock of getWeight method
        """
        self.backend = backend
        self.server = server
        self.weight = weight
        return 'server weight'

    @staticmethod
    def showFrontends():
        """
        Mock of showFrontends method
        """
        return 'server frontend'

    @staticmethod
    def showBackends():
        """
        Mock of showBackends method
        """
        return 'server backend'


class Mockhaproxy(object):
    """
    Mock of haproxy
    """
    def __init__(self):
        self.cmds = Mockcmds()

haproxyconn.haproxy = Mockhaproxy()


class MockHaConn(object):
    """
    Mock of HaConn
    """
    def __init__(self):
        self.ha_cmd = None

    def sendCmd(self, ha_cmd, objectify=False):
        """
        Mock of sendCmd method
        """
        self.ha_cmd = ha_cmd
        self.objectify = objectify
        return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.haproxyconn._get_conn', return_value=MockHaConn())
class HaproxyConnTestCase(TestCase):
    '''
    Test cases for salt.modules.haproxyconn
    '''
    # 'list_servers' function tests: 1

    def test_list_servers(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.list_servers('mysql'))

    # 'enable_server' function tests: 1

    def test_enable_server(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.enable_server('web1.salt.com', 'www'))

    # 'disable_server' function tests: 1

    def test_disable_server(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.disable_server('db1.salt.com', 'mysql'))

    # 'get_weight' function tests: 1

    def test_get_weight(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.get_weight('db1.salt.com', 'mysql'))

    # 'set_weight' function tests: 1

    def test_set_weight(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.set_weight('db1.salt.com', 'mysql',
                                               weight=11))

    # 'show_frontends' function tests: 1

    def test_show_frontends(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.show_frontends())

    # 'show_backends' function tests: 1

    def test_show_backends(self, mock):
        '''
        Test if it get a value from etcd, by direct path
        '''
        self.assertTrue(haproxyconn.show_backends())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HaproxyConnTestCase, needs_daemon=False)
