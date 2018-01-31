# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.netscaler as netscaler


class MockJson(Exception):
    '''
    Mock Json class
    '''
    @staticmethod
    def loads(content):
        '''
        Mock loads method
        '''
        return content

    @staticmethod
    def dumps(dumps):
        '''
        Mock dumps method
        '''
        return dumps


class MockNSNitroError(Exception):
    '''
    Mock NSNitroError class
    '''
    def __init__(self, message='error'):
        self._message = message
        super(MockNSNitroError, self).__init__(self.message)

    def _get_message(self):
        '''
        get_message method
        '''
        return self._message

    def _set_message(self, message):
        '''
        set_message method
        '''
        self._message = message
    message = property(_get_message, _set_message)


class MockNSNitro(object):
    '''
    Mock NSNitro class
    '''
    flag = None

    def __init__(self, host, user, passwd, bol):
        pass

    @staticmethod
    def login():
        '''
        Mock login method
        '''
        return True

    @staticmethod
    def logout():
        '''
        Mock logout method
        '''
        return True


class MockNSServiceGroup(object):
    '''
    Mock NSServiceGroup class
    '''
    def __init__(self):
        self.sg_name = None

    def set_servicegroupname(self, sg_name):
        '''
        Mock set_servicegroupname method
        '''
        self.sg_name = sg_name
        return MockNSServiceGroup()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroup()

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroup()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroup()

    @staticmethod
    def get_servers(obj, servicegroup):
        '''
        Mock get_servers method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return [MockNSServiceGroup()]

    @staticmethod
    def enable_server(obj, servicegroup):
        '''
        Mock enable_server method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroup()

    @staticmethod
    def disable_server(obj, servicegroup):
        '''
        Mock disable_server method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroup()

    @staticmethod
    def get_servername():
        '''
        Mock get_servername method
        '''
        return 'serviceGroupName'

    @staticmethod
    def get_state():
        '''
        Mock get_state method
        '''
        return 'ENABLED'

    @staticmethod
    def get_servicetype():
        '''
        Mock get_servicetype method
        '''
        return ''

    @staticmethod
    def set_servicetype(bol):
        '''
        Mock set_servicetype method
        '''
        return bol


class MockNSServiceGroupServerBinding(object):
    '''
    Mock NSServiceGroupServerBinding class
    '''
    def __init__(self):
        self.sg_name = None

    def set_servername(self, sg_name):
        '''
        Mock set_servername method
        '''
        self.sg_name = sg_name
        return MockNSServiceGroupServerBinding()

    def set_servicegroupname(self, sg_name):
        '''
        Mock set_servicegroupname method
        '''
        self.sg_name = sg_name
        return MockNSServiceGroupServerBinding()

    def set_port(self, sg_name):
        '''
        Mock set_port method
        '''
        self.sg_name = sg_name
        return MockNSServiceGroupServerBinding()

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroupServerBinding()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSServiceGroupServerBinding()


class MockNSService(object):
    '''
    Mock NSService class
    '''
    def __init__(self):
        self.sg_name = None

    def set_name(self, sg_name):
        '''
        Mock set_name method
        '''
        self.sg_name = sg_name
        return MockNSService()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSService()

    @staticmethod
    def enable(obj, servicegroup):
        '''
        Mock enable method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSService()

    @staticmethod
    def disable(obj, servicegroup):
        '''
        Mock disable method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSService()

    @staticmethod
    def get_svrstate():
        '''
        Mock get_svrstate method
        '''
        return 'UP'


class MockNSServer(object):
    '''
    Mock NSServer class
    '''
    flag = None

    def __init__(self):
        self.sg_name = None

    def set_name(self, sg_name):
        '''
        Mock set_name method
        '''
        self.sg_name = sg_name
        return MockNSServer()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        return MockNSServer()

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        return MockNSServer()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        return MockNSServer()

    @staticmethod
    def update(obj, servicegroup):
        '''
        Mock update method
        '''
        return MockNSServer()

    @staticmethod
    def enable(obj, servicegroup):
        '''
        Mock enable method
        '''
        return MockNSServer()

    @staticmethod
    def disable(obj, servicegroup):
        '''
        Mock disable method
        '''
        return MockNSServer()

    @staticmethod
    def get_ipaddress():
        '''
        Mock get_ipaddress method
        '''
        return ''

    @staticmethod
    def set_ipaddress(s_ip):
        '''
        Mock set_ipaddress method
        '''
        return s_ip

    def get_state(self):
        '''
        Mock get_state method
        '''
        if self.flag == 1:
            return ''
        elif self.flag == 2:
            return 'DISABLED'
        return 'ENABLED'


class MockNSLBVServer(object):
    '''
    Mock NSLBVServer class
    '''
    def __init__(self):
        self.sg_name = None

    def set_name(self, sg_name):
        '''
        Mock set_name method
        '''
        self.sg_name = sg_name
        return MockNSLBVServer()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        return MockNSLBVServer()

    @staticmethod
    def set_ipv46(v_ip):
        '''
        Mock set_ipv46 method
        '''
        return v_ip

    @staticmethod
    def set_port(v_port):
        '''
        Mock set_port method
        '''
        return v_port

    @staticmethod
    def set_servicetype(v_type):
        '''
        Mock set_servicetype method
        '''
        return v_type

    @staticmethod
    def get_ipv46():
        '''
        Mock get_ipv46 method
        '''
        return ''

    @staticmethod
    def get_port():
        '''
        Mock get_port method
        '''
        return ''

    @staticmethod
    def get_servicetype():
        '''
        Mock get_servicetype method
        '''
        return ''

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        return MockNSLBVServer()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        return MockNSLBVServer()


class MockNSLBVServerServiceGroupBinding(object):
    '''
    Mock NSLBVServerServiceGroupBinding class
    '''
    flag = None

    def __init__(self):
        self.sg_name = None

    def set_name(self, sg_name):
        '''
        Mock set_name method
        '''
        self.sg_name = sg_name
        return MockNSLBVServerServiceGroupBinding()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return [MockNSLBVServerServiceGroupBinding()]

    @staticmethod
    def get_servicegroupname():
        '''
        Mock get_servicegroupname method
        '''
        return 'serviceGroupName'

    def set_servicegroupname(self, sg_name):
        '''
        Mock set_servicegroupname method
        '''
        self.sg_name = sg_name
        if self.flag:
            return None
        return MockNSLBVServerServiceGroupBinding()

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSLBVServerServiceGroupBinding()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSLBVServerServiceGroupBinding()


class MockNSSSLVServerSSLCertKeyBinding(object):
    '''
    Mock NSSSLVServerSSLCertKeyBinding class
    '''
    def __init__(self):
        self.sg_name = None

    def set_vservername(self, sg_name):
        '''
        Mock set_vservername method
        '''
        self.sg_name = sg_name
        return MockNSSSLVServerSSLCertKeyBinding()

    @staticmethod
    def get(obj, servicegroup):
        '''
        Mock get method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return [MockNSSSLVServerSSLCertKeyBinding()]

    @staticmethod
    def get_certkeyname():
        '''
        Mock get_certkeyname method
        '''
        return 'serviceGroupName'

    def set_certkeyname(self, sg_name):
        '''
        Mock set_certkeyname method
        '''
        self.sg_name = sg_name
        return MockNSSSLVServerSSLCertKeyBinding()

    @staticmethod
    def add(obj, servicegroup):
        '''
        Mock add method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSSSLVServerSSLCertKeyBinding()

    @staticmethod
    def delete(obj, servicegroup):
        '''
        Mock delete method
        '''
        if MockNSNitro.flag:
            raise MockNSNitroError
        return MockNSSSLVServerSSLCertKeyBinding()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetscalerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.netscaler
    '''
    def setup_loader_modules(self):
        return {
            netscaler: {
                'NSNitro': MockNSNitro,
                'NSServiceGroup': MockNSServiceGroup,
                'NSServiceGroupServerBinding': MockNSServiceGroupServerBinding,
                'NSLBVServerServiceGroupBinding': MockNSLBVServerServiceGroupBinding,
                'NSService': MockNSService,
                'NSServer': MockNSServer,
                'NSLBVServer': MockNSLBVServer,
                'NSNitroError': MockNSNitroError,
                'NSSSLVServerSSLCertKeyBinding': MockNSSSLVServerSSLCertKeyBinding,
            }
        }
    # 'servicegroup_exists' function tests: 1

    def test_servicegroup_exists(self):
        '''
        Tests if it checks if a service group exists
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            MockNSNitro.flag = None
            self.assertTrue(netscaler.servicegroup_exists('serviceGrpName'))

            self.assertFalse(netscaler.servicegroup_exists('serviceGrpName',
                                                           sg_type='HTTP'))

            MockNSNitro.flag = True
            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.servicegroup_exists('serGrpNme'))

    # 'servicegroup_add' function tests: 1

    def test_servicegroup_add(self):
        '''
        Tests if it add a new service group
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.servicegroup_add('serviceGroupName'))

            MockNSNitro.flag = True
            self.assertFalse(netscaler.servicegroup_add('serviceGroupName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.servicegroup_add('serveGrpName'))

    # 'servicegroup_delete' function tests: 1

    def test_servicegroup_delete(self):
        '''
        Tests if it delete a new service group
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            MockNSNitro.flag = None
            self.assertTrue(netscaler.servicegroup_delete('serviceGrpName'))

            mock = MagicMock(side_effect=[None, MockNSServiceGroup()])
            with patch.object(netscaler, '_servicegroup_get', mock):
                MockNSNitro.flag = True
                self.assertFalse(netscaler.servicegroup_delete('srGrpName'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.servicegroup_delete('sGNam'))

    # 'servicegroup_server_exists' function tests: 1

    def test_servicegroup_server_exists(self):
        '''
        Tests if it check if a server:port combination
        is a member of a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.servicegroup_server_exists
                             ('serviceGrpName', 'serverName', 'serverPort'))

    # 'servicegroup_server_up' function tests: 1

    def test_servicegroup_server_up(self):
        '''
        Tests if it check if a server:port combination
        is a member of a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.servicegroup_server_up
                             ('serviceGrpName', 'serverName', 'serverPort'))

    # 'servicegroup_server_enable' function tests: 1

    def test_servicegroup_server_enable(self):
        '''
        Tests if it enable a server:port member of a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.servicegroup_server_enable
                             ('serviceGrpName', 'serverName', 'serverPort'))

            with patch.object(netscaler, '_servicegroup_get_server',
                              MagicMock(return_value=MockNSServiceGroup())):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.servicegroup_server_enable
                                ('servGrpName', 'serverName', 'serPort'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.servicegroup_server_enable
                                     ('serGrpName', 'serverName', 'sPort'))

    # 'servicegroup_server_disable' function tests: 1

    def test_sergrp_server_disable(self):
        '''
        Tests if it disable a server:port member of a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.servicegroup_server_disable
                             ('serviceGrpName', 'serverName', 'serverPort'))

            with patch.object(netscaler, '_servicegroup_get_server',
                              MagicMock(return_value=MockNSServiceGroup())):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.servicegroup_server_disable
                                ('serveGrpName', 'serverName', 'serPort'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.servicegroup_server_disable
                                     ('servGrpName', 'serverName', 'sPort'))

    # 'servicegroup_server_add' function tests: 1

    def test_servicegroup_server_add(self):
        '''
        Tests if it add a server:port member to a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.servicegroup_server_add
                                 ('serGrpName', 'serverName', 'sPort'))

            MockNSNitro.flag = None
            self.assertTrue(netscaler.servicegroup_server_add
                            ('serGrpName', 'serverName', 'serverPort'))

            mock = MagicMock(return_value=
                             MockNSServiceGroupServerBinding())
            with patch.object(netscaler, '_servicegroup_get_server',
                              mock):
                MockNSNitro.flag = True
                self.assertFalse(netscaler.servicegroup_server_add
                                 ('serviceGroupName', 'serverName',
                                  'serPort'))

    # 'servicegroup_server_delete' function tests: 1

    def test_servicegroup_server_delete(self):
        '''
        Tests if it remove a server:port member to a servicegroup
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.servicegroup_server_delete
                                 ('servGrpName', 'serverName', 'sPort'))

            self.assertFalse(netscaler.servicegroup_server_delete
                             ('serviceGroupName', 'serverName',
                              'serverPort'))

            mock = MagicMock(return_value=
                             MockNSServiceGroupServerBinding())
            with patch.object(netscaler, '_servicegroup_get_server',
                              mock):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.servicegroup_server_delete
                                ('serviceGroupName', 'serverName',
                                 'serPort'))

    # 'service_up' function tests: 1

    def test_service_up(self):
        '''
        Tests if it checks if a service is UP
        '''
        mock = MagicMock(return_value=MockNSService())
        with patch.object(netscaler, '_service_get', mock):
            self.assertTrue(netscaler.service_up('serviceGrpName'))

    # 'service_exists' function tests: 1

    def test_service_exists(self):
        '''
        Tests if it checks if a service is UP
        '''
        mock = MagicMock(return_value=MockNSService())
        with patch.object(netscaler, '_service_get', mock):
            self.assertTrue(netscaler.service_exists('serviceGrpName'))

    # 'service_enable' function tests: 1

    def test_service_enable(self):
        '''
        Tests if it enable a service
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.service_enable('serviceGrpName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.service_enable('serviceGrpName'))

                mock = MagicMock(return_value=MockNSService())
                with patch.object(netscaler, '_service_get', mock):
                    self.assertFalse(netscaler.service_enable('serGrpName'))

    # 'service_disable' function tests: 1

    def test_service_disable(self):
        '''
        Tests if it disable a service
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.service_disable('serviceGrpName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.service_disable('serceGrpName'))

                mock = MagicMock(return_value=MockNSService())
                with patch.object(netscaler, '_service_get', mock):
                    self.assertFalse(netscaler.service_disable('seGrpName'))

    # 'server_exists' function tests: 1

    def test_server_exists(self):
        '''
        Tests if it checks if a server exists
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.server_exists('serviceGrpName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.server_exists('serviceGrpName'))

            self.assertFalse(netscaler.server_exists('serviceGrpName',
                                                     ip='1.0.0.1'))

            self.assertFalse(netscaler.server_exists('serviceGrpName',
                                                     s_state='serverName'))

    # 'server_add' function tests: 1

    def test_server_add(self):
        '''
        Tests if it add a server
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.server_add('servGrpName', '1.0.0.1'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.server_add('serviceGrpName',
                                                      '1.0.0.1'))

            mock = MagicMock(return_value=False)
            with patch.object(netscaler, 'server_exists', mock):
                self.assertTrue(netscaler.server_add('serviceGrpName',
                                                     '1.0.0.1'))

    # 'server_delete' function tests: 1

    def test_server_delete(self):
        '''
        Tests if it delete a server
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.server_delete('serviceGrpName'))

            mock = MagicMock(side_effect=[MockNSServer(), None])
            with patch.object(netscaler, '_server_get', mock):
                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.server_delete('serGrpName'))

                self.assertFalse(netscaler.server_delete('serviceGrpName'))

    # 'server_update' function tests: 1

    def test_server_update(self):
        '''
        Tests if it update a server's attributes
        '''
        mock = MagicMock(side_effect=[None, MockNSServer(), MockNSServer(),
                                      MockNSServer()])
        with patch.object(netscaler, '_server_get', mock):
            self.assertFalse(netscaler.server_update('seGrName', '1.0.0.1'))

            self.assertFalse(netscaler.server_update('serGrpName', ''))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.server_update('serGrpName',
                                                         '1.0.0.1'))

            mock = MagicMock(return_value='')
            with patch.dict(netscaler.__salt__, {'config.option': mock}):
                self.assertTrue(netscaler.server_update('serGrpName',
                                                        '1.0.0.1'))

    # 'server_enabled' function tests: 1

    def test_server_enabled(self):
        '''
        Tests if it check if a server is enabled globally
        '''
        mock = MagicMock(return_value=MockNSServer())
        with patch.object(netscaler, '_server_get', mock):
            MockNSServer.flag = None
            self.assertTrue(netscaler.server_enabled('serGrpName'))

    # 'server_enable' function tests: 1

    def test_server_enable(self):
        '''
        Tests if it enables a server globally
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.server_enable('serGrpName'))

            MockNSServer.flag = 1
            self.assertTrue(netscaler.server_enable('serGrpName'))

            mock = MagicMock(side_effect=[MockNSServer(), None])
            with patch.object(netscaler, '_server_get', mock):
                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.server_enable('serGrpName'))

                self.assertFalse(netscaler.server_enable('serGrpName'))

    # 'server_disable' function tests: 1

    def test_server_disable(self):
        '''
        Tests if it disable a server globally
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.server_disable('serGrpName'))

            MockNSServer.flag = 2
            self.assertTrue(netscaler.server_disable('serGrpName'))

            MockNSServer.flag = None
            mock = MagicMock(side_effect=[None, MockNSServer()])
            with patch.object(netscaler, '_server_get', mock):
                self.assertFalse(netscaler.server_disable('serGrpName'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.server_disable('serGrpName'))

    # 'vserver_exists' function tests: 1

    def test_vserver_exists(self):
        '''
        Tests if it checks if a vserver exists
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.vserver_exists('vserverName'))

            self.assertFalse(netscaler.vserver_exists('vserverName',
                                                      v_ip='1.0.0.1'))

            self.assertFalse(netscaler.vserver_exists('vserrName', v_ip='',
                                                      v_port='vserverPort'))

            self.assertFalse(netscaler.vserver_exists('vserrName', v_ip='',
                                                      v_port='',
                                                      v_type='vserverType'))

            mock = MagicMock(return_value=None)
            with patch.object(netscaler, '_vserver_get', mock):
                self.assertFalse(netscaler.vserver_exists('vserverName'))

    # 'vserver_add' function tests: 1

    def test_vserver_add(self):
        '''
        Tests if it add a new lb vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.vserver_add('alex.patate.chaude.443',
                                                   '1.2.3.4', '443', 'SSL'))

            mock = MagicMock(return_value=False)
            with patch.object(netscaler, 'vserver_exists', mock):
                self.assertTrue(netscaler.vserver_add('alex.pae.chaude.443',
                                                      '1.2.3.4', '443',
                                                      'SSL'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.vserver_add('alex.chde.443',
                                                           '1.2.3.4', '443',
                                                           'SSL'))

    # 'vserver_delete' function tests: 1

    def test_vserver_delete(self):
        '''
        Tests if it delete a new lb vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.vserver_delete('alex.pe.chaude.443'))

            mock = MagicMock(side_effect=[None, MockNSLBVServer()])
            with patch.object(netscaler, '_vserver_get', mock):
                self.assertFalse(netscaler.vserver_delete('alex.chade.443'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.vserver_delete('al.cha.443'))

    # 'vserver_servicegroup_exists' function tests: 1

    def test_vser_sergrp_exists(self):
        '''
        Tests if it checks if a servicegroup is tied to a vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.vserver_servicegroup_exists
                            ('vserverName', 'serviceGroupName'))

    # 'vserver_servicegroup_add' function tests: 1

    def test_vserver_servicegroup_add(self):
        '''
        Tests if it bind a servicegroup to a vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            MockNSNitro.flag = None
            self.assertTrue(netscaler.vserver_servicegroup_add
                            ('vserverName', 'serGroupName'))

            mock = MagicMock(side_effect=
                             [MockNSLBVServerServiceGroupBinding(), None])
            with patch.object(netscaler, 'vserver_servicegroup_exists',
                              mock):
                self.assertFalse(netscaler.vserver_servicegroup_add
                                 ('vserName', 'serGroupName'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.vserver_servicegroup_add
                                     ('vName', 'serGroupName'))

    # 'vserver_servicegroup_delete' function tests: 1

    def test_vser_sergrp_delete(self):
        '''
        Tests if it unbind a servicegroup from a vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertFalse(netscaler.vserver_servicegroup_delete
                             ('vservName', 'serGroupName'))

            mock = MagicMock(return_value=
                             MockNSLBVServerServiceGroupBinding())
            with patch.object(netscaler, 'vserver_servicegroup_exists',
                              mock):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.vserver_servicegroup_delete
                                ('vName', 'serGroupName'))

                with patch.object(netscaler, '_connect',
                                  MagicMock(return_value=None)):
                    self.assertFalse(netscaler.vserver_servicegroup_delete
                                     ('vserverName', 'serGroupName'))

    # 'vserver_sslcert_exists' function tests: 1

    def test_vserver_sslcert_exists(self):
        '''
        Tests if it checks if a SSL certificate is tied to a vserver
        '''
        mock = MagicMock(return_value='')
        with patch.dict(netscaler.__salt__, {'config.option': mock}):
            self.assertTrue(netscaler.vserver_sslcert_exists
                            ('vserverName', 'serviceGroupName'))

    # 'vserver_sslcert_add' function tests: 1

    def test_vserver_sslcert_add(self):
        '''
        Tests if it binds a SSL certificate to a vserver
        '''
        mock = MagicMock(side_effect=[MockNSSSLVServerSSLCertKeyBinding(),
                                      None, None])
        with patch.object(netscaler, 'vserver_sslcert_exists', mock):
            self.assertFalse(netscaler.vserver_sslcert_add
                             ('vserName', 'serGroupName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.vserver_sslcert_add
                                 ('vName', 'serGrName'))

            mock = MagicMock(return_value='')
            with patch.dict(netscaler.__salt__, {'config.option': mock}):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.vserver_sslcert_add
                                ('vserverName', 'serGroupName'))

    # 'vserver_sslcert_delete' function tests: 1

    def test_vserver_sslcert_delete(self):
        '''
        Tests if it unbinds a SSL certificate from a vserver
        '''
        mock = MagicMock(side_effect=[None,
                                      MockNSSSLVServerSSLCertKeyBinding(),
                                      MockNSSSLVServerSSLCertKeyBinding()])
        with patch.object(netscaler, 'vserver_sslcert_exists', mock):
            self.assertFalse(netscaler.vserver_sslcert_delete('vName',
                                                              'serGrpName'))

            mock = MagicMock(return_value='')
            with patch.dict(netscaler.__salt__, {'config.option': mock}):
                MockNSNitro.flag = None
                self.assertTrue(netscaler.vserver_sslcert_delete
                                ('vservName', 'serGroupName'))

            with patch.object(netscaler, '_connect',
                              MagicMock(return_value=None)):
                self.assertFalse(netscaler.vserver_sslcert_delete
                                 ('vserverName', 'serGroupName'))
