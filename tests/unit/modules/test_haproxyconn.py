# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.haproxyconn as haproxyconn

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
class HaproxyConnTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.haproxyconn
    '''
    def setup_loader_modules(self):
        return {haproxyconn: {'haproxy': Mockhaproxy()}}

    # 'list_servers' function tests: 1

    def test_list_servers(self, mock):
        '''
        Test list_servers
        '''
        self.assertTrue(haproxyconn.list_servers('mysql'))

    # 'enable_server' function tests: 1

    def test_enable_server(self, mock):
        '''
        Test enable_server
        '''
        self.assertTrue(haproxyconn.enable_server('web1.salt.com', 'www'))

    # 'disable_server' function tests: 1

    def test_disable_server(self, mock):
        '''
        Test disable_server
        '''
        self.assertTrue(haproxyconn.disable_server('db1.salt.com', 'mysql'))

    # 'get_weight' function tests: 1

    def test_get_weight(self, mock):
        '''
        Test get the weight of a server
        '''
        self.assertTrue(haproxyconn.get_weight('db1.salt.com', 'mysql'))

    # 'set_weight' function tests: 1

    def test_set_weight(self, mock):
        '''
        Test setting the weight of a given server
        '''
        self.assertTrue(haproxyconn.set_weight('db1.salt.com', 'mysql',
                                               weight=11))

    # 'show_frontends' function tests: 1

    def test_show_frontends(self, mock):
        '''
        Test print all frontends received from the HAProxy socket
        '''
        self.assertTrue(haproxyconn.show_frontends())

    # 'show_backends' function tests: 1

    def test_show_backends(self, mock):
        '''
        Test print all backends received from the HAProxy socket
        '''
        self.assertTrue(haproxyconn.show_backends())
