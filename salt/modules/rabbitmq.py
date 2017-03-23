# -*- coding: utf-8 -*-
'''
Module to provide RabbitMQ compatibility to Salt.
Todo: A lot, need to add cluster support, logging, and minion configuration
data.
'''
from __future__ import absolute_import

# Import python libs
import json
import re
import logging
import os
import os.path
import random
import string

# Import salt libs
import salt.utils
import salt.utils.itertools
import salt.ext.six as six
from salt.exceptions import SaltInvocationError
from salt.ext.six.moves import range
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

RABBITMQCTL = None
RABBITMQ_PLUGINS = None


def __virtual__():
    '''
    Verify RabbitMQ is installed.
    '''
    global RABBITMQCTL
    global RABBITMQ_PLUGINS

    if salt.utils.is_windows():
        from salt.ext.six.moves import winreg
        key = None
        try:
            key = winreg.OpenKeyEx(
                winreg.HKEY_LOCAL_MACHINE,
                'SOFTWARE\\VMware, Inc.\\RabbitMQ Server',
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_32KEY
            )
            (dir_path, value_type) = winreg.QueryValueEx(
                key,
                'Install_Dir'
            )
            if value_type != winreg.REG_SZ:
                raise TypeError('Invalid RabbitMQ Server directory type: {0}'.format(value_type))
            if not os.path.isdir(dir_path):
                raise IOError('RabbitMQ directory not found: {0}'.format(dir_path))
            subdir_match = ''
            for name in os.listdir(dir_path):
                if name.startswith('rabbitmq_server-'):
                    subdir_path = os.path.join(dir_path, name)
                    # Get the matching entry that is last in ASCII order.
                    if os.path.isdir(subdir_path) and subdir_path > subdir_match:
                        subdir_match = subdir_path
            if not subdir_match:
                raise IOError('"rabbitmq_server-*" subdirectory not found in: {0}'.format(dir_path))
            RABBITMQCTL = os.path.join(subdir_match, 'sbin', 'rabbitmqctl.bat')
            RABBITMQ_PLUGINS = os.path.join(subdir_match, 'sbin', 'rabbitmq-plugins.bat')
        except Exception:
            pass
        finally:
            if key is not None:
                winreg.CloseKey(key)
    else:
        RABBITMQCTL = salt.utils.which('rabbitmqctl')
        RABBITMQ_PLUGINS = salt.utils.which('rabbitmq-plugins')

    if not RABBITMQCTL:
        return (False, 'Module rabbitmq: module only works when RabbitMQ is installed')
    return True


def _check_response(response):
    if isinstance(response, dict):
        if response['retcode'] != 0 or response['stderr']:
            raise CommandExecutionError(
                'RabbitMQ command failed: {0}'.format(response['stderr'])
            )
    else:
        if 'Error' in response:
            raise CommandExecutionError(
                'RabbitMQ command failed: {0}'.format(response)
            )


def _format_response(response, msg):
    if isinstance(response, dict):
        if response['retcode'] != 0 or response['stderr']:
            raise CommandExecutionError(
                'RabbitMQ command failed: {0}'.format(response['stderr'])
            )
        else:
            response = response['stdout']
    else:
        if 'Error' in response:
            raise CommandExecutionError(
                'RabbitMQ command failed: {0}'.format(response)
            )
    return {
        msg: response
    }


def _get_rabbitmq_plugin():
    '''
    Returns the rabbitmq-plugin command path if we're running an OS that
    doesn't put it in the standard /usr/bin or /usr/local/bin
    This works by taking the rabbitmq-server version and looking for where it
    seems to be hidden in /usr/lib.
    '''
    global RABBITMQ_PLUGINS

    if RABBITMQ_PLUGINS is None:
        version = __salt__['pkg.version']('rabbitmq-server').split('-')[0]
        RABBITMQ_PLUGINS = ('/usr/lib/rabbitmq/lib/rabbitmq_server-{0}'
                            '/sbin/rabbitmq-plugins').format(version)

    return RABBITMQ_PLUGINS


def _safe_output(line):
    '''
    Looks for rabbitmqctl warning, or general formatting, strings that aren't
    intended to be parsed as output.
    Returns a boolean whether the line can be parsed as rabbitmqctl output.
    '''
    return not any([
        line.startswith('Listing') and line.endswith('...'),
        '...done' in line,
        line.startswith('WARNING:')
    ])


def _strip_listing_to_done(output_list):
    '''
    Conditionally remove non-relevant first and last line,
    "Listing ..." - "...done".
    outputlist: rabbitmq command output split by newline
    return value: list, conditionally modified, may be empty.
    '''
    return [line for line in output_list if _safe_output(line)]


def _output_to_dict(cmdoutput, values_mapper=None):
    '''
    Convert rabbitmqctl output to a dict of data
    cmdoutput: string output of rabbitmqctl commands
    values_mapper: function object to process the values part of each line
    '''
    if isinstance(cmdoutput, dict):
        if cmdoutput['retcode'] != 0 or cmdoutput['stderr']:
            raise CommandExecutionError(
                'RabbitMQ command failed: {0}'.format(cmdoutput['stderr'])
            )
        cmdoutput = cmdoutput['stdout']

    ret = {}
    if values_mapper is None:
        values_mapper = lambda string: string.split('\t')

    # remove first and last line: Listing ... - ...done
    data_rows = _strip_listing_to_done(cmdoutput.splitlines())

    for row in data_rows:
        try:
            key, values = row.split('\t', 1)
        except ValueError:
            # If we have reached this far, we've hit an edge case where the row
            # only has one item: the key. The key doesn't have any values, so we
            # set it to an empty string to preserve rabbitmq reporting behavior.
            # e.g. A user's permission string for '/' is set to ['', '', ''],
            # Rabbitmq reports this only as '/' from the rabbitmqctl command.
            log.debug('Could not find any values for key \'{0}\'. '
                      'Setting to \'{0}\' to an empty string.'.format(row))
            ret[row] = ''
            continue
        ret[key] = values_mapper(values)
    return ret


def _output_to_list(cmdoutput):
    '''
    Convert rabbitmqctl output to a list of strings (assuming whitespace-delimited output).
    Ignores output lines that shouldn't be parsed, like warnings.
    cmdoutput: string output of rabbitmqctl commands
    '''
    return [item for line in cmdoutput.splitlines() if _safe_output(line) for item in line.split()]


def _output_lines_to_list(cmdoutput):
    '''
    Convert rabbitmqctl output to a list of strings (assuming newline-delimited output).
    Ignores output lines that shouldn't be parsed, like warnings.
    cmdoutput: string output of rabbitmqctl commands
    '''
    return [line.strip() for line in cmdoutput.splitlines() if _safe_output(line)]


def list_users(runas=None):
    '''
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_users
    '''
    # Windows runas currently requires a password.
    # Due to this, don't use a default value for
    # runas in Windows.
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'list_users', '-q'],
        runas=runas,
        python_shell=False)

    # func to get tags from string such as "[admin, monitoring]"
    func = lambda string: [x.strip() for x in string[1:-1].split(',')] if ',' in string else [x for x in
                                                                                              string[1:-1].split(' ')]
    return _output_to_dict(res, func)


def list_vhosts(runas=None):
    '''
    Return a list of vhost based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_vhosts
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'list_vhosts', '-q'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return _output_to_list(res['stdout'])


def user_exists(name, runas=None):
    '''
    Return whether the user exists based on rabbitmqctl list_users.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.user_exists rabbit_user
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    return name in list_users(runas=runas)


def vhost_exists(name, runas=None):
    '''
    Return whether the vhost exists based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.vhost_exists rabbit_host
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    return name in list_vhosts(runas=runas)


def add_user(name, password=None, runas=None):
    '''
    Add a rabbitMQ user via rabbitmqctl user_add <user> <password>

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.add_user rabbit_user password
    '''
    clear_pw = False

    if password is None:
        # Generate a random, temporary password. RabbitMQ requires one.
        clear_pw = True
        password = ''.join(random.SystemRandom().choice(
            string.ascii_uppercase + string.digits) for x in range(15))

    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()

    if salt.utils.is_windows():
        # On Windows, if the password contains a special character
        # such as '|', normal execution will fail. For example:
        # cmd: rabbitmq.add_user abc "asdf|def"
        # stderr: 'def' is not recognized as an internal or external
        #         command,\r\noperable program or batch file.
        # Work around this by using a shell and a quoted command.
        python_shell = True
        cmd = '"{0}" add_user "{1}" "{2}"'.format(
            RABBITMQCTL, name, password
        )
    else:
        python_shell = False
        cmd = [RABBITMQCTL, 'add_user', name, password]

    res = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='quiet',
        runas=runas,
        python_shell=python_shell)

    if clear_pw:
        # Now, Clear the random password from the account, if necessary
        try:
            clear_password(name, runas)
        except Exception:
            # Clearing the password failed. We should try to cleanup
            # and rerun and error.
            delete_user(name, runas)
            raise

    msg = 'Added'
    return _format_response(res, msg)


def delete_user(name, runas=None):
    '''
    Deletes a user via rabbitmqctl delete_user.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_user rabbit_user
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'delete_user', name],
        python_shell=False,
        runas=runas)
    msg = 'Deleted'

    return _format_response(res, msg)


def change_password(name, password, runas=None):
    '''
    Changes a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.change_password rabbit_user password
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    if salt.utils.is_windows():
        # On Windows, if the password contains a special character
        # such as '|', normal execution will fail. For example:
        # cmd: rabbitmq.add_user abc "asdf|def"
        # stderr: 'def' is not recognized as an internal or external
        #         command,\r\noperable program or batch file.
        # Work around this by using a shell and a quoted command.
        python_shell = True
        cmd = '"{0}" change_password "{1}" "{2}"'.format(
            RABBITMQCTL, name, password
        )
    else:
        python_shell = False
        cmd = [RABBITMQCTL, 'change_password', name, password]
    res = __salt__['cmd.run_all'](
        cmd,
        runas=runas,
        output_loglevel='quiet',
        python_shell=python_shell)
    msg = 'Password Changed'

    return _format_response(res, msg)


def clear_password(name, runas=None):
    '''
    Removes a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.clear_password rabbit_user
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'clear_password', name],
        runas=runas,
        python_shell=False)
    msg = 'Password Cleared'

    return _format_response(res, msg)


def check_password(name, password, runas=None):
    '''
    .. versionadded:: 2016.3.0

    Checks if a user's password is valid.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.check_password rabbit_user password
    '''
    # try to get the rabbitmq-version - adapted from _get_rabbitmq_plugin

    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()

    try:
        res = __salt__['cmd.run']([RABBITMQCTL, 'status'], runas=runas, python_shell=False)
        server_version = re.search(r'\{rabbit,"RabbitMQ","(.+)"\}', res)

        if server_version is None:
            raise ValueError

        server_version = server_version.group(1)
        version = [int(i) for i in server_version.split('.')]
    except ValueError:
        version = (0, 0, 0)
    if len(version) < 3:
        version = (0, 0, 0)

    # rabbitmq introduced a native api to check a username and password in version 3.5.7.
    if tuple(version) >= (3, 5, 7):
        if salt.utils.is_windows():
            # On Windows, if the password contains a special character
            # such as '|', normal execution will fail. For example:
            # cmd: rabbitmq.add_user abc "asdf|def"
            # stderr: 'def' is not recognized as an internal or external
            #         command,\r\noperable program or batch file.
            # Work around this by using a shell and a quoted command.
            python_shell = True
            cmd = '"{0}" authenticate_user "{1}" "{2}"'.format(
                RABBITMQCTL, name, password
            )
        else:
            python_shell = False
            cmd = [RABBITMQCTL, 'authenticate_user', name, password]

        res = __salt__['cmd.run_all'](
            cmd,
            runas=runas,
            output_loglevel='quiet',
            python_shell=python_shell)

        if res['retcode'] != 0 or res['stderr']:
            return False
        return True

    cmd = ('rabbit_auth_backend_internal:check_user_login'
        '(<<"{0}">>, [{{password, <<"{1}">>}}]).').format(
        name.replace('"', '\\"'),
        password.replace('"', '\\"'))

    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'eval', cmd],
        runas=runas,
        output_loglevel='quiet',
        python_shell=False)
    msg = 'password-check'

    _response = _format_response(res, msg)
    _key = _response.keys()[0]

    if 'invalid credentials' in _response[_key]:
        return False

    return True


def add_vhost(vhost, runas=None):
    '''
    Adds a vhost via rabbitmqctl add_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq add_vhost '<vhost_name>'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'add_vhost', vhost],
        runas=runas,
        python_shell=False)

    msg = 'Added'
    return _format_response(res, msg)


def delete_vhost(vhost, runas=None):
    '''
    Deletes a vhost rabbitmqctl delete_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_vhost '<vhost_name>'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'delete_vhost', vhost],
        runas=runas,
        python_shell=False)
    msg = 'Deleted'
    return _format_response(res, msg)


def set_permissions(vhost, user, conf='.*', write='.*', read='.*', runas=None):
    '''
    Sets permissions for vhost via rabbitmqctl set_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_permissions 'myvhost' 'myuser'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'set_permissions', '-p',
         vhost, user, conf, write, read],
        runas=runas,
        python_shell=False)
    msg = 'Permissions Set'
    return _format_response(res, msg)


def list_permissions(vhost, runas=None):
    '''
    Lists permissions for vhost via rabbitmqctl list_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_permissions '/myvhost'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'list_permissions', '-q', '-p', vhost],
        runas=runas,
        python_shell=False)

    return _output_to_dict(res)


def list_user_permissions(name, runas=None):
    '''
    List permissions for a user via rabbitmqctl list_user_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_user_permissions 'user'.
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'list_user_permissions', name, '-q'],
        runas=runas,
        python_shell=False)

    return _output_to_dict(res)


def set_user_tags(name, tags, runas=None):
    '''Add user tags via rabbitmqctl set_user_tags

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_user_tags 'myadmin' 'administrator'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()

    if tags and isinstance(tags, (list, tuple)):
        tags = ' '.join(tags)

    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'set_user_tags', name, tags],
        runas=runas,
        python_shell=False)
    msg = "Tag(s) set"
    return _format_response(res, msg)


def status(runas=None):
    '''
    return rabbitmq status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.status
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'status'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def cluster_status(runas=None):
    '''
    return rabbitmq cluster_status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.cluster_status
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'cluster_status'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def join_cluster(host, user='rabbit', ram_node=None, runas=None):
    '''
    Join a rabbit cluster

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.join_cluster 'rabbit.example.com' 'rabbit'
    '''
    cmd = [RABBITMQCTL, 'join_cluster']
    if ram_node:
        cmd.append('--ram')
    cmd.append('{0}@{1}'.format(user, host))

    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    stop_app(runas)
    res = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    start_app(runas)

    return _format_response(res, 'Join')


def stop_app(runas=None):
    '''
    Stops the RabbitMQ application, leaving the Erlang node running.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.stop_app
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'stop_app'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def start_app(runas=None):
    '''
    Start the RabbitMQ application.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.start_app
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'start_app'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def reset(runas=None):
    '''
    Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.reset
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'reset'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def force_reset(runas=None):
    '''
    Forcefully Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.force_reset
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'force_reset'],
        runas=runas,
        python_shell=False)
    _check_response(res)
    return res['stdout']


def list_queues(runas=None, *args):
    '''
    Returns queue details of the / virtual host

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [RABBITMQCTL, 'list_queues', '-q']
    cmd.extend(args)
    res = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    _check_response(res)
    return _output_to_dict(res['stdout'])


def list_queues_vhost(vhost, runas=None, *args):
    '''
    Returns queue details of specified virtual host. This command will consider
    first parameter as the vhost name and rest will be treated as
    queueinfoitem. For getting details on vhost ``/``, use :mod:`list_queues
    <salt.modules.rabbitmq.list_queues>` instead).

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [RABBITMQCTL, 'list_queues', '-q', '-p', vhost]
    cmd.extend(args)
    res = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    _check_response(res)
    return _output_to_dict(res['stdout'])


def list_policies(vhost="/", runas=None):
    '''
    Return a dictionary of policies nested by vhost and name
    based on the data returned from rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_policies'
    '''
    ret = {}
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'list_policies', '-q', '-p', vhost],
        runas=runas,
        python_shell=False)
    _check_response(res)
    output = res['stdout']
    for line in _output_lines_to_list(output):
        parts = line.split('\t')
        if len(parts) not in (5, 6):
            continue
        vhost, name = parts[0], parts[1]
        if vhost not in ret:
            ret[vhost] = {}
        ret[vhost][name] = {}
        # How many fields are there? - 'apply_to' was inserted in position
        # 2 at some point
        offset = len(parts) - 5
        if len(parts) == 6:
            ret[vhost][name]['apply_to'] = parts[2]
        ret[vhost][name].update({
            'pattern': parts[offset+2],
            'definition': parts[offset+3],
            'priority': parts[offset+4]
        })

    return ret


def set_policy(vhost, name, pattern, definition, priority=None, runas=None):
    '''
    Set a policy based on rabbitmqctl set_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_policy / HA '.*' '{"ha-mode":"all"}'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    if isinstance(definition, dict):
        definition = json.dumps(definition)
    if not isinstance(definition, six.string_types):
        raise SaltInvocationError(
            'The \'definition\' argument must be a dictionary or JSON string'
        )
    cmd = [RABBITMQCTL, 'set_policy', '-p', vhost]
    if priority:
        cmd.extend(['--priority', priority])
    cmd.extend([name, pattern, definition])
    res = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    log.debug('Set policy: {0}'.format(res['stdout']))
    return _format_response(res, 'Set')


def delete_policy(vhost, name, runas=None):
    '''
    Delete a policy based on rabbitmqctl clear_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_policy / HA'
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    res = __salt__['cmd.run_all'](
        [RABBITMQCTL, 'clear_policy', '-p', vhost, name],
        runas=runas,
        python_shell=False)
    log.debug('Delete policy: {0}'.format(res['stdout']))
    return _format_response(res, 'Deleted')


def policy_exists(vhost, name, runas=None):
    '''
    Return whether the policy exists based on rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.policy_exists / HA
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    policies = list_policies(runas=runas)
    return bool(vhost in policies and name in policies[vhost])


def list_available_plugins(runas=None):
    '''
        Returns a list of the names of all available plugins (enabled and disabled).

        CLI Example:

        .. code-block:: bash

            salt '*' rabbitmq.list_available_plugins
        '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [_get_rabbitmq_plugin(), 'list', '-m']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, runas=runas)
    _check_response(ret)
    return _output_to_list(ret['stdout'])


def list_enabled_plugins(runas=None):
    '''
        Returns a list of the names of the enabled plugins.

        CLI Example:

        .. code-block:: bash

            salt '*' rabbitmq.list_enabled_plugins
        '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [_get_rabbitmq_plugin(), 'list', '-m', '-e']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, runas=runas)
    _check_response(ret)
    return _output_to_list(ret['stdout'])


def plugin_is_enabled(name, runas=None):
    '''
    Return whether the plugin is enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.plugin_is_enabled rabbitmq_plugin_name
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    return name in list_enabled_plugins(runas)


def enable_plugin(name, runas=None):
    '''
    Enable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.enable_plugin foo
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [_get_rabbitmq_plugin(), 'enable', name]
    ret = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    return _format_response(ret, 'Enabled')


def disable_plugin(name, runas=None):
    '''
    Disable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.disable_plugin foo
    '''
    if runas is None and not salt.utils.is_windows():
        runas = salt.utils.get_user()
    cmd = [_get_rabbitmq_plugin(), 'disable', name]
    ret = __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)
    return _format_response(ret, 'Disabled')
