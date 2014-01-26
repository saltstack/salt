# -*- coding: utf-8 -*-
'''
Management of PostgreSQL users (roles)
======================================

The postgres_users module is used to create and manage Postgres users.

.. code-block:: yaml

    frank:
      postgres_user.present
'''

# Import Python libs

# Import salt libs
import salt.utils
import logging

# Salt imports
from salt.modules import postgres


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    return 'postgres_user' if (
        'postgres.user_exists' in __salt__
    ) else False


def present(name,
            createdb=None,
            createroles=None,
            createuser=None,
            encrypted=None,
            superuser=None,
            replication=None,
            inherit=None,
            login=None,
            password=None,
            groups=None,
            runas=None,
            user=None,
            maintenance_db=None,
            db_password=None,
            db_host=None,
            db_port=None,
            db_user=None):
    '''
    Ensure that the named user is present with the specified privileges
    Please note that the user/group notion in postgresql is just abstract, we
    have roles, where users can be seens as roles with the LOGIN privilege
    and groups the others.

    name
        The name of the user to manage

    createdb
        Is the user allowed to create databases?

    createroles
        Is the user allowed to create other users?

    createuser
        Alias to create roles

    encrypted
        Should the password be encrypted in the system catalog?

    login
        Should the group have login perm

    inherit
        Should the group inherit permissions

    superuser
        Should the new user be a "superuser"

    replication
        Should the new user be allowed to initiate streaming replication

    password
        The user's password
        It can be either a plain string or a md5 postgresql hashed password::

            'md5{MD5OF({password}{role}}'

        If encrypted is None or True, the password will be automaticly
        encrypted to the previous
        format if it is not already done.

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
    if createuser:
        createroles = True
    # default to encrypted passwords
    if encrypted is not False:
        encrypted = postgres._DEFAULT_PASSWORDS_ENCRYPTION
    # maybe encrypt if if not already and neccesary
    password = postgres._maybe_encrypt_password(name,
                                                password,
                                                encrypted=encrypted)

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
        'maintenance_db': maintenance_db,
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }

    # check if user exists
    mode = 'create'
    user_attr = __salt__['postgres.role_get'](
        name, return_password=True, **db_args)
    if user_attr is not None:
        mode = 'update'

    # The user is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} is set to be {1}d'.format(name, mode)
        return ret
    cret = None
    update = {}
    if mode == 'update':
        if (
            createdb is not None
            and user_attr['can create databases'] != createdb
        ):
            update['createdb'] = createdb
        if (
            inherit is not None
            and user_attr['inherits privileges'] != inherit
        ):
            update['inherit'] = inherit
        if (login is not None and user_attr['can login'] != login):
            update['login'] = login
        if (
            createroles is not None
            and user_attr['can create roles'] != createroles
        ):
            update['createroles'] = createroles
        if (
            replication is not None
            and user_attr['replication'] != replication
        ):
            update['replication'] = replication
        if superuser is not None and user_attr['superuser'] != superuser:
            update['superuser'] = superuser
        if (password is not None and user_attr['password'] != password):
            update['password'] = True
    if mode == 'create' or (mode == 'update' and update):
        cret = __salt__['postgres.user_{0}'.format(mode)](
            username=name,
            createdb=createdb,
            createroles=createroles,
            encrypted=encrypted,
            superuser=superuser,
            login=login,
            inherit=inherit,
            replication=replication,
            rolepassword=password,
            groups=groups,
            **db_args)
    else:
        cret = None
    if cret:
        ret['comment'] = 'The user {0} has been {1}d'.format(name, mode)
        if update:
            ret['changes'][name] = update
    elif cret is not None:
        ret['comment'] = 'Failed to create user {0}'.format(name)
        ret['result'] = False
    else:
        ret['result'] = True

    return ret


def absent(name,
           runas=None,
           user=None,
           maintenance_db=None,
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
        'maintenance_db': maintenance_db,
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
