# -*- coding: utf-8 -*-
'''
Module to provide RabbitMQ compatibility to Salt.
Todo: A lot, need to add cluster support, logging, and minion configuration
data.
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils

# Import python libs
import logging
import random
import string
from salt.ext.six.moves import range

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Verify RabbitMQ is installed.
    '''
    return salt.utils.which('rabbitmqctl') is not None


def _format_response(response, msg):
    if isinstance(response, dict):
        if response['retcode'] != 0:
            msg = 'Error'
        else:
            msg = response['stdout']
    else:
        if 'Error' in response:
            msg = 'Error'
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
    rabbitmq = salt.utils.which('rabbitmq-plugins')

    if rabbitmq is None:
        version = __salt__['pkg.version']('rabbitmq-server').split('-')[0]

        rabbitmq = ('/usr/lib/rabbitmq/lib/rabbitmq_server-{0}'
                    '/sbin/rabbitmq-plugins').format(version)

    return rabbitmq


def _strip_listing_to_done(output_list):
    '''Conditionally remove non-relevant first and last line,
    "Listing ..." - "...done".
    outputlist: rabbitmq command output split by newline
    return value: list, conditionally modified, may be empty.
    '''

    # conditionally remove non-relevant first line
    f_line = ''.join(output_list[:1])
    if f_line.startswith('Listing') and f_line.endswith('...'):
        output_list.pop(0)

    # some versions of rabbitmq have no trailing '...done' line,
    # which some versions do not output.
    l_line = ''.join(output_list[-1:])
    if '...done' in l_line:
        output_list.pop()

    return output_list


def _output_to_dict(cmdoutput, values_mapper=None):
    '''Convert rabbitmqctl output to a dict of data
    cmdoutput: string output of rabbitmqctl commands
    values_mapper: function object to process the values part of each line
    '''
    ret = {}
    if values_mapper is None:
        values_mapper = lambda string: string.split('\t')

    # remove first and last line: Listing ... - ...done
    data_rows = _strip_listing_to_done(cmdoutput.splitlines())

    for row in data_rows:
        key, values = row.split('\t', 1)
        ret[key] = values_mapper(values)
    return ret


def list_users(runas=None):
    '''
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_users
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl list_users',
                              runas=runas)

    # func to get tags from string such as "[admin, monitoring]"
    func = lambda string: set(string[1:-1].split(','))
    return _output_to_dict(res, func)


def list_vhosts(runas=None):
    '''
    Return a list of vhost based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_vhosts
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl list_vhosts',
                              runas=runas)

    # remove first and last line: Listing ... - ...done
    return _strip_listing_to_done(res.splitlines())


def user_exists(name, runas=None):
    '''
    Return whether the user exists based on rabbitmqctl list_users.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.user_exists rabbit_user
    '''
    if runas is None:
        runas = salt.utils.get_user()
    user_list = list_users(runas=runas)
    log.debug(user_list)

    return name in user_list


def vhost_exists(name, runas=None):
    '''
    Return whether the vhost exists based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.vhost_exists rabbit_host
    '''
    if runas is None:
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

    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl add_user {0} {1!r}'.format(name, password),
        output_loglevel='quiet',
        python_shell=False,
        runas=runas)

    if clear_pw:
        # Now, Clear the random password from the account, if necessary
        res2 = clear_password(name, runas)

        if 'Error' in res2:
            # Clearing the password failed. We should try to cleanup
            # and rerun and error.
            delete_user(name, runas)
            msg = 'Error'
            return _format_response(res2, msg)

    msg = 'Added'
    return _format_response(res, msg)


def delete_user(name, runas=None):
    '''
    Deletes a user via rabbitmqctl delete_user.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_user rabbit_user
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl delete_user {0}'.format(name),
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
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl change_password {0} {1!r}'.format(name, password),
        output_loglevel='quiet',
        python_shell=False,
        runas=runas)
    msg = 'Password Changed'

    return _format_response(res, msg)


def clear_password(name, runas=None):
    '''
    Removes a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.clear_password rabbit_user
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl clear_password {0}'.format(name),
                              python_shell=False,
                              runas=runas)
    msg = 'Password Cleared'

    return _format_response(res, msg)


def add_vhost(vhost, runas=None):
    '''
    Adds a vhost via rabbitmqctl add_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq add_vhost '<vhost_name>'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl add_vhost {0}'.format(vhost),
                              python_shell=False,
                              runas=runas)

    msg = 'Added'
    return _format_response(res, msg)


def delete_vhost(vhost, runas=None):
    '''
    Deletes a vhost rabbitmqctl delete_vhost.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_vhost '<vhost_name>'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl delete_vhost {0}'.format(vhost),
                              python_shell=False,
                              runas=runas)
    msg = 'Deleted'
    return _format_response(res, msg)


def set_permissions(vhost, user, conf='.*', write='.*', read='.*', runas=None):
    '''
    Sets permissions for vhost via rabbitmqctl set_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_permissions 'myvhost' 'myuser'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl set_permissions -p {0} {1} "{2}" "{3}" "{4}"'.format(
            vhost, user, conf, write, read),
        python_shell=False,
        runas=runas)
    msg = 'Permissions Set'
    return _format_response(res, msg)


def list_permissions(vhost, runas=None):
    '''
    Lists permissions for vhost via rabbitmqctl list_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_permissions '/myvhost'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl list_permissions -p {0}'.format(vhost),
        python_shell=False,
        runas=runas)

    return _output_to_dict(res)


def list_user_permissions(name, runas=None):
    '''
    List permissions for a user via rabbitmqctl list_user_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_user_permissions 'user'.
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl list_user_permissions {0}'.format(name),
        python_shell=False,
        runas=runas)

    return _output_to_dict(res)


def set_user_tags(name, tags, runas=None):
    '''Add user tags via rabbitmqctl set_user_tags

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_user_tags 'myadmin' 'administrator'
    '''
    if runas is None:
        runas = salt.utils.get_user()

    if tags and isinstance(tags, (list, tuple)):
        tags = ' '.join(tags)

    res = __salt__['cmd.run'](
        'rabbitmqctl set_user_tags {0} {1}'.format(name, tags),
        python_shell=False,
        runas=runas)
    msg = "Tag(s) set"
    return _format_response(res, msg)


def status(runas=None):
    '''
    return rabbitmq status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.status
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl status',
        runas=runas
    )
    return res


def cluster_status(runas=None):
    '''
    return rabbitmq cluster_status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.cluster_status
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl cluster_status',
        runas=runas)

    return res


def join_cluster(host, user='rabbit', ram_node=None, runas=None):
    '''
    Join a rabbit cluster

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.join_cluster 'rabbit.example.com' 'rabbit'
    '''
    if ram_node:
        cmd = 'rabbitmqctl join_cluster --ram {0}@{1}'.format(user, host)
    else:
        cmd = 'rabbitmqctl join_cluster {0}@{1}'.format(user, host)

    if runas is None:
        runas = salt.utils.get_user()
    stop_app(runas)
    res = __salt__['cmd.run'](cmd, runas=runas, python_shell=False)
    start_app(runas)

    return _format_response(res, 'Join')


def stop_app(runas=None):
    '''
    Stops the RabbitMQ application, leaving the Erlang node running.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.stop_app
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl stop_app',
        runas=runas)

    return res


def start_app(runas=None):
    '''
    Start the RabbitMQ application.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.start_app
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl start_app',
        runas=runas)

    return res


def reset(runas=None):
    '''
    Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.reset
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl reset',
        runas=runas)

    return res


def force_reset(runas=None):
    '''
    Forcefully Return a RabbitMQ node to its virgin state

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.force_reset
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl force_reset',
        runas=runas)

    return res


def list_queues(runas=None, *kwargs):
    '''
    Returns queue details of the / virtual host

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl list_queues {0}'.format(' '.join(list(kwargs))),
        python_shell=False,
        runas=runas,
        )
    return res


def list_queues_vhost(vhost, runas=None, *kwargs):
    '''
    Returns queue details of specified virtual host. This command will consider
    first parameter as the vhost name and rest will be treated as
    queueinfoitem. For getting details on vhost ``/``, use :mod:`list_queues
    <salt.modules.rabbitmq.list_queues>` instead).

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl list_queues -p {0} {1}'.format(
            vhost,
            ' '.join(list(kwargs))
            ),
        python_shell=False,
        runas=runas,
        )
    return res


def list_policies(runas=None):
    '''
    Return a dictionary of policies nested by vhost and name
    based on the data returned from rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_policies'
    '''
    ret = {}
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqctl list_policies',
                              runas=runas)
    for line in res.splitlines():
        if '...' not in line and line != '\n':
            parts = line.split('\t')
            if len(parts) not in (5, 6):
                continue
            vhost, name = parts[0], parts[1]
            if vhost not in ret:
                ret[vhost] = {}
            ret[vhost][name] = {}
            # How many fields are there? - 'apply_to' was inserted in position 2 at somepoint
            offset = len(parts) - 5
            if len(parts) == 6:
                ret[vhost][name]['apply_to'] = parts[2]
            ret[vhost][name].update({
                'pattern': parts[offset+2],
                'definition': parts[offset+3],
                'priority': parts[offset+4]
            })
    log.debug('Listing policies: {0}'.format(ret))
    return ret


def set_policy(vhost, name, pattern, definition, priority=None, runas=None):
    '''
    Set a policy based on rabbitmqctl set_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_policy / HA '.*' '{"ha-mode": "all"}'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        "rabbitmqctl set_policy -p {0}{1}{2} {3} '{4}' '{5}'".format(
            vhost,
            ' --priority ' if priority else '',
            priority if priority else '',
            name,
            pattern,
            definition.replace("'", '"')),
        python_shell=False,
        runas=runas)
    log.debug('Set policy: {0}'.format(res))
    return _format_response(res, 'Set')


def delete_policy(vhost, name, runas=None):
    '''
    Delete a policy based on rabbitmqctl clear_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_policy / HA'
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqctl clear_policy -p {0} {1}'.format(
            vhost, name),
        python_shell=False,
        runas=runas)
    log.debug('Delete policy: {0}'.format(res))
    return _format_response(res, 'Deleted')


def policy_exists(vhost, name, runas=None):
    '''
    Return whether the policy exists based on rabbitmqctl list_policies.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.policy_exists / HA
    '''
    if runas is None:
        runas = salt.utils.get_user()
    policies = list_policies(runas=runas)
    return bool(vhost in policies and name in policies[vhost])


def plugin_is_enabled(name, runas=None):
    '''
    Return whether the plugin is enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.plugin_is_enabled foo
    '''
    rabbitmq = _get_rabbitmq_plugin()
    cmd = '{0} list -m -e'.format(rabbitmq)
    if runas is None:
        runas = salt.utils.get_user()
    ret = __salt__['cmd.run'](cmd, python_shell=False, runas=runas)
    return bool(name in ret)


def enable_plugin(name, runas=None):
    '''
    Enable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.enable_plugin foo
    '''
    rabbitmq = _get_rabbitmq_plugin()
    cmd = '{0} enable {1}'.format(rabbitmq, name)

    if runas is None:
        runas = salt.utils.get_user()
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, runas=runas)

    return _format_response(ret, 'Enabled')


def disable_plugin(name, runas=None):
    '''
    Disable a RabbitMQ plugin via the rabbitmq-plugins command.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.disable_plugin foo
    '''

    rabbitmq = _get_rabbitmq_plugin()
    cmd = '{0} disable {1}'.format(rabbitmq, name)

    if runas is None:
        runas = salt.utils.get_user()
    ret = __salt__['cmd.run_all'](cmd, python_shell=False, runas=runas)

    return _format_response(ret, 'Disabled')
