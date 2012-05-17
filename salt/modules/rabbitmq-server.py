'''
Module to provide rabbitMQ compatibility to salt.
Todo: Alot, need to add cluster support, logging, and minion configuration data.
'''

def list_users():
    '''
    Return a list of users based off of rabbitmqctl user_list.

    CLI Example::

        salt '*' rabbitmq-server.list_users
    '''
    d = {}
    res = __salt__['cmd.run']('rabbitmqctl list_users')
    for line in res.split('\n'):
        if '...' not in line or line == '\n': d[ line.split('\t')[0] ] = line.split('\t')[1]
    return d


def list_vhosts():
    '''
    Return a list of vhost based of of rabbitmqctl list_vhosts.

    CLI Example::
        salt '*' rabbitmq-server.list_vhosts
    '''
    res = __salt__['cmd.run']('rabbitmqctl list_vhosts')
    r = res.split('\n')
    vhost = []
    [vhost.append(x) for x in r if '...' not in x]
    return { 'vhost_list' : vhost }


def add_user(name, password):
    '''
    Add a rabbitMQ user.
    '''
    res = __salt__['cmd.run']('rabbitmqctl add_user {0} {1}'.format(name, password))
    return { 'Added' : res }


def delete_user(name):
    '''
    Deletes a user.
    '''
    res = __salt__['cmd.run']('rabbitmqctl delete_user {0}'.format(name))
    return { 'delete' : res }


def add_vhost(vhost):
    '''
    Adds a vhost to the service.
    '''
    res = __salt__['cmd.run']('rabbitmqctl add_vhost {0}'.format(vhost))
    return {'add_vhost' : res}


def delete_vhost(vhost):
    '''
    Deletes a vhost.
    '''
    res = __salt__['cmd.run']('rabbitmqctl delete_vhost {0}'.format(vhost))
    return {'delete' : res}


def set_permissions(vhost,user,conf='.*',write='.*',read='.*'):
    '''
    Sets permissions for vhost.
    '''
    res = __salt__['cmd.run']('rabbitmqctl set_permissions -p {0} {1} "{2}" "{3}" "{4}"'.format(vhost,user,conf,write,read))
    return { 'set_permissions': res }


def list_user_permissions(name):
    '''
    List permissions for a user.
    '''
    res = __salt__['cmd.run']('rabbitmqctl list_user_permissions {0}'.format(name))
    return { 'user_permissions' : [ r.split('\t') for r in res.split('\n') ] }
