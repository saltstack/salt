'''
Module to provide RabbitMQ compatibility to Salt.
Todo: A lot, need to add cluster support, logging, and minion configuration
data.
'''
from salt import exceptions, utils
import logging


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


def list_users():
    '''
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example::

        salt '*' rabbitmq.list_users
    '''
    d = {}
    res = __salt__['cmd.run']('rabbitmqctl list_users')
    for line in res.split('\n'):
        if '...' not in line or line == '\n':
            # TODO Rename these vars
            k = line.split('\t')[0]
            d[k] = line.split('\t')[1]
    return d


def list_vhosts():
    '''
    Return a list of vhost based of of rabbitmqctl list_vhosts.

    CLI Example::

        salt '*' rabbitmq.list_vhosts
    '''
    res = __salt__['cmd.run']('rabbitmqctl list_vhosts')
    lines = res.split('\n')
    vhost = [line for line in lines if '...' not in line]
    return {
        'vhost_list': vhost
    }


def add_user(name, password):
    '''
    Add a rabbitMQ user via rabbitmqctl user_add <user> <password>

    CLI Example::

        salt '*' rabbitmq.add_user rabbit_user password
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl add_user {0} {1}'.format(name, password))

    msg = 'Added'
    return _format_response(res, msg)


def delete_user(name):
    '''
    Deletes a user via rabbitmqctl delete_user.

    CLI Example::

        salt '*' rabbitmq.delete_user rabbit_user
    '''
    res = __salt__['cmd.run']('rabbitmqctl delete_user {0}'.format(name))
    msg = 'Deleted'

    return _format_response(res, msg)


def change_password(name, password):
    '''
    Changes a user's password.

    CLI Example::

        salt '*' rabbitmq.change_password rabbit_user password
    '''
    res = __salt__['cmd.run'](
        'rabbitmqctl change_password {0} {1}'.format(name, password))
    msg = 'Password Changed'

    return _format_response(res, msg)


def clear_password(name):
    '''
    Removes a user's password.

    CLI Example::

        salt '*' rabbitmq.clear_password rabbit_user
    '''
    res = __salt__['cmd.run']('rabbitmqctl clear_password {0}'.format(name))
    msg = 'Password Cleared'

    return _format_response(res, msg)


def add_vhost(vhost):
    '''
    Adds a vhost via rabbitmqctl add_vhost.

    CLI Example::

        salt '*' rabbitmq add_vhost '<vhost_name>'
    '''
    res = __salt__['cmd.run']('rabbitmqctl add_vhost {0}'.format(vhost))
    if 'Error' in res:
        return { 'Error' : res.replace('\n', '') }
    return { 'added_vhost' : res.replace('\n', '') }


def delete_vhost(vhost):
    '''
    Deletes a vhost rabbitmqctl delete_vhost.

    CLI Example::

        salt '*' rabbitmq.delete_vhost '<vhost_name>'
    '''
    res = __salt__['cmd.run']('rabbitmqctl delete_vhost {0}'.format(vhost))
    if 'Error' in res:
        return { 'Error' : res.replace('\n', '') }
    return { 'deleted_vhost' : res.replace('\n','') }


def set_permissions(vhost,user,conf='.*',write='.*',read='.*'):
    '''
    Sets permissions for vhost via rabbitmqctl set_permissions

    CLI Example::

        salt '*' rabbitmq.set_permissions 'myvhost' 'myuser'
    '''
    res = __salt__['cmd.run']('rabbitmqctl set_permissions -p {0} {1} "{2}" "{3}" "{4}"'.format(vhost,user,conf,write,read))
    return { 'set_permissions': res.replace('\n', '') }


def list_user_permissions(name):
    '''
    List permissions for a user via rabbitmqctl list_user_permissions

    Example::

        salt '*' rabbitmq.list_user_permissions 'user'.
    '''
    res = __salt__['cmd.run']('rabbitmqctl list_user_permissions {0}'.format(name))
    return { 'user_permissions' : [ r.split('\t') for r in res.split('\n') ] }
