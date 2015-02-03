# -*- coding: utf-8 -*-
'''
Module to provide MS SQL Server compatibility to salt.

:depends:   - FreeTDS
            - pymssql Python module

:configuration: In order to connect to MS SQL Server, certain configuration is
    required in minion configs/pillars on the relevant minions. Some sample
    pillars might look like::
        
        mssql.server: 'localhost'
        mssql.port:   1433
        mssql.user:   'sysdba'
        mssql.password:   'Some preferable complex password'
        mssql.database: ''

    The default for the port is '1433' and for the database is '' (empty string);
    in most cases they can be left at the default setting.
    Options that are directly passed into functions will overwrite options from
    configs or pillars.
'''


import logging
from json import JSONEncoder, loads

try:
    import pymssql
    HAS_ALL_IMPORTS = True
except ImportError:
    HAS_ALL_IMPORTS = False


log = logging.getLogger(__name__)


_DEFAULTS = {
    'server': 'localhost',
    'port': 1433,
    'user': 'sysdba',
    'password': '',
    'database': '',
    'as_dict': False
}


def __virtual__():
    '''
    Only load this module if all imports succeeded bin exists
    '''
    if HAS_ALL_IMPORTS:
        return True
    return False


def _get_connection(**kwargs):
    connection_args = {}
    for arg in ('server', 'port', 'user', 'password', 'database', 'as_dict'):
        if arg in kwargs:
            connection_args[arg] = kwargs[arg]
        else:
            connection_args[arg] = __salt__['config.option']('mssql.'+arg, _DEFAULTS.get(arg, None))
    return pymssql.connect(**connection_args)


class _MssqlEncoder(JSONEncoder):
    def default(self, o):
        return str(o)


def tsql_query(query, **kwargs):
    '''
    Run a SQL query and return query result as list of tuples, or a list of dictionaries if as_dict was passed, or an empty list if no data is available.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.tsql_query 'SELECT @@version as version' as_dict=True
    '''
    try:
        cur = _get_connection(**kwargs).cursor()
        cur.execute(query)
        # Making sure the result is JSON serializable
        return loads(_MssqlEncoder().encode({'resultset': cur.fetchall()}))['resultset']
    except Exception as e:
        # Trying to look like the output of cur.fetchall()
        return ( ('Could not run the query', ), (str(e), ) )


def version(**kwargs):
    '''
    Return the version of a MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.version
    '''
    return tsql_query('SELECT @@version', **kwargs)


def role_list(**kwargs):

    '''
    Lists database roles.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_list
    '''
    return tsql_query(query='sp_helprole', as_dict=True, **kwargs)


def role_exists(role, **kwargs):

    '''
    
    Checks if a role exists.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_exists db_owner
    '''
    # We should get one, and only one row
    return len(tsql_query(query='sp_helprole "%s"' % role, as_dict=True, **kwargs)) == 1


def role_create(role, owner=None, **kwargs):
    '''
    Creates a new database role.
    If no owner is specified, the role will be owned by the user that
    executes CREATE ROLE, which is the user argument or mssql.user option.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_create role=product01 owner=sysdba
    '''
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        if owner:
            cur.execute('CREATE ROLE %s AUTHORIZATION %s' % (role, owner))
        else:
            cur.execute('CREATE ROLE %s' % (role))
        conn.autocommit(True)
        conn.close()
        return True
    except Exception as e:
        return 'Could not create the role: {0}'.format(e)


def role_remove(role, **kwargs):
    '''
    Remove a database role.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_create role=test_role01
    '''
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        cur.execute('DROP ROLE %s' % (role))
        conn.autocommit(True)
        conn.close()
        return True
    except Exception as e:
        return 'Could not create the role: {0}'.format(e)

