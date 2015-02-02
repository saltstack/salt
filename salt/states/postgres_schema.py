# -*- coding: utf-8 -*-
'''
Management of PostgreSQL schemas
================================

The postgres_schemas module is used to create and manage Postgres schemas.

.. code-block:: yaml

    public:
      postgres_schema.present 'dbname' 'name'
'''
from __future__ import absolute_import

# Import Python libs
import logging


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    return 'postgres.schema_exists' in __salt__


def present(dbname, name,
            owner=None,
            db_user=None, db_password=None,
            db_host=None, db_port=None):
    '''
    Ensure that the named schema is present in the database.

    dbname
        The database's name will work on

    name
        The name of the schema to manage

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    ret = {'dbname': dbname,
           'name': name,
           'changes': {},
           'result': True,
           'comment': 'Schema {0} is already present in '
                      'database {1}'.format(name, dbname)}

    db_args = {
        'db_user': db_user,
        'db_password': db_password,
        'db_host': db_host,
        'db_port': db_port
    }

    # check if schema exists
    schema_attr = __salt__['postgres.schema_get'](dbname, name, **db_args)

    cret = None

    # The schema is not present, make it!
    if schema_attr is None:
        cret = __salt__['postgres.schema_create'](dbname,
                                                  name,
                                                  owner=owner,
                                                  **db_args)
    else:
        msg = 'Schema {0} already exists in database {1}'
        cret = None

    if cret:
        msg = 'Schema {0} has been created in database {1}'
        ret['result'] = True
        ret['changes'][name] = 'Present'
    elif cret is not None:
        msg = 'Failed to create schema {0} in database {1}'
        ret['result'] = False
    else:
        msg = 'Schema {0} already exists in database {1}'
        ret['result'] = True

    ret['comment'] = msg.format(name, dbname)
    return ret


def absent(dbname, name,
           db_user=None, db_password=None,
           db_host=None, db_port=None):
    '''
    Ensure that the named schema is absent

    dbname
        The database's name will work on

    name
        The name of the schema to remove

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
           'dbname': dbname,
           'changes': {},
           'result': True,
           'comment': ''}

    db_args = {
        'db_user': db_user,
        'db_password': db_password,
        'db_host': db_host,
        'db_port': db_port
        }

    # check if schema exists and remove it
    if __salt__['postgres.schema_exists'](dbname, name, **db_args):
        if __salt__['postgres.schema_remove'](dbname, name, **db_args):
            ret['comment'] = 'Schema {0} has been removed' \
                             ' from database {1}'.format(name, dbname)
            ret['changes'][name] = 'Absent'
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Schema {0} failed to be removed'.format(name)
            return ret
    else:
        ret['comment'] = 'Schema {0} is not present in database {1},' \
                         ' so it cannot be removed'.format(name, dbname)

    return ret
