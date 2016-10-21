# -*- coding: utf-8 -*-
'''
Module for Samba's pdbedit tool
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pdbedit'

# Function aliases
__func_alias__ = {
    'list_users': 'list',
    'get_user': 'get',
}


def __virtual__():
    '''
    Provides pdbedit if available
    '''
    if salt.utils.which('pdbedit'):
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded when pdbedit is available'.format(
            __virtualname__
        )
    )


def list_users(verbose=True):
    '''
    List user accounts

    verbose : boolean
        return all information

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.list
    '''
    users = {} if verbose else []

    if verbose:
        ## parse detailed user data
        res = __salt__['cmd.run_all']('pdbedit --list --verbose')

        if res['retcode'] > 0:
            log.error(res['stderr'] if 'stderr' in res else res['stdout'])
        else:
            user_data = {}
            for user in res['stdout'].splitlines():
                if user.startswith('-'):
                    if len(user_data) > 0:
                        users[user_data['unix username']] = user_data
                    user_data = {}
                else:
                    label = user[:user.index(':')].strip().lower()
                    data = user[(user.index(':')+1):].strip()
                    if len(data) > 0:
                        user_data[label] = data

            if len(user_data) > 0:
                users[user_data['unix username']] = user_data
    else:
        ## list users
        res = __salt__['cmd.run_all']('pdbedit --list')

        if res['retcode'] > 0:
            log.error(res['stderr'] if 'stderr' in res else res['stdout'])
        else:
            for user in res['stdout'].splitlines():
                users.append(user.split(':')[0])

    return users


def get_user(login):
    '''
    Get user account details

    login : string
        login name

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.get kaylee
    '''
    users = list_users()
    return users[login] if login in users else {}

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
