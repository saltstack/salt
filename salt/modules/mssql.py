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

# Import python libs
from __future__ import absolute_import
from json import JSONEncoder, loads

try:
    import pymssql
    HAS_ALL_IMPORTS = True
except ImportError:
    HAS_ALL_IMPORTS = False


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
    # E0202: 68:_MssqlEncoder.default: An attribute inherited from JSONEncoder hide this method
    def default(self, o):  # pylint: disable=E0202
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
        return (('Could not run the query', ), (str(e), ))


def version(**kwargs):
    '''
    Return the version of a MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.version
    '''
    return tsql_query('SELECT @@version', **kwargs)


def db_list(**kwargs):
    '''
    Return the databse list created on a MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_list
    '''
    return [row[0] for row in tsql_query('SELECT name FROM sys.databases', as_dict=False, **kwargs)]


def db_exists(database_name, **kwargs):
    '''
    Find if a specific database exists on the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_exists database_name='DBNAME'
    '''
    # We should get one, and only one row
    return len(tsql_query("SELECT database_id FROM sys.databases WHERE NAME='{0}'".format(database_name), **kwargs)) == 1


def db_remove(database_name, **kwargs):
    '''
    Drops a specific database from the MS SQL server.
    It will not drop any of 'master', 'model', 'msdb' or 'tempdb'.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_remove database_name='DBNAME'
    '''
    try:
        if db_exists(database_name) and database_name not in ['master', 'model', 'msdb', 'tempdb']:
            conn = _get_connection(**kwargs)
            conn.autocommit(True)
            cur = conn.cursor()
            cur.execute('ALTER DATABASE {0} SET SINGLE_USER WITH ROLLBACK IMMEDIATE'.format(database_name))
            cur.execute('DROP DATABASE {0}'.format(database_name))
            conn.autocommit(False)
            conn.close()
            return True
        else:
            return False
    except Exception as e:
        return 'Could not find the database: {0}'.format(e)


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
    return len(tsql_query(query='sp_helprole "{0}"'.format(role), as_dict=True, **kwargs)) == 1


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
            cur.execute('CREATE ROLE {0} AUTHORIZATION {1}'.format(role, owner))
        else:
            cur.execute('CREATE ROLE {0}'.format(role))
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
        cur.execute('DROP ROLE {0}'.format(role))
        conn.autocommit(True)
        conn.close()
        return True
    except Exception as e:
        return 'Could not create the role: {0}'.format(e)


def login_exists(login, **kwargs):
    '''
    Find if a login exists in the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.login_exists 'LOGIN'
    '''
    try:
        # We should get one, and only one row
        return len(tsql_query(query="SELECT name FROM sys.syslogins WHERE name='{0}'".format(login), **kwargs)) == 1

    except Exception as e:
        return 'Could not find the login: {0}'.format(e)


def user_exists(username, **kwargs):
    '''
    Find if an user exists in a specific database on the MS SQL server.

    Note:
        *database* argument is mandatory

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_exists 'USERNAME' [database='DBNAME']
    '''
    # 'database' argument is mandatory
    if 'database' not in kwargs:
        return False

    # We should get one, and only one row
    return len(tsql_query(query="SELECT name FROM sysusers WHERE name='{0}'".format(username), **kwargs)) == 1


def user_list(**kwargs):
    '''
    Get the user list for a specific database on the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_list [database='DBNAME']
    '''
    return [row[0] for row in tsql_query("SELECT name FROM sysusers where issqluser=1 or isntuser=1", as_dict=False, **kwargs)]


def user_create(username, new_login_password=None, **kwargs):
    '''
    Creates a new user.
    If new_login_password is not specified, the user will be created without a login.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_create USERNAME database=DBNAME [new_login_password=PASSWORD]
    '''
    # 'database' argument is mandatory
    if 'database' not in kwargs:
        return False
    if user_exists(username, **kwargs):
        return False

    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()

        if new_login_password:
            if login_exists(username, **kwargs):
                conn.close()
                return False
            cur.execute("CREATE LOGIN {0} WITH PASSWORD='{1}',check_policy = off".format(username, new_login_password))
            cur.execute("CREATE USER {0} FOR LOGIN {1}".format(username, username))
        else:  # new_login_password is not specified
            cur.execute("CREATE USER {0} WITHOUT LOGIN".format(username))

        conn.autocommit(False)
        conn.close()
        return True
    except Exception as e:
        return 'Could not create the user: {0}'.format(e)


def user_remove(username, **kwargs):
    '''
    Removes an user.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_remove USERNAME database=DBNAME
    '''
    # 'database' argument is mandatory
    if 'database' not in kwargs:
        return False
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        cur.execute("DROP USER {0}".format(username))
        conn.autocommit(False)
        conn.close()
        return True
    except Exception as e:
        return 'Could not create the user: {0}'.format(e)
