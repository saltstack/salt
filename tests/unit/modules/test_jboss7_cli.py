# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import re

# Import salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

# Import salt libs
import salt.modules.jboss7_cli as jboss7_cli
from salt.exceptions import CommandExecutionError


class CmdMock(object):
    commands = []
    command_response_func = None     # if you want to test complete response object (with retcode, stdout and stderr)
    cli_commands = []

    default_response = {'retcode': 0, 'stdout': ''' {
        "outcome" => "success"
    }''', 'stderr': ''}

    def __init__(self, command_response_func=None):
        self.command_response_func = command_response_func

    def run_all(self, command):
        self.commands.append(command)
        if self.command_response_func is not None:
            return self.command_response_func(command)

        cli_command = self.__get_cli_command(command)
        self.cli_commands.append(cli_command)
        return self.default_response

    @staticmethod
    def __get_cli_command(command):
        command_re = re.compile(r'--command=\"\s*(.+?)\s*\"$', re.DOTALL)
        m = command_re.search(command)  # --command has to be the last argument
        if m:
            cli_command = m.group(1)
            return cli_command
        return None

    def get_last_command(self):
        if len(self.commands) > 0:
            return self.commands[-1]
        else:
            return None

    def get_last_cli_command(self):
        if len(self.cli_commands) > 0:
            return self.cli_commands[-1]
        else:
            return None

    def clear(self):
        self.commands = []
        self.command_response_func = None
        self.cli_commands = []


class JBoss7CliTestCase(TestCase, LoaderModuleMockMixin):
    cmd = CmdMock()
    jboss_config = {
        'cli_path': '/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh',
        'controller': '123.234.345.456:9999',
        'instance_name': 'Instance1',
        'cli_user': 'jbossadm',
        'cli_password': 'jbossadm',
        'status_url': 'http://sampleapp.example.com:8080/'
    }

    def setup_loader_modules(self):
        self.cmd = CmdMock()
        self.addCleanup(delattr, self, 'cmd')
        return {
            jboss7_cli: {
                '__salt__': {
                    'cmd.run_all': self.cmd.run_all
                }
            }
        }

    def test_controller_authentication(self):
        jboss7_cli.run_operation(self.jboss_config, 'some cli operation')

        self.assertEqual(self.cmd.get_last_command(), '/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh --connect --controller="123.234.345.456:9999" --user="jbossadm" --password="jbossadm" --command="some cli operation"')

    def test_controller_without_authentication(self):
        jboss_config = {
            'cli_path': '/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh',
            'controller': '123.234.345.456:9999'
        }
        jboss7_cli.run_operation(jboss_config, 'some cli operation')

        self.assertEqual(self.cmd.get_last_command(), '/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh --connect --controller="123.234.345.456:9999" --command="some cli operation"')

    def test_operation_execution(self):
        operation = r'sample_operation'
        jboss7_cli.run_operation(self.jboss_config, operation)

        self.assertEqual(self.cmd.get_last_command(), r'/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh --connect --controller="123.234.345.456:9999" --user="jbossadm" --password="jbossadm" --command="sample_operation"')

    def test_handling_jboss_error(self):
        def command_response(command):
            return {'retcode': 1,
                    'stdout': r'''{
                       "outcome" => "failed",
                       "failure-description" => "JBAS014807: Management resource '[
                       (\"subsystem\" => \"datasources\"),
                       (\"data-source\" => \"non-existing\")
                    ]' not found",
                        "rolled-back" => true,
                        "response-headers" => {"process-state" => "reload-required"}
                    }
                    ''',
                    'stderr': 'some err'}
        self.cmd.command_response_func = command_response

        result = jboss7_cli.run_operation(self.jboss_config, 'some cli command')

        self.assertFalse(result['success'])
        self.assertEqual(result['err_code'], 'JBAS014807')

    def test_handling_cmd_not_exists(self):
        def command_response(command):
            return {'retcode': 127,
                    'stdout': '''Command not exists''',
                    'stderr': 'some err'}
        self.cmd.command_response_func = command_response

        try:
            jboss7_cli.run_operation(self.jboss_config, 'some cli command')
            # should throw an exception
            assert False
        except CommandExecutionError as e:
            self.assertTrue(str(e).startswith('Could not execute jboss-cli.sh script'))

    def test_handling_other_cmd_error(self):
        def command_response(command):
            return {'retcode': 1,
                    'stdout': '''Command not exists''',
                    'stderr': 'some err'}
        self.cmd.command_response_func = command_response

        try:
            jboss7_cli.run_command(self.jboss_config, 'some cli command')
            # should throw an exception
            self.fail('An exception should be thrown')
        except CommandExecutionError as e:
            self.assertTrue(str(e).startswith('Command execution failed'))

    def test_matches_cli_output(self):
        text = '''{
            "key1" => "value1"
            "key2" => "value2"
            }
            '''

        self.assertTrue(jboss7_cli._is_cli_output(text))

    def test_not_matches_cli_output(self):
        text = '''Some error '''

        self.assertFalse(jboss7_cli._is_cli_output(text))

    def test_parse_flat_dictionary(self):
        text = '''{
            "key1" => "value1"
            "key2" => "value2"
            }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(len(result), 2)
        self.assertEqual(result['key1'], 'value1')
        self.assertEqual(result['key2'], 'value2')

    def test_parse_nested_dictionary(self):
        text = '''{
            "key1" => "value1",
            "key2" => {
                "nested_key1" => "nested_value1"
            }
        }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(len(result), 2)
        self.assertEqual(result['key1'], 'value1')
        self.assertEqual(len(result['key2']), 1)
        self.assertEqual(result['key2']['nested_key1'], 'nested_value1')

    def test_parse_string_after_dict(self):
        text = '''{
            "result" => {
                "jta" => true
            },
            "response-headers" => {"process-state" => "reload-required"}
        }'''

        result = jboss7_cli._parse(text)

        self.assertTrue(result['result']['jta'])
        self.assertEqual(result['response-headers']['process-state'], 'reload-required')

    def test_parse_all_datatypes(self):
        text = '''{
            "outcome" => "success",
            "result" => {
                "allocation-retry" => undefined,
                "connection-url" => "jdbc:mysql://localhost:3306/appdb",
                "driver-name" => "mysql",
                "enabled" => false,
                "jta" => true
            },
            "response-headers" => {"process-state" => "reload-required"}
        }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(result['outcome'], 'success')
        self.assertIsNone(result['result']['allocation-retry'])
        self.assertEqual(result['result']['connection-url'], 'jdbc:mysql://localhost:3306/appdb')
        self.assertEqual(result['result']['driver-name'], 'mysql')
        self.assertEqual(result['result']['enabled'], False)
        self.assertTrue(result['result']['jta'])
        self.assertEqual(result['response-headers']['process-state'], 'reload-required')

    def test_multiline_strings_with_escaped_quotes(self):
        text = r'''{
            "outcome" => "failed",
            "failure-description" => "JBAS014807: Management resource '[
            (\"subsystem\" => \"datasources\"),
            (\"data-source\" => \"asc\")
        ]' not found",
            "rolled-back" => true,
            "response-headers" => {"process-state" => "reload-required"}
        }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(result['outcome'], 'failed')
        self.assertTrue(result['rolled-back'])
        self.assertEqual(result['response-headers']['process-state'], 'reload-required')
        self.assertEqual(result['failure-description'], r'''JBAS014807: Management resource '[
            (\"subsystem\" => \"datasources\"),
            (\"data-source\" => \"asc\")
        ]' not found''')

    def test_handling_double_backslash_in_return_values(self):
        text = r'''{
                 "outcome" => "success",
                 "result" => {
                    "binding-type" => "simple",
                    "value" => "DOMAIN\\user"
                   }
                }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(result['outcome'], 'success')
        self.assertEqual(result['result']['binding-type'], 'simple')
        self.assertEqual(result['result']['value'], r'DOMAIN\user')

    def test_numbers_without_quotes(self):
        text = r'''{
                "outcome" => "success",
                "result" => {
                    "min-pool-size" => 1233,
                    "new-connection-sql" => undefined
                }
            }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(result['outcome'], 'success')
        self.assertEqual(result['result']['min-pool-size'], 1233)
        self.assertIsNone(result['result']['new-connection-sql'])

    def test_all_datasource_properties(self):
        text = r'''{
            "outcome" => "success",
            "result" => {
                "allocation-retry" => undefined,
                "allocation-retry-wait-millis" => undefined,
                "allow-multiple-users" => undefined,
                "background-validation" => undefined,
                "background-validation-millis" => undefined,
                "blocking-timeout-wait-millis" => undefined,
                "check-valid-connection-sql" => undefined,
                "connection-properties" => undefined,
                "connection-url" => "jdbc:mysql:thin:@db.example.com",
                "datasource-class" => undefined,
                "driver-class" => undefined,
                "driver-name" => "mysql",
                "enabled" => true,
                "exception-sorter-class-name" => undefined,
                "exception-sorter-properties" => undefined,
                "flush-strategy" => "FailingConnectionOnly",
                "idle-timeout-minutes" => undefined,
                "jndi-name" => "java:/appDS",
                "jta" => true,
                "max-pool-size" => 20,
                "min-pool-size" => 3,
                "new-connection-sql" => undefined,
                "password" => "Password4321",
                "pool-prefill" => undefined,
                "pool-use-strict-min" => undefined,
                "prepared-statements-cache-size" => undefined,
                "query-timeout" => undefined,
                "reauth-plugin-class-name" => undefined,
                "reauth-plugin-properties" => undefined,
                "security-domain" => undefined,
                "set-tx-query-timeout" => false,
                "share-prepared-statements" => false,
                "spy" => false,
                "stale-connection-checker-class-name" => undefined,
                "stale-connection-checker-properties" => undefined,
                "track-statements" => "NOWARN",
                "transaction-isolation" => undefined,
                "url-delimiter" => undefined,
                "url-selector-strategy-class-name" => undefined,
                "use-ccm" => "true",
                "use-fast-fail" => false,
                "use-java-context" => "false",
                "use-try-lock" => undefined,
                "user-name" => "user1",
                "valid-connection-checker-class-name" => undefined,
                "valid-connection-checker-properties" => undefined,
                "validate-on-match" => false,
                "statistics" => {
                    "jdbc" => undefined,
                    "pool" => undefined
                }
            },
            "response-headers" => {"process-state" => "reload-required"}
        }'''

        result = jboss7_cli._parse(text)

        self.assertEqual(result['outcome'], 'success')
        self.assertEqual(result['result']['max-pool-size'], 20)
        self.assertIsNone(result['result']['new-connection-sql'])
        self.assertIsNone(result['result']['url-delimiter'])
        self.assertFalse(result['result']['validate-on-match'])

    def test_datasource_resource_one_attribute_description(self):
        cli_output = '''{
            "outcome" => "success",
            "result" => {
                "description" => "A JDBC data-source configuration",
                "head-comment-allowed" => true,
                "tail-comment-allowed" => true,
                "attributes" => {
                    "connection-url" => {
                        "type" => STRING,
                        "description" => "The JDBC driver connection URL",
                        "expressions-allowed" => true,
                        "nillable" => false,
                        "min-length" => 1L,
                        "max-length" => 2147483647L,
                        "access-type" => "read-write",
                        "storage" => "configuration",
                        "restart-required" => "no-services"
                    }
                },
                "children" => {"connection-properties" => {"description" => "The connection-properties element allows you to pass in arbitrary connection properties to the Driver.connect(url, props) method"}}
            }
        }
        '''
        result = jboss7_cli._parse(cli_output)

        self.assertEqual(result['outcome'], 'success')
        conn_url_attributes = result['result']['attributes']['connection-url']
        self.assertEqual(conn_url_attributes['type'], 'STRING')
        self.assertEqual(conn_url_attributes['description'], 'The JDBC driver connection URL')
        self.assertTrue(conn_url_attributes['expressions-allowed'])
        self.assertFalse(conn_url_attributes['nillable'])
        self.assertEqual(conn_url_attributes['min-length'], 1)
        self.assertEqual(conn_url_attributes['max-length'], 2147483647)
        self.assertEqual(conn_url_attributes['access-type'], 'read-write')
        self.assertEqual(conn_url_attributes['storage'], 'configuration')
        self.assertEqual(conn_url_attributes['restart-required'], 'no-services')

    def test_datasource_complete_resource_description(self):
        cli_output = '''{
            "outcome" => "success",
            "result" => {
                "description" => "A JDBC data-source configuration",
                "head-comment-allowed" => true,
                "tail-comment-allowed" => true,
                "attributes" => {
                    "connection-url" => {
                        "type" => STRING,
                        "description" => "The JDBC driver connection URL",
                        "expressions-allowed" => true,
                        "nillable" => false,
                        "min-length" => 1L,
                        "max-length" => 2147483647L,
                        "access-type" => "read-write",
                        "storage" => "configuration",
                        "restart-required" => "no-services"
                    }
                },
                "children" => {"connection-properties" => {"description" => "The connection-properties element allows you to pass in arbitrary connection properties to the Driver.connect(url, props) method"}}
            }
        }
        '''

        result = jboss7_cli._parse(cli_output)

        self.assertEqual(result['outcome'], 'success')
        conn_url_attributes = result['result']['attributes']['connection-url']
        self.assertEqual(conn_url_attributes['type'], 'STRING')
        self.assertEqual(conn_url_attributes['description'], 'The JDBC driver connection URL')
        self.assertTrue(conn_url_attributes['expressions-allowed'])
        self.assertFalse(conn_url_attributes['nillable'])
        self.assertEqual(conn_url_attributes['min-length'], 1)
        self.assertEqual(conn_url_attributes['max-length'], 2147483647)
        self.assertEqual(conn_url_attributes['access-type'], 'read-write')
        self.assertEqual(conn_url_attributes['storage'], 'configuration')
        self.assertEqual(conn_url_attributes['restart-required'], 'no-services')

    def test_escaping_operation_with_backslashes_and_quotes(self):
        operation = r'/subsystem=naming/binding="java:/sampleapp/web-module/ldap/username":add(binding-type=simple, value="DOMAIN\\\\user")'
        jboss7_cli.run_operation(self.jboss_config, operation)

        self.assertEqual(self.cmd.get_last_command(), r'/opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh --connect --controller="123.234.345.456:9999" --user="jbossadm" --password="jbossadm" --command="/subsystem=naming/binding=\"java:/sampleapp/web-module/ldap/username\":add(binding-type=simple, value=\"DOMAIN\\\\\\\\user\")"')
