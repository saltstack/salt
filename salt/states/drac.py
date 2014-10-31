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

'''

import salt.exceptions


def __virtual__():
    '''
    Ensure the racadm command is installed
    '''
    if salt.utils.which('racadm'):
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
