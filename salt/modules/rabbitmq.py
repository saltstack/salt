# -*- coding: utf-8 -*-
'''
Module to provide RabbitMQ compatibility to Salt.
Todo: A lot, need to add cluster support, logging, and minion configuration
data.
'''

# Import salt libs
from salt import exceptions, utils

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''Verify RabbitMQ is installed.
    '''
    name = 'rabbitmq'
    try:
        utils.check_or_die('rabbitmqctl')
    except exceptions.CommandNotFoundError:
        name = False
    return name


def _format_response(response, msg):
    if 'Error' in response:
        msg = 'Error'

    return {
        msg: response.replace('\n', '')
    }


def list_users(runas=None):
    '''
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_users
    '''
    ret = {}
    res = __salt__['cmd.run']('rabbitmqctl list_users',
                              runas=runas)
    for line in res.splitlines():
        if '...' not in line or line == '\n':
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            user, properties = parts[0], parts[1]
            ret[user] = properties
    return ret


def list_vhosts(runas=None):
    '''
    Return a list of vhost based on rabbitmqctl list_vhosts.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_vhosts
    '''
    res = __salt__['cmd.run']('rabbitmqctl list_vhosts',
                              runas=runas)
    lines = res.splitlines()
    vhost_list = [line for line in lines if '...' not in line]
    return vhost_list


def user_exists(name, runas=None):
    '''
    Return whether the user exists based on rabbitmqctl list_users.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.user_exists rabbit_user
    '''
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
    return name in list_vhosts(runas=runas)


def add_user(name, password, runas=None):
    '''
    Add a rabbitMQ user via rabbitmqctl user_add <user> <password>

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.add_user rabbit_user password
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl add_user {0} \'{1}\''.format(name, password),
        runas=runas)

    msg = 'Added'
    return _format_response(res, msg)


def delete_user(name, runas=None):
    '''
    Deletes a user via rabbitmqctl delete_user.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.delete_user rabbit_user
    '''
    res = __salt__['cmd.run']('rabbitmqctl delete_user {0}'.format(name),
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
    res = __salt__['cmd.run'](
        'rabbitmqctl change_password {0} \'{1}\''.format(name, password),
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
    res = __salt__['cmd.run']('rabbitmqctl clear_password {0}'.format(name),
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
    res = __salt__['cmd.run']('rabbitmqctl add_vhost {0}'.format(vhost),
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
    res = __salt__['cmd.run']('rabbitmqctl delete_vhost {0}'.format(vhost),
                              runas=runas)
    msg = 'Deleted'
    return _format_response(res, msg)


def set_permissions(vhost, user, conf='.*', write='.*', read='.*',
        runas=None):
    '''
    Sets permissions for vhost via rabbitmqctl set_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_permissions 'myvhost' 'myuser'
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl set_permissions -p {0} {1} "{2}" "{3}" "{4}"'.format(
            vhost, user, conf, write, read),
        runas=runas)
    msg = 'Permissions Set'
    return _format_response(res, msg)


def list_user_permissions(name, user=None):
    '''
    List permissions for a user via rabbitmqctl list_user_permissions

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_user_permissions 'user'.
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl list_user_permissions {0}'.format(name),
        runas=user)
    return [r.split('\t') for r in res.splitlines()]


def status(user=None):
    '''
    return rabbitmq status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.status
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl status',
        runas=user
    )
    return res


def cluster_status(user=None):
    '''
    return rabbitmq cluster_status

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.cluster_status
    '''
    ret = {}
    res = __salt__['cmd.run'](
        'rabbitmqctl cluster_status',
        runas=user)

    return res


def stop_app(runas=None):
    '''
    Stops the RabbitMQ application, leaving the Erlang node running.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.stop_app
    '''
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
    res = __salt__['cmd.run'](
        'rabbitmqctl force_reset',
        runas=runas)

    return res


def list_queues(*kwargs):
    '''
    Returns queue details of the / virtual host

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl list_queues {0}'.format(' '.join(list(kwargs))))
    return res


def list_queues_vhost(vhost, *kwargs):
    '''
    Returns queue details of specified virtual host. This command will consider
    first parameter as the vhost name and rest will be treated as
    queueinfoitem. For getting details on vhost ``/``, use :mod:`list_queues
    <salt.modules.rabbitmq.list_queues>` instead).

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.list_queues messages consumers
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl list_queues -p {0} {1}'.format(vhost, ' '.join(list(kwargs))))
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
    res = __salt__['cmd.run']('rabbitmqctl list_policies',
                              runas=runas)
    for line in res.splitlines():
        if '...' not in line and line != '\n':
            parts = line.split('\t')
            if len(parts) != 5:
                continue
            vhost, name = parts[0], parts[1]
            if vhost not in ret:
                ret[vhost] = {}
            ret[vhost][name] = {
                'pattern': parts[2],
                'definition': parts[3],
                'priority': parts[4]
            }
    log.debug('Listing policies: {0}'.format(ret))
    return ret


def set_policy(vhost, name, pattern, definition, priority=0, runas=None):
    '''
    Set a policy based on rabbitmqctl set_policy.

    Reference: http://www.rabbitmq.com/ha.html

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.set_policy / HA '.*' '{"ha-mode": "all"}'
    '''
    res = __salt__['cmd.run'](
        "rabbitmqctl set_policy -p {0} {1} '{2}' '{3}' {4}".format(
            vhost, name, pattern, definition.replace("'", '"'), priority),
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
    res = __salt__['cmd.run'](
        'rabbitmqctl clear_policy -p {0} {1}'.format(
            vhost, name),
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
    policies = list_policies(runas=runas)
    return bool(vhost in policies and name in policies[vhost])
