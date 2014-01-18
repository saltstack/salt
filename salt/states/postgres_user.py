# -*- coding: utf-8 -*-
'''
Management of PostgreSQL users (roles)
======================================

The postgres_users module is used to create and manage Postgres users.

.. code-block:: yaml

    frank:
      postgres_user.present
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    return 'postgres_user' if 'postgres.user_exists' in __salt__ else False


def present(name,
            createdb=None,
            createuser=None,
            encrypted=None,
            superuser=None,
            replication=None,
            password=None,
            groups=None,
            runas=None,
            user=None,
            db_password=None,
            db_host=None,
            db_port=None,
            db_user=None):
    '''
    Ensure that the named user is present with the specified privileges

    name
        The name of the user to manage

    createdb
        Is the user allowed to create databases?

    createuser
        Is the user allowed to create other users?

    encrypted
        Should the password be encrypted in the system catalog?

    superuser
        Should the new user be a "superuser"

    replication
        Should the new user be allowed to initiate streaming replication

    password
        The user's password

    groups
        A string of comma separated groups the user should be in

    runas
        System user all operations should be performed on behalf of

        .. deprecated:: 0.17.0

    user
        System user all operations should be performed on behalf of

        .. versionadded:: 0.17.0

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is already present'.format(name)}

    salt.utils.warn_until(
        'Hydrogen',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    db_args = {
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }

    # check if user exists
    if __salt__['postgres.user_exists'](name,
                                        createdb=createdb,
                                        createuser=createuser,
                                        superuser=superuser,
                                        replication=replication,
                                        rolepassword=password,
                                        **db_args):
        return ret
    # User might exist with different password or attributes
    if __salt__['postgres.user_exists'](name, **db_args):
        # User does exist with different password or attributes
        # Lets update it
        ret['changes']['Updated user "{0}" successfully'.format(name)] = (
            __salt__['postgres.user_update'](name,
                                             createdb=createdb,
                                             createuser=createuser,
                                             encrypted=encrypted,
                                             superuser=superuser,
                                             replication=replication,
                                             rolepassword=password,
                                             groups=groups,
                                             **db_args))
        return ret

    # The user is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} is set to be created'.format(name)
        return ret

    # Setting default values
    if createdb is None:
        createdb = False
    if createuser is None:
        createuser = False
    if encrypted is None:
        encrypted = False
    if superuser is None:
        superuser = False
    if replication is None:
        replication = False

    if __salt__['postgres.user_create'](username=name,
                                        createdb=createdb,
                                        createuser=createuser,
                                        encrypted=encrypted,
                                        superuser=superuser,
                                        replication=replication,
                                        rolepassword=password,
                                        groups=groups,
                                        **db_args):
        ret['comment'] = 'The user {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create user {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name,
           runas=None,
           user=None,
           db_password=None,
           db_host=None,
           db_port=None,
           db_user=None):
    '''
    Ensure that the named user is absent

    name
        The username of the user to remove

    runas
        System user all operations should be performed on behalf of

        .. deprecated:: 0.17.0

    user
        System user all operations should be performed on behalf of

        .. versionadded:: 0.17.0

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    salt.utils.warn_until(
        'Hydrogen',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    db_args = {
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }
    # check if user exists and remove it
    if __salt__['postgres.user_exists'](name, **db_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.user_remove'](name, **db_args):
            ret['comment'] = 'User {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'User {0} failed to be removed'.format(name)
            return ret
    else:
        ret['comment'] = 'User {0} is not present, so it cannot ' \
                         'be removed'.format(name)

    return ret
