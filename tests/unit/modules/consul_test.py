# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import consul
from salt.exceptions import SaltInvocationError


# Globals
consul.__grains__ = {}
consul.__salt__ = {}
consul.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ConsulTestCase(TestCase):
    '''
    Test cases for salt.modules.consul
    '''
    @patch('salt.modules.consul._query')
    def test_list(self, mock_query):
        '''
        List
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.list_(), {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='kv/', query_params={'keys': 'True', 'recurse': 'True'}
        )

        self.assertEqual(
            consul.list_(key='abc', recurse=True), {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='kv/abc', query_params={'keys': 'True', 'recurse': 'True'}
        )

    @patch('salt.modules.consul._query')
    def test_get(self, mock_query):
        '''
        Get
        '''
        mock_query.side_effect = [{
            'comment': {'LockIndex': 0,
                        'ModifyIndex': 20038,
                        'Value': 'IkhlbGxvIFdvcmxkIg==',
                        'Flags': 0,
                        'Key': 'web1/key1',
                        'CreateIndex': 20038},
            'result': True
        }, {
            'comment': [{'LockIndex': 0,
                         'ModifyIndex': 20038,
                         'Value': 'IkhlbGxvIFdvcmxkIg==',
                         'Flags': 0,
                         'Key': 'web1/key1',
                         'CreateIndex': 20038},
                        {'LockIndex': 0,
                         'ModifyIndex': 20039,
                         'Value': 'IkhlbGxvIFdvcmxkIg==',
                         'Flags': 0,
                         'Key': 'web1/key1',
                         'CreateIndex': 20039}],
            'result': True
        }]

        self.assertEqual(
            consul.get(key='web1/key1', decode=False),
            {'comment': {'LockIndex': 0,
                         'ModifyIndex': 20038,
                         'Value': 'IkhlbGxvIFdvcmxkIg==',
                         'Flags': 0,
                         'Key': 'web1/key1',
                         'CreateIndex': 20038},
             'result': True}
        )
        mock_query.assert_called_with(
            function='kv/web1/key1', query_params={}
        )

        # Test decoding and recursion
        self.assertEqual(
            consul.get(key='web1', decode=True, recurse=True, raw=True),
            {'comment': [{'LockIndex': 0,
                          'ModifyIndex': 20038,
                          'Value': '"Hello World"',
                          'Flags': 0,
                          'Key': 'web1/key1',
                          'CreateIndex': 20038},
                         {'LockIndex': 0,
                          'ModifyIndex': 20039,
                          'Value': '"Hello World"',
                          'Flags': 0,
                          'Key': 'web1/key1',
                          'CreateIndex': 20039}],
             'result': True}
        )
        mock_query.assert_called_with(
            function='kv/web1', query_params={'raw': True, 'recurse': True}
        )

    @patch('salt.modules.consul._query')
    @patch('salt.modules.consul.get')
    def test_put(self, mock_get, mock_query):
        '''
        PUT
        '''
        mock_query.return_value = {'comment': 'OK', 'result': True}

        mock_get.return_value = {
            'comment': {
                'LockIndex': 0,
                'ModifyIndex': 20038,
                'Value': '"Hello World"',
                'Flags': 0,
                'Key': 'web1/key1',
                'CreateIndex': 20038
            }, 'result': True
        }

        # Test successful key creation
        self.assertEqual(
            consul.put(key='web/key1', value='Hello World'),
            {'comment': 'Added key `web/key1` with value `Hello World`.',
             'result': True}
        )
        mock_query.assert_called_with(
            data='Hello World', function='kv/web/key1', method='PUT', query_params={}
        )

        # Test cas argument
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.put(key='web/key1', value='Hello World', cas=0),
            {'comment': 'Key `web/key1` exists, index must be non-zero.',
             'result': False}
        )

        self.assertEqual(
            consul.put(key='web/key1', value='Hello World', cas=5),
            {'comment': 'Key `web/key1` exists, but index do not match.',
             'result': False}
        )

        self.assertEqual(
            consul.put(key='web/key1', value='Hello World', cas=20038),
            {'comment': 'Added key `web/key1` with value `Hello World`.',
             'result': True}
        )
        mock_query.assert_called_with(
            data='Hello World', function='kv/web/key1', method='PUT', query_params={'cas': 20038}
        )

        # Test internal service error
        mock_query.return_value = {'comment': '500: Internal Server Error', 'result': False}

        self.assertEqual(
            consul.put(key='web/key1', value='Hello World'),
            {'comment': 'Unable to add key `web/key1` with value `Hello World`: `500: Internal Server Error`',
             'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_delete(self, mock_query):
        '''
        Delete
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.delete(key='web/key1'),
            {'comment': 'Deleted `web/key1` key.', 'result': True}
        )
        mock_query.assert_called_with(
            function='kv/web/key1', method='DELETE', query_params={}
        )

        mock_query.return_value = {'comment': '500: Internal Server Error', 'result': False}

        self.assertEqual(
            consul.delete(key='web/key1'),
            {'comment': 'Unable to delete key `web/key1`: `500: Internal Server Error`',
             'result': False}
        )
        mock_query.assert_called_with(
            function='kv/web/key1', method='DELETE', query_params={}
        )

        # Invalid cas
        self.assertEqual(
            consul.delete(key='web/key1', recurse=True, cas=0),
            {'comment': 'Check and Set Operation value must be greater than 0.',
             'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_checks(self, mock_query):
        '''
        Agent Check
        '''
        mock_query.return_value = {'comments': '', 'result': True}

        self.assertEqual(
            consul.agent_checks(),
            {'comments': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/checks'
        )

    @patch('salt.modules.consul._query')
    def test_agent_services(self, mock_query):
        '''
        Agent Services
        '''
        mock_query.return_value = {'comments': '', 'result': True}

        self.assertEqual(
            consul.agent_services(),
            {'comments': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/services'
        )

    @patch('salt.modules.consul._query')
    def test_agent_members(self, mock_query):
        '''
        Agent Members
        '''
        mock_query.return_value = {'comments': '', 'result': True}

        self.assertEqual(
            consul.agent_members(),
            {'comments': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/members', query_params={}
        )

    @patch('salt.modules.consul._query')
    def test_agent_self(self, mock_query):
        '''
        Agent Self
        '''
        mock_query.return_value = {'comments': '', 'result': True}

        self.assertEqual(
            consul.agent_self(),
            {'comments': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/self'
        )

    @patch('salt.modules.consul._query')
    def test_agent_maintenance(self, mock_query):
        '''
        Agent Maintenance
        '''
        mock_query.return_value = {'comments': '', 'result': True}

        self.assertEqual(
            consul.agent_maintenance(enable=True),
            {'comment': 'Agent maintenance mode `enabled`.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/maintenance', method='PUT', query_params={'enable': True}
        )

        self.assertEqual(
            consul.agent_maintenance(enable=False, reason='For fun'),
            {'comment': 'Agent maintenance mode `disabled`.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/maintenance', method='PUT', query_params={'enable': False, 'reason': 'For fun'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_maintenance(enable=False, reason='For fun'),
            {'comment': 'Unable to change maintenance mode for agent: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_join(self, mock_query):
        '''
        Agent Join
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_join(address='192.168.1.1'),
            {'comment': 'Node `192.168.1.1` joined.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/join/192.168.1.1', query_params={}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_join(address='192.168.1.1'),
            {'comment': 'Node `192.168.1.1` was unable to join: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_leave(self, mock_query):
        '''
        Agent Leave
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_leave(node='node1'),
            {'comment': 'Node `node1` put in leave state.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/force-leave/node1'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_leave(node='node1'),
            {'comment': 'Unable to change state for `node1`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_check_register(self, mock_query):
        '''
        Agent Check Register
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_check_register(
                name='My Check',
                script='/usr/local/bin/check_mem'
            ),
            {'comment': 'Check `My Check` added to agent.', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Interval': '5s', 'Name': 'My Check', 'Script': '/usr/local/bin/check_mem'},
            function='agent/check/register',
            method='PUT'
        )

        # specify multiple health checks
        self.assertRaises(
            SaltInvocationError,
            consul.agent_check_register,
            name='My Check', script='MyScript', http='www.google.com'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_check_register(name='My Check', http='www.google.com'),
            {'comment': 'Unable to add `My Check`check to agent: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_check_deregister(self, mock_query):
        '''
        Agent Check Deregister
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_check_deregister('My Check'),
            {'comment': 'Check `My Check` removed from agent.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/check/deregister/My%20Check'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_check_deregister('My Check'),
            {'comment': 'Unable to remove `My Check` check from agent: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_check_pass(self, mock_query):
        '''
        Agent Check Pass
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_check_pass(check_id='My Check', note='Note'),
            {'comment': 'Check `My Check` marked as passing.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/check/pass/My%20Check', query_params={'note': 'Note'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_check_pass(check_id='My Check', note='Note'),
            {'comment': 'Unable to update check `My Check`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_check_warn(self, mock_query):
        '''
        Agent Check Warn
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_check_warn(check_id='My Check', note='Note'),
            {'comment': 'Check `My Check` marked as warning.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/check/warn/My%20Check', query_params={'note': 'Note'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_check_warn(check_id='My Check', note='Note'),
            {'comment': 'Unable to update check `My Check`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_check_fail(self, mock_query):
        '''
        Agent Check Fail
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_check_fail(check_id='My Check', note='Note'),
            {'comment': 'Check `My Check` marked as critical.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/check/fail/My%20Check', query_params={'note': 'Note'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_check_fail(check_id='My Check', note='Note'),
            {'comment': 'Unable to update check `My Check`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_service_register(self, mock_query):
        '''
        Agent Service Register
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_service_register(name='redis', address="127.0.0.1", check_http="www.google.com"),
            {'comment': 'Service `redis` registered on agent.', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Check': {'Interval': '5s', 'HTTP': 'www.google.com'}, 'Name': 'redis', 'Address': '127.0.0.1'},
            function='agent/service/register',
            method='PUT'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_service_register(name='redis'),
            {'comment': 'Unable to register service `redis`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_service_deregister(self, mock_query):
        '''
        Agent Service Deregister
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_service_deregister(service_id='redis'),
            {'comment': 'Service `redis` removed from agent.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/service/deregister/redis', method='PUT'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_service_deregister(service_id='redis'),
            {'comment': 'Unable to remove service `redis`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_agent_service_maintenance(self, mock_query):
        '''
        Agent Service Maintenance
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.agent_service_maintenance(service_id='redis', enable=True, reason='Finished'),
            {'comment': 'Service `redis` set in maintenance mode.', 'result': True}
        )
        mock_query.assert_called_with(
            function='agent/service/maintenance/redis',
            query_params={'reason': 'Finished', 'enable': True}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.agent_service_maintenance(service_id='redis',),
            {'comment': 'Unable to set service `redis` to maintenance mode: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_session_create(self, mock_query):
        '''
        Session Create
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.session_create(name='MySession', node='node1', ttl='3600s'),
            {'comment': 'Created session `MySession`', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Node': 'node1', 'Name': 'MySession', 'TTL': '3600s'},
            function='session/create',
            method='PUT'
        )

        # specify incorrect behaviour
        self.assertEqual(
            consul.session_create(name='MySession', node='node1', behavior='abc'),
            {'comment': 'Behavior must be either delete or release.', 'result': False}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.session_create(name='MySession', node='node1', ttl='3600s'),
            {'comment': 'Unable to create session `MySession`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_session_list(self, mock_query):
        '''
        Session List
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.session_list(datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='session/list',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_session_destroy(self, mock_query):
        '''
        Session Destroy
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.session_destroy(session='abc', datacenter='asg'),
            {'comment': 'Session destroyed `abc`', 'result': True}
        )
        mock_query.assert_called_with(
            function='session/destroy/abc',
            query_params={'dc': 'asg'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.session_destroy(session='abc', datacenter='asg'),
            {'comment': 'Unable to destroy session `abc`: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_session_info(self, mock_query):
        '''
        Session Info
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.session_info(session='abc', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='session/info/abc',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_register(self, mock_query):
        '''
        Catalog Register
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_register(node='node1',
                                    address='192.168.1.1',
                                    service='redis',
                                    service_address='127.0.0.1',
                                    service_port='8080',
                                    service_id='redis_server1'),
            {'comment': 'Catalog registration for `node1` successful', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Node': 'node1', 'Service': {'ID': 'redis_server1',
                                               'Port': '8080',
                                               'Service': 'redis',
                                               'Address': '127.0.0.1'},
                  'Address': '192.168.1.1'},
            function='catalog/register',
            method='PUT'
        )

        self.assertEqual(
            consul.catalog_register(node='node1',
                                    address='192.168.1.1',
                                    check='redis',
                                    check_status='passing',
                                    check_service='redis',
                                    check_id='redis',
                                    check_notes='abc'),
            {'comment': 'Catalog registration for `node1` successful', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Node': 'node1', 'Check': {'CheckID': 'redis',
                                             'Status': 'passing',
                                             'Notes': 'abc',
                                             'ServiceID': 'redis',
                                             'Name': 'redis'},
                  'Address': '192.168.1.1'},
            function='catalog/register',
            method='PUT'
        )

        # invalid check status
        self.assertRaises(
            SaltInvocationError,
            consul.catalog_register,
            node='node1',
            address='192.168.1.1',
            check='redis',
            check_status='abc',
            check_service='redis',
            check_id='redis',
            check_notes='abc'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.catalog_register(node='node1',
                                    address='192.168.1.1',
                                    check='redis',
                                    check_status='passing',
                                    check_service='redis',
                                    check_id='redis',
                                    check_notes='abc'),
            {'comment': 'Catalog registration for `node1` failed: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_deregister(self, mock_query):
        '''
        Catalog Deregister
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_deregister(node='node1', service_id='redis_server1', check_id='redis_check1'),
            {'comment': 'Catalog item `node1` removed.', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Node': 'node1', 'CheckID': 'redis_check1', 'ServiceID': 'redis_server1'},
            function='catalog/deregister',
            method='PUT'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.catalog_deregister(node='node1', service_id='redis_server1', check_id='redis_check1'),
            {'comment': 'Removing Catalog item `node1` failed: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_datacenters(self, mock_query):
        '''
        Catalog Datacenters
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_datacenters(),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='catalog/datacenters',
        )

    @patch('salt.modules.consul._query')
    def test_catalog_nodes(self, mock_query):
        '''
        Catalog Nodes
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_nodes(datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='catalog/nodes',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_services(self, mock_query):
        '''
        Catalog Services
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_services(datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='catalog/services',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_service(self, mock_query):
        '''
        Catalog Service
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_service(service='redis', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='catalog/service/redis',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_catalog_node(self, mock_query):
        '''
        Catalog Node
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.catalog_node(node='node1', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='catalog/node/node1',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_health_node(self, mock_query):
        '''
        Health Node
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.health_node(node='node1', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='health/node/node1',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_health_checks(self, mock_query):
        '''
        Health Checks
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.health_checks(service='redis', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='health/checks/redis',
            query_params={'dc': 'asg'}
        )

    @patch('salt.modules.consul._query')
    def test_health_service(self, mock_query):
        '''
        Health Service
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.health_service(service='redis', datacenter='asg', tag='mytag', passing=True),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='health/service/redis',
            query_params={'dc': 'asg', 'tag': 'mytag', 'passing': True}
        )

    @patch('salt.modules.consul._query')
    def test_health_state(self, mock_query):
        '''
        Health State
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.health_state(state='any', datacenter='asg'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='health/state/any',
            query_params={'dc': 'asg'}
        )

        # specify invalid  state
        self.assertEqual(
            consul.health_state(state='abc', datacenter='asg'),
            {'comment': 'State must be any, unknown, passing, warning, or critical.', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_status_leader(self, mock_query):
        '''
        Status Leader
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.status_leader(),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='status/leader'
        )

    @patch('salt.modules.consul._query')
    def test_status_peers(self, mock_query):
        '''
        Status Peers
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.status_peers(),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='status/peers'
        )

    @patch('salt.modules.consul._query')
    def test_acl_create(self, mock_query):
        '''
        ACL Create
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_create(name='abc', type_='client'),
            {'comment': 'ACL `abc` created.', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Type': 'client', 'Name': 'abc'}, function='acl/create', method='PUT'
        )

        # specify invalid type
        self.assertRaises(
            SaltInvocationError,
            consul.acl_create,
            name='abc',
            type_='abc'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.acl_create(name='abc', type_='client'),
            {'comment': 'Unable to create `abc` ACL token: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_acl_update(self, mock_query):
        '''
        ACL Update
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_update(name='abc', id_='id', type_='client'),
            {'comment': 'ACL `id` updated.', 'result': True}
        )
        mock_query.assert_called_with(
            data={'Type': 'client', 'Name': 'abc', 'ID': 'id'}, function='acl/update', method='PUT'
        )

        # specify an invalid type
        self.assertRaises(
            SaltInvocationError,
            consul.acl_update,
            name='abc',
            id_='id',
            type_='abc'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.acl_update(name='abc', id_='id', type_='client'),
            {'comment': 'Updating ACL `id` failed: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_acl_delete(self, mock_query):
        '''
        ACL Delete
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_delete(id_='abc'),
            {'comment': 'ACL `abc` deleted.', 'result': True}
        )
        mock_query.assert_called_with(
            function='acl/destroy/abc', method='PUT'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.acl_delete(id_='abc'),
            {'comment': 'Removing ACL `abc` failed: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_acl_info(self, mock_query):
        '''
        ACL Info
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_info(id_='abc'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='acl/info/abc'
        )

    @patch('salt.modules.consul._query')
    def test_acl_clone(self, mock_query):
        '''
        ACL Clone
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_clone(id_='abc'),
            {'comment': 'ACL `abc` cloned.', 'result': True}
        )
        mock_query.assert_called_with(
            function='acl/clone/abc', method='PUT'
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.acl_clone(id_='abc'),
            {'comment': 'Cloning ACL `abc` failed: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_acl_list(self, mock_query):
        '''
        ACL List
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.acl_list(),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='acl/list',
        )

    @patch('salt.modules.consul._query')
    def test_event_fire(self, mock_query):
        '''
        Event Fire
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.event_fire(name='abc', datacenter='asg', node='node1'),
            {'comment': 'Event `abc` fired.', 'result': True}
        )
        mock_query.assert_called_with(
            function='event/fire/abc', method='PUT', query_params={'dc': 'asg', 'node': 'node1'}
        )

        # internal server error
        mock_query.return_value = {'comment': '500: Internal', 'result': False}

        self.assertEqual(
            consul.event_fire(name='abc', datacenter='asg', node='node1'),
            {'comment': 'Event `abc` failed to fire: `500: Internal`', 'result': False}
        )

    @patch('salt.modules.consul._query')
    def test_event_list(self, mock_query):
        '''
        Event List
        '''
        mock_query.return_value = {'comment': '', 'result': True}

        self.assertEqual(
            consul.event_list(name='abc', service='redis', tag='tag1'),
            {'comment': '', 'result': True}
        )
        mock_query.assert_called_with(
            function='event/list', query_params={'name': 'abc', 'service': 'redis', 'tag': 'tag1'}
        )
