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
    return (False, 'The mssql execution module cannot be loaded: the pymssql python library is not available.')


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


def login_exists(login, domain=None, **kwargs):
    '''
    Find if a login exists in the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.login_exists 'LOGIN'
    '''
    if domain:
        login = '{0}\{1}'.format(domain, login)
    try:
        # We should get one, and only one row
        return len(tsql_query(query="SELECT name FROM sys.syslogins WHERE name='{0}'".format(login), **kwargs)) == 1

    except Exception as e:
        return 'Could not find the login: {0}'.format(e)


def login_create(login, new_login_password=None, new_login_domain=None, new_login_options=[], **kwargs):
    '''
    Creates a new login.
    Does not update password of existing logins.
    For Windows authentication, provide new_login_domain.
    For SQL Server authentication, prvide new_login_password.
    Since hashed passwords are varbinary values, if the
    new_login_password is 'long', it will be considered
    to be HASHED.
    new_login_options can only be a list of strings

    CLI Example:
    .. code-block:: bash
        salt minion mssql.login_create LOGIN_NAME database=DBNAME [new_login_password=PASSWORD]
    '''
    # One and only one of password and domain should be specifies
    if bool(new_login_password) == bool(new_login_domain):
        return False
    if login_exists(login, new_login_domain, **kwargs):
        return False
    if new_login_domain:
        login = '{0}\{1}'.format(new_login_domain, login)

    sql = "CREATE LOGIN [{0}] ".format(login)
    if new_login_domain:
        sql += " FROM WINDOWS "
    elif type(new_login_password) is long:
        new_login_options.insert(0, "PASSWORD=0x{0:x} HASHED".format(new_login_password))
    else:  # Plain test password
        new_login_options.insert(0, "PASSWORD=N'{0}'".format(new_login_password))
    if new_login_options:
        sql += ' WITH ' + ', '.join(new_login_options)
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
    except Exception as e:
        return 'Could not create the login: {0}'.format(e)
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True



def user_exists(username, domain=None, database=None, **kwargs):
    '''
    Find if an user exists in a specific database on the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_exists 'USERNAME' [database='DBNAME']
    '''
    if domain:
        username = '{0}\{1}'.format(domain, username)
    if database:
        kwargs['database'] = database
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


def user_create(username, login=None, domain=None, database=None, roles=[], options=[], **kwargs):
    '''
    Creates a new user.
    If login is not specified, the user will be created without a login.
    options can only be a list of strings

    CLI Example:
    .. code-block:: bash
        salt minion mssql.user_create USERNAME database=DBNAME
    '''
    if domain and not login:
        return 'domain cannot be set without login'
        return False
    if user_exists(username, domain, **kwargs):
        return 'User {0} already exists'.format(username)
        return False
    if domain:
        username = '{0}\{1}'.format(domain, username)
        login    = '{0}\{1}'.format(domain, login) if login else login
    if database:
        kwargs['database'] = database

    sql = "CREATE USER [{0}] ".format(login)
    if login:
        # If the login does not exist, user creation will throw
        # if not login_exists(name, **kwargs):
        #     return False
        sql += " FOR LOGIN [{0}]".format(login)
    else:  # Plain test password
        sql += " WITHOUT LOGIN"
    if options:
        sql += ' WITH ' + ', '.join(options)
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
    except Exception as e:
        return 'Could not create the user: {0}'.format(e)
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True


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
