# -*- coding: utf-8 -*-
'''
Manage the shadow file

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
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
    return (False, 'Module win_shadow: module only works on Windows systems.')


def info(name):
    '''
    Return information for the specified user
    This is just returns dummy data so that salt states can work.

    :param str name: The name of the user account to show.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    '''
    info = __salt__['user.info'](name=name)

    ret = {'name': name,
           'passwd': '',
           'lstchg': '',
           'min': '',
           'max': '',
           'warn': '',
           'inact': '',
           'expire': ''}

    if info:
        ret = {'name': info['name'],
               'passwd': 'Unavailable',
               'lstchg': info['password_changed'],
               'min': '',
               'max': '',
               'warn': '',
               'inact': '',
               'expire': info['expiration_date']}

    return ret


def set_expire(name, expire):
    '''
    Set the expiration date for a user account.

    :param name: The name of the user account to edit.

    :param expire: The date the account will expire.

    :return: True if successful. False if unsuccessful.
    :rtype: bool
    '''
    return __salt__['user.update'](name, expiration_date=expire)


def require_password_change(name):
    '''
    Require the user to change their password the next time they log in.

    :param name: The name of the user account to require a password change.

    :return: True if successful. False if unsuccessful.
    :rtype: bool
    '''
    return __salt__['user.update'](name, expired=True)


def unlock_account(name):
    '''
    Unlocks a user account.

    :param name: The name of the user account to unlock.

    :return: True if successful. False if unsuccessful.
    :rtype: bool
    '''
    return __salt__['user.update'](name, unlock_account=True)


def set_password(name, password):
    '''
    Set the password for a named user.

    :param str name: The name of the user account

    :param str password: The new password

    :return: True if successful. False if unsuccessful.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root mysecretpassword
    '''
    return __salt__['user.update'](name=name, password=password)
