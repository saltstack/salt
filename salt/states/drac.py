# -*- coding: utf-8 -*-
'''
Management of Dell DRAC

The DRAC module is used to create and manage DRAC cards on Dell servers


Ensure the user damian is present

  .. code-block:: yaml

    damian:
      drac.present:
        - name: damian
        - password: secret
        - permission: login,test_alerts,clear_logs


Ensure the user damian does not exist

  .. code-block:: yaml

    damian:
      drac.absent:
        - name: damian


Ensure DRAC network is in a consistent state

  .. code-block:: yaml

    my_network:
      drac.network:
        - ip: 10.225.108.29
        - netmask: 255.255.255.224
        - gateway: 10.225.108.1

'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.exceptions
import salt.utils.path


def __virtual__():
    '''
    Ensure the racadm command is installed
    '''
    if salt.utils.path.which('racadm'):
        return True

    return False


def present(name, password, permission):
    '''
    Ensure the user exists on the Dell DRAC

    name:
        The users username

    password
        The password used to authenticate

    permission
        The permissions that should be assigned to a user
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    users = __salt__['drac.list_users']()

    if __opts__['test']:
        if name in users:
            ret['comment'] = '`{0}` already exists'.format(name)
        else:
            ret['comment'] = '`{0}` will be created'.format(name)
            ret['changes'] = {name: 'will be created'}

        return ret

    if name in users:
        ret['comment'] = '`{0}` already exists'.format(name)
    else:
        if __salt__['drac.create_user'](name, password, permission, users):
            ret['comment'] = '`{0}` user created'.format(name)
            ret['changes'] = {name: 'new user created'}
        else:
            ret['comment'] = 'Unable to create user'
            ret['result'] = False

    return ret


def absent(name):
    '''
    Ensure a user does not exist on the Dell DRAC

    name:
        The users username
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    users = __salt__['drac.list_users']()

    if __opts__['test']:
        if name in users:
            ret['comment'] = '`{0}` is set to be deleted'.format(name)
            ret['changes'] = {name: 'will be deleted'}
        else:
            ret['comment'] = '`{0}` does not exist'.format(name)

        return ret

    if name in users:
        if __salt__['drac.delete_user'](name, users[name]['index']):
            ret['comment'] = '`{0}` deleted'.format(name)
            ret['changes'] = {name: 'deleted'}
        else:
            ret['comment'] = 'Unable to delete user'
            ret['result'] = False
    else:
        ret['comment'] = '`{0}` does not exist'.format(name)

    return ret


def network(ip, netmask, gateway):
    '''
    Ensure the DRAC network settings are consistent
    '''
    ret = {'name': ip,
           'result': True,
           'changes': {},
           'comment': ''}

    current_network = __salt__['drac.network_info']()
    new_network = {}

    if ip != current_network['IPv4 settings']['IP Address']:
        ret['changes'].update({'IP Address':
                              {'Old': current_network['IPv4 settings']['IP Address'],
                               'New': ip}})

    if netmask != current_network['IPv4 settings']['Subnet Mask']:
        ret['changes'].update({'Netmask':
                              {'Old': current_network['IPv4 settings']['Subnet Mask'],
                               'New': netmask}})

    if gateway != current_network['IPv4 settings']['Gateway']:
        ret['changes'].update({'Gateway':
                              {'Old': current_network['IPv4 settings']['Gateway'],
                               'New': gateway}})

    if __opts__['test']:
        ret['result'] = None
        return ret

    if __salt__['drac.set_network'](ip, netmask, gateway):
        if not ret['changes']:
            ret['comment'] = 'Network is in the desired state'

        return ret

    ret['result'] = False
    ret['comment'] = 'unable to configure network'

    return ret
