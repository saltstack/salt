# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jakub Sliva <jakub.sliva@ultimum.io>`
'''

# Import Python Libs
from __future__ import absolute_import
from __future__ import unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salt.modules.zabbix import _params_extend

import salt.states.zabbix_host as zabbix_host
import salt.modules.zabbix as zabbix


AUTH_ID = '0424bd59b807674191e7d77572075f33'
HOST_NAME = 'Linux Server'
HOST_ID = '10178'
GROUP_ID = '2'
GROUP_NAME = 'Linux Servers'
VISIBLE_NAME = 'My Linux Server'

SERVER_URL = 'http://test.url'

EXTRA_ARGS = dict()
EXTRA_ARGS['_connection_user'] = 'test123'
EXTRA_ARGS['_connection_password'] = 'secret'
EXTRA_ARGS['_connection_url'] = SERVER_URL
EXTRA_ARGS['visible_name'] = VISIBLE_NAME
EXTRA_ARGS['inventory'] = [{'serial': 'ASDF1234'}]

DEFINED_OBJ = {
    "host": HOST_NAME,
    "interfaces": [
        {
            "interface1": [
                {"type": "agent"},
                {"main": True},
                {"useip": True},
                {"ip": "192.168.3.1"},
                {"dns": ""},
                {"port": "10050"}
            ]
        }
    ],
    "groups": [
        GROUP_NAME
    ]
}

COMPARISON_CREATE = (
                    'host.create',
                    {'host': HOST_NAME,
                     'groups': [{'groupid': int(GROUP_ID)}],
                     'interfaces': [{
                         'type': '1',
                         'main': '1',
                         'useip': '1',
                         'ip': '192.168.3.1',
                         'dns': '',
                         'port': '10050'}],
                     'proxy_hostid': '0',
                     'inventory': {'serial': 'ASDF1234'},
                     'name': 'My Linux Server'
                     },
                    SERVER_URL,
                    AUTH_ID
                    )

CREATE_RETURN = {'result': {'hostids': ['107819']}, 'id': '0', 'jsonrpc': '2.0'}

HOST_GET_EXISTS_RETURN = {
    'jsonrpc': '2.0',
    'result': [
        {
            'hostid': HOST_ID,
            'proxy_hostid': '0',
            'inventory': (
                {'serial': 'ASDF1234'}
            )
        }
    ]
}
HOSTGROUP_GET_EXISTS_RETURN = {
    'jsonrpc': '2.0',
    'result': [
        {
            'groupid': GROUP_ID
        }
    ]
}

HOSTINTERFACE_GET_EXISTS_RETURN = {
    'jsonrpc': '2.0',
    'result': [
        {
                'interfaceid': '1234',
                'hostid': HOST_ID,
                'main': '1',
                'type': '1',
                'useip': '1',
                'ip': '192.168.3.1',
                'dns': '',
                'port': '10050',
                'bulk': '1'
         }
    ]
}

HOSTINVENTORY_GET_EXISTS_RETURN = {
    'jsonrpc': '2.0',
    'result': [
        {
            'hostid': HOST_ID,

        }
    ]
}

SUBSTITUTE_PARAMS_CREATE = []

@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZabbixHostTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {zabbix_host: {}}

    def test_present_create(self):
        '''
        Test to ensure that host is created
        '''
        ret = {'name': HOST_NAME, 'changes': {}, 'result': False, 'comment': ''}

        def side_effect_run_query(*args, **kwargs):
            '''
            Differentiate between __salt__ exec module function calls with different parameters.
            '''

            if args[0] == 'host.get':
                return []
            elif args[0] == 'hostgroup.get':
                return HOSTGROUP_GET_EXISTS_RETURN
            elif args[0] == 'host.create':
                self.assertEqual(args, COMPARISON_CREATE)
                return CREATE_RETURN

        def side_effect_login(**kwargs):
            args = kwargs
            args['url'] = args['_connection_url']
            args['user'] = args['_connection_user']
            args['password'] = args['_connection_password']
            args['auth'] = AUTH_ID
            return args

        with patch.dict(zabbix_host.__opts__, {'test': False}):
            with patch.object(zabbix, '_query', side_effect=side_effect_run_query):
                with patch.object(zabbix, '_login', side_effect=side_effect_login):
                    with patch.dict(zabbix_host.__salt__,
                                    {'zabbix.host_exists': MagicMock(return_value=False),
                                     'zabbix.host_create': MagicMock(side_effect=zabbix.host_create),
                                     'zabbix.hostgroup_get': MagicMock(side_effect=zabbix.hostgroup_get)}):
                        ret['result'] = True
                        ret['comment'] = 'Host {0} created.'.format(HOST_NAME)
                        ret['changes'] = {HOST_NAME: {'old': 'Host {0} does not exist.'.format(HOST_NAME),
                                                 'new': 'Host {0} created.'.format(HOST_NAME),
                                                 }
                                          }

                        self.assert_called_once(side_effect_login)
                        self.assert_called_once(side_effect_run_query)
                        self.assertDictEqual(zabbix_host.present(HOST_NAME, DEFINED_OBJ['groups'],
                                                                 DEFINED_OBJ['interfaces'],
                                                                 **EXTRA_ARGS), ret)

    def test_present_exists(self):
        '''
        Test to show host exists in expected state
        '''
        ret = {'name': HOST_NAME, 'changes': {}, 'result': False, 'comment': ''}

        def side_effect_run_query(*args, **kwargs):
            '''
            Differentiate between __salt__ exec module function calls with different parameters.
            '''

            if args[0] == 'host.get':
                return HOST_GET_EXISTS_RETURN
            elif args[0] == 'hostgroup.get':
                return HOSTGROUP_GET_EXISTS_RETURN
            elif args[0] == 'hostinterface.get':
                return HOSTINTERFACE_GET_EXISTS_RETURN
            elif args[0] == 'host.update':
                return ''

        def side_effect_login(**kwargs):
            args = kwargs
            args['url'] = args['_connection_url']
            args['user'] = args['_connection_user']
            args['password'] = args['_connection_password']
            args['auth'] = AUTH_ID
            return args

        with patch.dict(zabbix_host.__opts__, {'test': False}):
            with patch.object(zabbix, '_query', side_effect=side_effect_run_query):
                with patch.object(zabbix, '_login', side_effect=side_effect_login):
                    with patch.dict(zabbix_host.__salt__,
                                    {'zabbix.host_exists': MagicMock(return_value=True),
                                     'zabbix.host_get': MagicMock(side_effect=zabbix.host_get),
                                     'zabbix.hostgroup_get': MagicMock(side_effect=zabbix.hostgroup_get),
                                     'zabbix.hostinterface_get': MagicMock(side_effect=zabbix.hostinterface_get),
                                     'zabbix.host_inventory_get': MagicMock(side_effect=zabbix.host_inventory_get),
                                     'zabbix.host_inventory_set': MagicMock(side_effect=zabbix.host_inventory_set)}):
                        ret['result'] = True
                        ret['comment'] = 'Host {0} already exists.'.format(HOST_NAME)

                        self.assert_called_once(side_effect_login)
                        self.assert_called_once(side_effect_run_query)
                        self.assertDictEqual(zabbix_host.present(HOST_NAME, DEFINED_OBJ['groups'],
                                                                 DEFINED_OBJ['interfaces'],
                                                                 **EXTRA_ARGS), ret)
