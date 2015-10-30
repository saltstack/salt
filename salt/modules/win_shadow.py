# -*- coding: utf-8 -*-
'''
Manage the shadow file
'''
from __future__ import absolute_import

import salt.utils

# Define the module's virtual name
__virtualname__ = 'shadow'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def info(name):
    '''
    Return information for the specified user
    This is just returns dummy data so that salt states can work.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    '''
    ret = {
            'name': name,
            'passwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_expire(name, expire):
    return __salt__['user.update'](name, expiration_date=expire)


def force_password_change(name):
    return __salt__['user.update'](name, expired=True)


def unlock_account(name):
    return __salt__['user.update'](name, unlock_account=True)


def set_password(name, password):
    '''
    Set the password for a named user.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root mysecretpassword
    '''
    return __salt__['user.update'](name=name, password=password)


def info(name):
    return __salt__['user.info'](name=name)
