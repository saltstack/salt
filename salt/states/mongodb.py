# -*- coding: utf-8 -*-
'''
Management of Mongodb users and databases
=========================================

.. note::
    This module requires PyMongo to be installed.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Define the module's virtual name
__virtualname__ = 'mongodb'


def __virtual__():
    if 'mongodb.user_exists' not in __salt__:
        return False
    return __virtualname__


def database_absent(name,
           user=None,
           password=None,
           host=None,
           port=None,
           authdb=None):
    '''
    Ensure that the named database is absent. Note that creation doesn't make sense in MongoDB.

    name
        The name of the database to remove

    user
        The user to connect as (must be able to create the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    authdb
        The database in which to authenticate
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if database exists and remove it
    if __salt__['mongodb.db_exists'](name, user, password, host, port, authdb=authdb):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Database {0} is present and needs to be removed'
                    ).format(name)
            return ret
        if __salt__['mongodb.db_remove'](name, user, password, host, port, authdb=authdb):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = ('User {0} is not present, so it cannot be removed'
            ).format(name)
    return ret


def user_present(name,
            passwd,
            database="admin",
            user=None,
            password=None,
            host="localhost",
            port=27017,
            authdb=None):
    '''
    Ensure that the user is present with the specified properties

    name
        The name of the user to manage

    passwd
        The password of the user to manage

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified with the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database in which to create the user

        .. note::
            If the database doesn't exist, it will be created.

    authdb
        The database in which to authenticate

    Example:

    .. code-block:: yaml

        mongouser-myapp:
          mongodb.user_present:
          - name: myapp
          - passwd: password-of-myapp
          # Connect as admin:sekrit
          - user: admin
          - password: sekrit

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is already present'.format(name)}

    # Check for valid port
    try:
        port = int(port)
    except TypeError:
        ret['result'] = False
        ret['comment'] = 'Port ({0}) is not an integer.'.format(port)
        return ret

    # check if user exists
    user_exists = __salt__['mongodb.user_exists'](name, user, password, host, port, database, authdb)
    if user_exists is True:
        return ret

    # if the check does not return a boolean, return an error
    # this may be the case if there is a database connection error
    if not isinstance(user_exists, bool):
        ret['comment'] = user_exists
        ret['result'] = False
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('User {0} is not present and needs to be created'
                ).format(name)
        return ret
    # The user is not present, make it!
    if __salt__['mongodb.user_create'](name, passwd, user, password, host, port, database=database, authdb=authdb):
        ret['comment'] = 'User {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create database {0}'.format(name)
        ret['result'] = False

    return ret


def user_absent(name,
           user=None,
           password=None,
           host=None,
           port=None,
           database="admin",
           authdb=None):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified by the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database from which to remove the user specified by the ``name``
        parameter

    authdb
        The database in which to authenticate
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if user exists and remove it
    user_exists = __salt__['mongodb.user_exists'](name, user, password, host, port, database=database, authdb=authdb)
    if user_exists is True:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('User {0} is present and needs to be removed'
                    ).format(name)
            return ret
        if __salt__['mongodb.user_remove'](name, user, password, host, port, database=database, authdb=authdb):
            ret['comment'] = 'User {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # if the check does not return a boolean, return an error
    # this may be the case if there is a database connection error
    if not isinstance(user_exists, bool):
        ret['comment'] = user_exists
        ret['result'] = False
        return ret

    # fallback
    ret['comment'] = ('User {0} is not present, so it cannot be removed'
            ).format(name)
    return ret


def _roles_to_set(roles, database):
    ret = set()
    for r in roles:
        if isinstance(r, dict):
            if r['db'] == database:
                ret.add(r['role'])
        else:
            ret.add(r)
    return ret


def _user_roles_to_set(user_list, name, database):
    ret = set()

    for item in user_list:
        if item['user'] == name:
            ret = ret.union(_roles_to_set(item['roles'], database))
    return ret


def user_grant_roles(name, roles,
            database="admin",
            user=None,
            password=None,
            host="localhost",
            port=27017,
            authdb=None):

    '''
    Ensure that the named user is granted certain roles

    name
        The name of the user to remove

    roles
        The roles to grant to the user

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified by the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database from which to remove the user specified by the ``name``
        parameter

    authdb
        The database in which to authenticate
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not isinstance(roles, (list, tuple)):
        roles = [roles]

    if not roles:
        ret['result'] = True
        ret['comment'] = "nothing to do (no roles given)"
        return ret

    # Check for valid port
    try:
        port = int(port)
    except TypeError:
        ret['result'] = False
        ret['comment'] = 'Port ({0}) is not an integer.'.format(port)
        return ret

    # check if grant exists
    user_roles_exists = __salt__['mongodb.user_roles_exists'](name, roles, database,
        user=user, password=password, host=host, port=port, authdb=authdb)
    if user_roles_exists is True:
        ret['result'] = True
        ret['comment'] = "Roles already assigned"
        return ret

    user_list = __salt__['mongodb.user_list'](database=database,
        user=user, password=password, host=host, port=port, authdb=authdb)

    user_set = _user_roles_to_set(user_list, name, database)
    roles_set = _roles_to_set(roles, database)
    diff = roles_set - user_set

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = "Would have modified roles (missing: {0})".format(diff)
        return ret

    # The user is not present, make it!
    if __salt__['mongodb.user_grant_roles'](name, roles, database,
        user=user, password=password, host=host, port=port, authdb=authdb):
        ret['comment'] = 'Granted roles to {0} on {1}'.format(name, database)
        ret['changes'][name] = ['{0} granted'.format(i) for i in diff]
        ret['result'] = True
    else:
        ret['comment'] = 'Failed to grant roles ({2}) to {0} on {1}'.format(name, database, diff)

    return ret


def user_set_roles(name, roles,
            database="admin",
            user=None,
            password=None,
            host="localhost",
            port=27017,
            authdb=None):

    '''
    Ensure that the named user has the given roles and no other roles

    name
        The name of the user to remove

    roles
        The roles the given user should have

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified by the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database from which to remove the user specified by the ``name``
        parameter

    authdb
        The database in which to authenticate
    '''

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not isinstance(roles, (list, tuple)):
        roles = [roles]

    if not roles:
        ret['result'] = True
        ret['comment'] = "nothing to do (no roles given)"
        return ret

    # Check for valid port
    try:
        port = int(port)
    except TypeError:
        ret['result'] = False
        ret['comment'] = 'Port ({0}) is not an integer.'.format(port)
        return ret

    user_list = __salt__['mongodb.user_list'](database=database,
        user=user, password=password, host=host, port=port, authdb=authdb)

    user_set = _user_roles_to_set(user_list, name, database)
    roles_set = _roles_to_set(roles, database)
    to_grant = list(roles_set - user_set)
    to_revoke = list(user_set - roles_set)

    if not to_grant and not to_revoke:
        ret['result'] = True
        ret['comment'] = "User {0} has the appropriate roles on {1}".format(name, database)
        return ret

    if __opts__['test']:
        lsg = ', '.join(to_grant)
        lsr = ', '.join(to_revoke)
        ret['result'] = None
        ret['comment'] = "Would have modified roles (grant: {0}; revoke: {1})".format(lsg, lsr)
        return ret

    ret['changes'][name] = changes = {}

    if to_grant:
        if not __salt__['mongodb.user_grant_roles'](name, to_grant, database,
            user=user, password=password, host=host, port=port, authdb=authdb):
            ret['comment'] = "failed to grant some or all of {0} to {1} on {2}".format(to_grant, name, database)
            return ret
        else:
            changes['granted'] = list(to_grant)

    if to_revoke:
        if not __salt__['mongodb.user_revoke_roles'](name, to_revoke, database,
            user=user, password=password, host=host, port=port, authdb=authdb):
            ret['comment'] = "failed to revoke some or all of {0} to {1} on {2}".format(to_revoke, name, database)
            return ret
        else:
            changes['revoked'] = list(to_revoke)

    ret['result'] = True
    return ret
