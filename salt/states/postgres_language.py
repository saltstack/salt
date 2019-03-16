# -*- coding: utf-8 -*-
'''
Management of PostgreSQL languages
==================================

The postgres_language module is used to create and manage Postgres languages.
Languages can be set as either absent or present

.. versionadded:: 2016.3.0

.. code-block:: yaml

    plpgsql:
      postgres_language.present:
        - maintenance_db: testdb

.. code-block:: yaml

    plpgsql:
      postgres_language.absent:
        - maintenance_db: testdb

'''
from __future__ import absolute_import, unicode_literals, print_function


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    if 'postgres.language_create' not in __salt__:
        return (False, 'Unable to load postgres module.  Make sure `postgres.bins_dir` is set.')
    return True


def present(name,
            maintenance_db,
            user=None,
            db_password=None,
            db_host=None,
            db_port=None,
            db_user=None):
    '''
    Ensure that a named language is present in the specified
    database.

    name
        The name of the language to install

    maintenance_db
        The name of the database in which the language is to be installed

    user
        System user all operations should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': 'Language {0} is already installed'.format(name)
    }

    dbargs = {
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }

    languages = __salt__['postgres.language_list'](maintenance_db, **dbargs)

    if name not in languages:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Language {0} is set to be installed'.format(
                name)
            return ret

        if __salt__['postgres.language_create'](name, maintenance_db,
                **dbargs):
            ret['comment'] = 'Language {0} has been installed'.format(name)
            ret['changes'][name] = 'Present'
        else:
            ret['comment'] = 'Failed to install language {0}'.format(name)
            ret['result'] = False

    return ret


def absent(
        name,
        maintenance_db,
        user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_user=None):
    '''
    Ensure that a named language is absent in the specified
    database.

    name
        The name of the language to remove

    maintenance_db
        The name of the database in which the language is to be installed

    user
        System user all operations should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': ''
    }

    dbargs = {
        'runas': user,
        'host': db_host,
        'user': db_user,
        'port': db_port,
        'password': db_password,
    }

    if __salt__['postgres.language_exists'](name, maintenance_db, **dbargs):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Language {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.language_remove'](name, **dbargs):
            ret['comment'] = 'Language {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['comment'] = 'Failed to remove language {0}'.format(name)
            ret['result'] = False

    ret['comment'] = 'Language {0} is not present ' \
        'so it cannot be removed'.format(name)
    return ret
