# -*- coding: utf-8 -*-
'''
Management of Microsoft SQLServer users (roles)
======================================

The mssql_users module is used to create and manage SQL Server users inside a database.

.. code-block:: yaml

    frank:
      mssql_user.present:
        - database: yolo
'''
from __future__ import absolute_import
import collections

# Salt imports
from salt.modules import mssql
import salt.ext.six as six


def __virtual__():
    '''
    Only load if the mssql module is present
    '''
    return 'mssql.version' in __salt__

def _normalize_options(options):
    if type(options) in [dict, collections.OrderedDict]:
        return [ '{0}={1}'.format(k, v) for k, v in options.items() ]
    if type(options) is list and (not len(options) or type(options[0]) is str):
        return options
    # Invalid options
    if type(options) is not list or type(options[0]) not in [dict, collections.OrderedDict]:
        return []
    return [ o for d in options for o in _normalize_options(d) ]

def present(name, password=None, domain=None, database=None, roles=None, login_options=None, user_options=None, **kwargs):
    '''
    Ensure that the named user is present with the specified roles

    name
        The name of the user to manage
    password
        creates a SQL Server authentication login
        Since hashed passwords are varbinary values, if the
        new_login_password is 'long', it will be considered
        to be HASHED.
    domain
        creates a Windows authentication login.
        Needs to be NetBIOS domain or hostname
    database
        the database of the user (not the login)
    roles
        Add this user to all the roles in the list
    login_options and user_options
        can be a list of strings, a dictionary, or a list of dictionaries
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __salt__['mssql.user_exists'](name, domain=domain, database=database, **kwargs):
        ret['comment'] = 'User {0} is already present (Not going to try to set its password)'.format(name, domain)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} is set to be added'.format(name, domain)
        return ret
    
    login = None
    if password or domain:
        login = name
        if __salt__['mssql.login_exists'](login, domain, **kwargs):
            ret['comment'] = 'Login {0} already exists. '.format(login, domain)
        else:
            login_created = __salt__['mssql.login_create'](name,
                    new_login_password=password,
                    new_login_domain=domain,
                    new_login_options=_normalize_options(login_options),
                    **kwargs)
            # Non-empty strings are also evaluated to True, so we cannot use if not login_created:
            if login_created != True:
                ret['result'] = False
                ret['comment'] = 'Login {0} failed to be added: {1}'.format(name, login_created)
                return ret
            ret['comment'] = 'Login {0} has been added. '.format(name)
            ret['changes'][name] = 'Present'
    
    user_created = __salt__['mssql.user_create'](name, login=login,
                                                       domain=domain,
                                                       database=database,
                                                       roles=roles,
                                                       options=_normalize_options(user_options),
                                                       **kwargs)
    if user_created != True:  # Non-empty strings are also evaluated to True, so we cannot use if not user_created:
        ret['result'] = False
        ret['comment'] += 'User {0} failed to be added: {1}'.format(name, user_created)
        return ret
    ret['comment'] += 'User {0} has been added'.format(name)
    ret['changes'][name] = 'Present'
    return ret


def absent(name, **kwargs):
    '''
    Ensure that the named user is absent

    name
        The username of the user to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if __salt__['mssql.user_exists'](name ):
        ret['comment'] = 'User {0} is not present'.format(name)
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} is set to be removed'.format(name)
        return ret
    if __salt__['mssql.user_remove'](name, **kwargs):
        ret['comment'] = 'User {0} has been removed'.format(name)
        ret['changes'][name] = 'Absent'
        return ret
    # else:
    ret['result'] = False
    ret['comment'] = 'User {0} failed to be removed'.format(name)
    return ret

