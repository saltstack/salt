# -*- coding: utf-8 -*-
import __builtin__
from salt.utils.odict import OrderedDict

from salt.modules import jboss7

from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, NO_MOCK, NO_MOCK_REASON

try:
    # will pass if executed along with other tests
    __salt__
except NameError:
    # if executed separately we need to export __salt__ dictionary ourselves
    __builtin__.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JBoss7TestCase(TestCase):
    jboss_config = {}
    org_run_operation = None

    def setUp(self):
        if 'jboss7_cli.run_operation' in __salt__:
            self.org_run_operation = __salt__['jboss7_cli.run_operation']
        __salt__['jboss7_cli.run_operation'] = MagicMock()

    def tearDown(self):
        if self.org_run_operation is not None:
            __salt__['jboss7_cli.run_operation'] = self.org_run_operation

    def test_create_simple_binding(self):
        jboss7.create_simple_binding(self.jboss_config, 'java:global/env', 'DEV')

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=naming/binding="java:global/env":add(binding-type=simple, value="DEV")')

    def test_create_simple_binding_with_backslash(self):
        jboss7.create_simple_binding(self.jboss_config, 'java:global/env', r'DEV\2')

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, r'/subsystem=naming/binding="java:global/env":add(binding-type=simple, value="DEV\\\\2")')

    def test_update_binding(self):
        jboss7.update_simple_binding(self.jboss_config, 'java:global/env', 'INT')

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=naming/binding="java:global/env":write-attribute(name=value, value="INT")')

    def test_update_binding_with_backslash(self):
        jboss7.update_simple_binding(self.jboss_config, 'java:global/env', r'INT\2')

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, r'/subsystem=naming/binding="java:global/env":write-attribute(name=value, value="INT\\\\2")')

    def test_read_binding(self):
        def cli_command_response(jboss_config, cli_command):
            if cli_command == '/subsystem=naming/binding="java:global/env":read-resource':
                return {'outcome': 'success',
                         'result': {
                             'binding-type': 'simple',
                             'value': 'DEV'
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response

        result = jboss7.read_simple_binding(self.jboss_config, 'java:global/env')
        self.assertEqual(result['outcome'], 'success')
        self.assertEqual(result['result']['value'], 'DEV')

    def test_create_datasource_all_properties_included(self):
        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'driver-name': {'type': 'STRING'},
                                'connection-url': {'type': 'STRING'},
                                'jndi-name': {'type': 'STRING'},
                                'user-name': {'type': 'STRING'},
                                'password': {'type': 'STRING'}
                            }
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response

        datasource_properties = OrderedDict()
        datasource_properties['driver-name'] = 'mysql'
        datasource_properties['connection-url'] = 'jdbc:mysql://localhost:3306/app'
        datasource_properties['jndi-name'] = 'java:jboss/datasources/appDS'
        datasource_properties['user-name'] = 'app'
        datasource_properties['password'] = 'app_password'

        jboss7.create_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=datasources/data-source="appDS":add(driver-name="mysql",connection-url="jdbc:mysql://localhost:3306/app",jndi-name="java:jboss/datasources/appDS",user-name="app",password="app_password")', fail_on_error=False)

    def test_create_datasource_format_boolean_value_when_string(self):
        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'use-ccm': {'type': 'BOOLEAN'}
                            }
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response
        datasource_properties = OrderedDict()
        datasource_properties['use-ccm'] = 'true'

        jboss7.create_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=datasources/data-source="appDS":add(use-ccm=true)', fail_on_error=False)

    def test_create_datasource_format_boolean_value_when_boolean(self):
        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'use-ccm': {'type': 'BOOLEAN'}
                            }
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response
        datasource_properties = OrderedDict()
        datasource_properties['use-ccm'] = True

        jboss7.create_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=datasources/data-source="appDS":add(use-ccm=true)', fail_on_error=False)

    def test_create_datasource_format_int_value_when_int(self):
        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'min-pool-size': {'type': 'INT'}
                            }
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response
        datasource_properties = OrderedDict()
        datasource_properties['min-pool-size'] = 15

        jboss7.create_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=datasources/data-source="appDS":add(min-pool-size=15)', fail_on_error=False)

    def test_create_datasource_format_int_value_when_string(self):
        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'min-pool-size': {'type': 'INT'}
                            }
                        }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response
        datasource_properties = OrderedDict()
        datasource_properties['min-pool-size'] = '15'

        jboss7.create_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_called_with(self.jboss_config, '/subsystem=datasources/data-source="appDS":add(min-pool-size=15)', fail_on_error=False)

    def test_read_datasource(self):
        def cli_command_response(jboss_config, cli_command):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource':
                return {
                    'outcome': 'success',
                    'result': {
                        'driver-name': 'mysql',
                        'connection-url': 'jdbc:mysql://localhost:3306/app',
                        'jndi-name': 'java:jboss/datasources/appDS',
                        'user-name': 'app',
                        'password': 'app_password'
                    }
                }

        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response

        ds_result = jboss7.read_datasource(self.jboss_config, 'appDS')
        ds_properties = ds_result['result']

        self.assertEqual(ds_properties['driver-name'], 'mysql')
        self.assertEqual(ds_properties['connection-url'], 'jdbc:mysql://localhost:3306/app')
        self.assertEqual(ds_properties['jndi-name'], 'java:jboss/datasources/appDS')
        self.assertEqual(ds_properties['user-name'], 'app')
        self.assertEqual(ds_properties['password'], 'app_password')

    def test_update_datasource(self):
        datasource_properties = {'driver-name': 'mysql',
                                 'connection-url': 'jdbc:mysql://localhost:3306/app',
                                 'jndi-name': 'java:jboss/datasources/appDS',
                                 'user-name': 'newuser',
                                 'password': 'app_password'}

        def cli_command_response(jboss_config, cli_command, fail_on_error=False):
            if cli_command == '/subsystem=datasources/data-source="appDS":read-resource-description':
                return {'outcome': 'success',
                        'result': {
                            'attributes': {
                                'driver-name': {'type': 'STRING'},
                                'connection-url': {'type': 'STRING'},
                                'jndi-name': {'type': 'STRING'},
                                'user-name': {'type': 'STRING'},
                                'password': {'type': 'STRING'}
                            }
                        }
                }

            elif cli_command == '/subsystem=datasources/data-source="appDS":read-resource':
                return {
                    'outcome': 'success',
                    'result': {
                        'driver-name': 'mysql',
                        'connection-url': 'jdbc:mysql://localhost:3306/app',
                        'jndi-name': 'java:jboss/datasources/appDS',
                        'user-name': 'app',
                        'password': 'app_password'
                    }
                }

            elif cli_command == '/subsystem=datasources/data-source="appDS":write-attribute(name="user-name",value="newuser")':
                return {
                    'outcome': 'success',
                    'success': True

                }
        __salt__['jboss7_cli.run_operation'].side_effect = cli_command_response

        jboss7.update_datasource(self.jboss_config, 'appDS', datasource_properties)

        __salt__['jboss7_cli.run_operation'].assert_any_call(self.jboss_config, '/subsystem=datasources/data-source="appDS":write-attribute(name="user-name",value="newuser")', fail_on_error=False)
