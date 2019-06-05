# -*- coding: utf-8 -*-
'''
Module for low-level interaction with JbossAS7 through CLI.

This module exposes two ways of interaction with the CLI, either through commands or operations.

.. note:: Following JBoss documentation (https://developer.jboss.org/wiki/CommandLineInterface):
    "Operations are considered a low level but comprehensive way to manage the AS controller, i.e. if it can't be done with operations it can't be done in any other way.
    Commands, on the other hand, are more user-friendly in syntax,
    although most of them still translate into operation requests and some of them even into a few
    composite operation requests, i.e. commands also simplify some management operations from the user's point of view."

The difference between calling a command or operation is in handling the result.
Commands return a zero return code if operation is successful or return non-zero return code and
print an error to standard output in plain text, in case of an error.

Operations return a json-like structure, that contain more information about the result.
In case of a failure, they also return a specific return code. This module parses the output from the operations and
returns it as a dictionary so that an execution of an operation can then be verified against specific errors.

In order to run each function, jboss_config dictionary with the following properties must be passed:
 * cli_path: the path to jboss-cli script, for example: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
 * controller: the IP address and port of controller, for example: 10.11.12.13:9999
 * cli_user: username to connect to jboss administration console if necessary
 * cli_password: password to connect to jboss administration console if necessary

Example:

.. code-block:: yaml

   jboss_config:
      cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
      controller: 10.11.12.13:9999
      cli_user: 'jbossadm'
      cli_password: 'jbossadm'

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import re
import pprint
import time

# Import Salt libs
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def run_command(jboss_config, command, fail_on_error=True):
    '''
    Execute a command against jboss instance through the CLI interface.

    jboss_config
           Configuration dictionary with properties specified above.
    command
           Command to execute against jboss instance
    fail_on_error (default=True)
           Is true, raise CommandExecutionError exception if execution fails.
           If false, 'success' property of the returned dictionary is set to False

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7_cli.run_command '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_command
    '''
    cli_command_result = __call_cli(jboss_config, command)

    if cli_command_result['retcode'] == 0:
        cli_command_result['success'] = True
    else:
        if fail_on_error:
            raise CommandExecutionError('''Command execution failed, return code={retcode}, stdout='{stdout}', stderr='{stderr}' '''.format(**cli_command_result))
        else:
            cli_command_result['success'] = False

    return cli_command_result


def run_operation(jboss_config, operation, fail_on_error=True, retries=1):
    '''
    Execute an operation against jboss instance through the CLI interface.

    jboss_config
           Configuration dictionary with properties specified above.
    operation
           An operation to execute against jboss instance

    fail_on_error (default=True)
           Is true, raise CommandExecutionError exception if execution fails.
           If false, 'success' property of the returned dictionary is set to False
    retries:
           Number of retries in case of "JBAS012144: Could not connect to remote" error.

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7_cli.run_operation '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_operation
    '''
    cli_command_result = __call_cli(jboss_config, operation, retries)

    if cli_command_result['retcode'] == 0:
        if _is_cli_output(cli_command_result['stdout']):
            cli_result = _parse(cli_command_result['stdout'])
            cli_result['success'] = cli_result['outcome'] == 'success'
        else:
            raise CommandExecutionError('Operation has returned unparseable output: {0}'.format(cli_command_result['stdout']))
    else:
        if _is_cli_output(cli_command_result['stdout']):
            cli_result = _parse(cli_command_result['stdout'])
            cli_result['success'] = False
            match = re.search(r'^(JBAS\d+):', cli_result['failure-description'])
            cli_result['err_code'] = match.group(1)
            cli_result['stdout'] = cli_command_result['stdout']
        else:
            if fail_on_error:
                raise CommandExecutionError('''Command execution failed, return code={retcode}, stdout='{stdout}', stderr='{stderr}' '''.format(**cli_command_result))
            else:
                cli_result = {
                    'success': False,
                    'stdout': cli_command_result['stdout'],
                    'stderr': cli_command_result['stderr'],
                    'retcode': cli_command_result['retcode']
                }
    return cli_result


def __call_cli(jboss_config, command, retries=1):
    command_segments = [
        jboss_config['cli_path'],
        '--connect',
        '--controller="{0}"'.format(jboss_config['controller'])
    ]
    if 'cli_user' in six.iterkeys(jboss_config):
        command_segments.append('--user="{0}"'.format(jboss_config['cli_user']))
    if 'cli_password' in six.iterkeys(jboss_config):
        command_segments.append('--password="{0}"'.format(jboss_config['cli_password']))
    command_segments.append('--command="{0}"'.format(__escape_command(command)))
    cli_script = ' '.join(command_segments)

    cli_command_result = __salt__['cmd.run_all'](cli_script)
    log.debug('cli_command_result=%s', cli_command_result)

    log.debug('========= STDOUT:\n%s', cli_command_result['stdout'])
    log.debug('========= STDERR:\n%s', cli_command_result['stderr'])
    log.debug('========= RETCODE: %d', cli_command_result['retcode'])

    if cli_command_result['retcode'] == 127:
        raise CommandExecutionError('Could not execute jboss-cli.sh script. Have you specified server_dir variable correctly?\nCurrent CLI path: {cli_path}. '.format(cli_path=jboss_config['cli_path']))

    if cli_command_result['retcode'] == 1 and 'Unable to authenticate against controller' in cli_command_result['stderr']:
        raise CommandExecutionError('Could not authenticate against controller, please check username and password for the management console. Err code: {retcode}, stdout: {stdout}, stderr: {stderr}'.format(**cli_command_result))

    # It may happen that eventhough server is up it may not respond to the call
    if cli_command_result['retcode'] == 1 and 'JBAS012144' in cli_command_result['stderr'] and retries > 0:  # Cannot connect to cli
        log.debug('Command failed, retrying... (%d tries left)', retries)
        time.sleep(3)
        return __call_cli(jboss_config, command, retries - 1)

    return cli_command_result


def __escape_command(command):
    '''
    This function escapes the command so that can be passed in the command line to JBoss CLI.
    Escaping commands passed to jboss is extremely confusing.
    If you want to save a binding that contains a single backslash character read the following explanation.

    A sample value, let's say "a\b" (with single backslash), that is saved in the config.xml file:
    <bindings>
      <simple name="java:/app/binding1" value="a\b"/>
    </bindings>

    Eventhough it is just a single "\" if you want to read it from command line you will get:

    /opt/jboss/jboss-eap-6.0.1/bin/jboss-cli.sh --connect --controller=ip_addr:9999 --user=user --password=pass --command="/subsystem=naming/binding=\"java:/app/binding1\":read-resource"
    {
       "outcome" => "success",
       "result" => {
           "binding-type" => "simple",
           "value" => "a\\b"
       }
    }

    So, now you have two backslashes in the output, even though in the configuration file you have one.
    Now, if you want to update this property, the easiest thing to do is to create a file with appropriate command:
    /tmp/update-binding.cli:
    ----
    /subsystem=naming/binding="java:/app/binding1":write-attribute(name=value, value="a\\\\b")
    ----
    And run cli command:
    ${JBOSS_HOME}/bin/jboss-cli.sh --connect --controller=ip_addr:9999 --user=user --password=pass --file="/tmp/update-binding.cli"

    As you can see, here you need 4 backslashes to save it as one to the configuration file. Run it and go to the configuration file to check.
    (You may need to reload jboss afterwards:  ${JBOSS_HOME}/bin/jboss-cli.sh --connect --controller=ip_addr:9999 --user=user --password=pass --command=":reload" )

    But if you want to run the same update operation directly from command line, prepare yourself for more escaping:
    ${JBOSS_HOME}/bin/jboss-cli.sh --connect --controller=ip_addr:9999 --user=user --password=pass --command="/subsystem=naming/binding=\"java:/app/binding1\":write-attribute(name=value, value=\"a\\\\\\\\b\")"

    So, here you need 8 backslashes to force JBoss to save it as one.
    To sum up this behavior:
    (1) 1 backslash in configuration file
    (2) 2 backslashes when reading
    (3) 4 backslashes when writing from file
    (4) 8 backslashes when writing from command line
    ... are all the same thing:)

    Remember that the command that comes in is already (3) format. Now we need to escape it further to be able to pass it to command line.
    '''
    result = command.replace('\\', '\\\\')  # replace \ -> \\
    result = result.replace('"', '\\"')     # replace " -> \"
    return result


def _is_cli_output(text):
    cli_re = re.compile(r"^\s*{.+}\s*$", re.DOTALL)
    if cli_re.search(text):
        return True
    else:
        return False


def _parse(cli_output):
    tokens = __tokenize(cli_output)
    result = __process_tokens(tokens)

    log.debug("=== RESULT: "+pprint.pformat(result))
    return result


def __process_tokens(tokens):
    result, token_no = __process_tokens_internal(tokens)
    return result


def __process_tokens_internal(tokens, start_at=0):
    if __is_dict_start(tokens[start_at]) and start_at == 0:  # the top object
        return __process_tokens_internal(tokens, start_at=1)

    log.debug("__process_tokens, start_at=%s", start_at)
    token_no = start_at
    result = {}
    current_key = None
    while token_no < len(tokens):
        token = tokens[token_no]
        log.debug("PROCESSING TOKEN %d: %s", token_no, token)
        if __is_quoted_string(token):
            log.debug("    TYPE: QUOTED STRING ")
            if current_key is None:
                current_key = __get_quoted_string(token)
                log.debug("    KEY: %s", current_key)
            else:
                result[current_key] = __get_quoted_string(token)
                log.debug("    %s -> %s", current_key, result[current_key])
                current_key = None
        elif __is_datatype(token):
            log.debug("    TYPE: DATATYPE: %s ", token)
            result[current_key] = __get_datatype(token)
            log.debug("    %s -> %s", current_key, result[current_key])
            current_key = None
        elif __is_boolean(token):
            log.debug("    TYPE: BOOLEAN ")
            result[current_key] = __get_boolean(token)
            log.debug("    %s -> %s", current_key, result[current_key])
            current_key = None
        elif __is_int(token):
            log.debug("    TYPE: INT ")
            result[current_key] = __get_int(token)
            log.debug("    %s -> %s", current_key, result[current_key])
            current_key = None
        elif __is_long(token):
            log.debug("    TYPE: LONG ")
            result[current_key] = __get_long(token)
            log.debug("    %s -> %s", current_key, result[current_key])
            current_key = None
        elif __is_undefined(token):
            log.debug("    TYPE: UNDEFINED ")
            log.debug("    %s -> undefined (Adding as None to map)", current_key)
            result[current_key] = None
            current_key = None
        elif __is_dict_start(token):
            log.debug("    TYPE: DICT START")
            dict_value, token_no = __process_tokens_internal(tokens, start_at=token_no+1)
            log.debug("    DICT = %s ", dict_value)
            result[current_key] = dict_value
            log.debug("    %s -> %s", current_key, result[current_key])
            current_key = None
        elif __is_dict_end(token):
            log.debug("    TYPE: DICT END")
            return result, token_no
        elif __is_assignment(token):
            log.debug("    TYPE: ASSIGNMENT")
            is_assignment = True
        elif __is_expression(token):
            log.debug("    TYPE: EXPRESSION")
            is_expression = True
        else:
            raise CommandExecutionError('Unknown token! Token: {0}'.format(token))

        token_no = token_no + 1


def __tokenize(cli_output):
    # add all possible tokens here
    # \\ means a single backslash here
    tokens_re = re.compile(r'("(?:[^"\\]|\\"|\\\\)*"|=>|{|}|true|false|undefined|[0-9A-Za-z]+)', re.DOTALL)
    tokens = tokens_re.findall(cli_output)
    log.debug("tokens=%s", tokens)
    return tokens


def __is_dict_start(token):
    return token == '{'


def __is_dict_end(token):
    return token == '}'


def __is_boolean(token):
    return token == 'true' or token == 'false'


def __get_boolean(token):
    return token == 'true'


def __is_int(token):
    return token.isdigit()


def __get_int(token):
    return int(token)


def __is_long(token):
    return token[0:-1].isdigit() and token[-1] == 'L'


def __get_long(token):
    if six.PY2:
        return long(token[0:-1])  # pylint: disable=incompatible-py3-code
    else:
        return int(token[0:-1])


def __is_datatype(token):
    return token in ("INT", "BOOLEAN", "STRING", "OBJECT", "LONG")


def __get_datatype(token):
    return token


def __is_undefined(token):
    return token == 'undefined'


def __is_quoted_string(token):
    return token[0] == '"' and token[-1] == '"'


def __get_quoted_string(token):
    result = token[1:-1]  # remove quotes
    result = result.replace('\\\\', '\\')  # unescape the output, by default all the string are escaped in the output
    return result


def __is_assignment(token):
    return token == '=>'


def __is_expression(token):
    return token == 'expression'
