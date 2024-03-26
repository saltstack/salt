"""
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
"""

import salt.utils.json

try:
    import pymssql

    HAS_ALL_IMPORTS = True
except ImportError:
    HAS_ALL_IMPORTS = False


_DEFAULTS = {
    "server": "localhost",
    "port": 1433,
    "user": "sysdba",
    "password": "",
    "database": "",
    "as_dict": False,
}


def __virtual__():
    """
    Only load this module if all imports succeeded bin exists
    """
    if HAS_ALL_IMPORTS:
        return True
    return (
        False,
        "The mssql execution module cannot be loaded: the pymssql python library is not"
        " available.",
    )


def _get_connection(**kwargs):
    connection_args = {}
    for arg in ("server", "port", "user", "password", "database", "as_dict"):
        if arg in kwargs:
            connection_args[arg] = kwargs[arg]
        else:
            connection_args[arg] = __salt__["config.option"](
                "mssql." + arg, _DEFAULTS.get(arg, None)
            )
    return pymssql.connect(**connection_args)


class _MssqlEncoder(salt.utils.json.JSONEncoder):
    # E0202: 68:_MssqlEncoder.default: An attribute inherited from JSONEncoder hide this method
    def default(self, o):  # pylint: disable=E0202
        return str(o)


def tsql_query(query, **kwargs):
    """
    Run a SQL query and return query result as list of tuples, or a list of dictionaries if as_dict was passed, or an empty list if no data is available.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.tsql_query 'SELECT @@version as version' as_dict=True
    """
    try:
        cur = _get_connection(**kwargs).cursor()
        cur.execute(query)
        # Making sure the result is JSON serializable
        return salt.utils.json.loads(
            _MssqlEncoder().encode({"resultset": cur.fetchall()})
        )["resultset"]
    except Exception as err:  # pylint: disable=broad-except
        # Trying to look like the output of cur.fetchall()
        return (("Could not run the query",), (str(err),))


def version(**kwargs):
    """
    Return the version of a MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.version
    """
    return tsql_query("SELECT @@version", **kwargs)


def db_list(**kwargs):
    """
    Return the database list created on a MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_list
    """
    return [
        row[0]
        for row in tsql_query("SELECT name FROM sys.databases", as_dict=False, **kwargs)
    ]


def db_exists(database_name, **kwargs):
    """
    Find if a specific database exists on the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_exists database_name='DBNAME'
    """
    # We should get one, and only one row
    return (
        len(
            tsql_query(
                "SELECT database_id FROM sys.databases WHERE NAME='{}'".format(
                    database_name
                ),
                **kwargs,
            )
        )
        == 1
    )


def db_create(database, containment="NONE", new_database_options=None, **kwargs):
    """
    Creates a new database.
    Does not update options of existing databases.
    new_database_options can only be a list of strings

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_create DB_NAME
    """
    if containment not in ["NONE", "PARTIAL"]:
        return "CONTAINMENT can be one of NONE and PARTIAL"
    sql = f"CREATE DATABASE [{database}] CONTAINMENT = {containment} "
    if new_database_options:
        sql += " WITH " + ", ".join(new_database_options)
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not create the database: {e}"
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True


def db_remove(database_name, **kwargs):
    """
    Drops a specific database from the MS SQL server.
    It will not drop any of 'master', 'model', 'msdb' or 'tempdb'.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.db_remove database_name='DBNAME'
    """
    try:
        if db_exists(database_name, **kwargs) and database_name not in [
            "master",
            "model",
            "msdb",
            "tempdb",
        ]:
            conn = _get_connection(**kwargs)
            conn.autocommit(True)
            cur = conn.cursor()
            cur.execute(
                "ALTER DATABASE {} SET SINGLE_USER WITH ROLLBACK IMMEDIATE".format(
                    database_name
                )
            )
            cur.execute(f"DROP DATABASE {database_name}")
            conn.autocommit(False)
            conn.close()
            return True
        else:
            return False
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not find the database: {e}"


def role_list(**kwargs):
    """
    Lists database roles.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_list
    """
    return tsql_query(query="sp_helprole", as_dict=True, **kwargs)


def role_exists(role, **kwargs):
    """
    Checks if a role exists.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_exists db_owner
    """
    # We should get one, and only one row
    return len(tsql_query(query=f'sp_helprole "{role}"', as_dict=True, **kwargs)) == 1


def role_create(role, owner=None, grants=None, **kwargs):
    """
    Creates a new database role.
    If no owner is specified, the role will be owned by the user that
    executes CREATE ROLE, which is the user argument or mssql.user option.
    grants is list of strings.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_create role=product01 owner=sysdba grants='["SELECT", "INSERT", "UPDATE", "DELETE", "EXECUTE"]'
    """
    if not grants:
        grants = []

    sql = f"CREATE ROLE {role}"
    if owner:
        sql += f" AUTHORIZATION {owner}"
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
        for grant in grants:
            conn.cursor().execute(f"GRANT {grant} TO [{role}]")
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not create the role: {e}"
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True


def role_remove(role, **kwargs):
    """
    Remove a database role.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.role_create role=test_role01
    """
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        cur.execute(f"DROP ROLE {role}")
        conn.autocommit(True)
        conn.close()
        return True
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not remove the role: {e}"


def login_exists(login, domain="", **kwargs):
    """
    Find if a login exists in the MS SQL server.
    domain, if provided, will be prepended to login

    CLI Example:

    .. code-block:: bash

        salt minion mssql.login_exists 'LOGIN'
    """
    if domain:
        login = f"{domain}\\{login}"
    try:
        # We should get one, and only one row
        return (
            len(
                tsql_query(
                    query="SELECT name FROM sys.syslogins WHERE name='{}'".format(
                        login
                    ),
                    **kwargs,
                )
            )
            == 1
        )

    except Exception as e:  # pylint: disable=broad-except
        return f"Could not find the login: {e}"


def login_create(
    login,
    new_login_password=None,
    new_login_domain="",
    new_login_roles=None,
    new_login_options=None,
    **kwargs,
):
    """
    Creates a new login.  Does not update password of existing logins.  For
    Windows authentication, provide ``new_login_domain``.  For SQL Server
    authentication, prvide ``new_login_password``.  Since hashed passwords are
    *varbinary* values, if the ``new_login_password`` is 'int / long', it will
    be considered to be HASHED.

    new_login_roles
        a list of SERVER roles

    new_login_options
        a list of strings

    CLI Example:

    .. code-block:: bash

        salt minion mssql.login_create LOGIN_NAME database=DBNAME [new_login_password=PASSWORD]
    """
    # One and only one of password and domain should be specifies
    if bool(new_login_password) == bool(new_login_domain):
        return False
    if login_exists(login, new_login_domain, **kwargs):
        return False
    if new_login_domain:
        login = f"{new_login_domain}\\{login}"
    if not new_login_roles:
        new_login_roles = []
    if not new_login_options:
        new_login_options = []

    sql = f"CREATE LOGIN [{login}] "
    if new_login_domain:
        sql += " FROM WINDOWS "
    elif isinstance(new_login_password, int):
        new_login_options.insert(0, f"PASSWORD=0x{new_login_password:x} HASHED")
    else:  # Plain test password
        new_login_options.insert(0, f"PASSWORD=N'{new_login_password}'")
    if new_login_options:
        sql += " WITH " + ", ".join(new_login_options)
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
        for role in new_login_roles:
            conn.cursor().execute(f"ALTER SERVER ROLE [{role}] ADD MEMBER [{login}]")
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not create the login: {e}"
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True


def login_remove(login, **kwargs):
    """
    Removes an login.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.login_remove LOGINNAME
    """
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        cur.execute(f"DROP LOGIN [{login}]")
        conn.autocommit(False)
        conn.close()
        return True
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not remove the login: {e}"


def user_exists(username, domain="", database=None, **kwargs):
    """
    Find if an user exists in a specific database on the MS SQL server.
    domain, if provided, will be prepended to username

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_exists 'USERNAME' [database='DBNAME']
    """
    if domain:
        username = f"{domain}\\{username}"
    if database:
        kwargs["database"] = database
    # We should get one, and only one row
    return (
        len(
            tsql_query(
                query=f"SELECT name FROM sysusers WHERE name='{username}'", **kwargs
            )
        )
        == 1
    )


def user_list(**kwargs):
    """
    Get the user list for a specific database on the MS SQL server.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_list [database='DBNAME']
    """
    return [
        row[0]
        for row in tsql_query(
            "SELECT name FROM sysusers where issqluser=1 or isntuser=1",
            as_dict=False,
            **kwargs,
        )
    ]


def user_create(
    username, login=None, domain="", database=None, roles=None, options=None, **kwargs
):
    """
    Creates a new user.  If login is not specified, the user will be created
    without a login.  domain, if provided, will be prepended to username.
    options can only be a list of strings

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_create USERNAME database=DBNAME
    """
    if domain and not login:
        return "domain cannot be set without login"
    if user_exists(username, domain, **kwargs):
        return f"User {username} already exists"
    if domain:
        username = f"{domain}\\{username}"
        login = f"{domain}\\{login}" if login else login
    if database:
        kwargs["database"] = database
    if not roles:
        roles = []
    if not options:
        options = []

    sql = f"CREATE USER [{username}] "
    if login:
        # If the login does not exist, user creation will throw
        # if not login_exists(name, **kwargs):
        #     return False
        sql += f" FOR LOGIN [{login}]"
    else:  # Plain test password
        sql += " WITHOUT LOGIN"
    if options:
        sql += " WITH " + ", ".join(options)
    conn = None
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        # cur = conn.cursor()
        # cur.execute(sql)
        conn.cursor().execute(sql)
        for role in roles:
            conn.cursor().execute(f"ALTER ROLE [{role}] ADD MEMBER [{username}]")
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not create the user: {e}"
    finally:
        if conn:
            conn.autocommit(False)
            conn.close()
    return True


def user_remove(username, **kwargs):
    """
    Removes an user.

    CLI Example:

    .. code-block:: bash

        salt minion mssql.user_remove USERNAME database=DBNAME
    """
    # 'database' argument is mandatory
    if "database" not in kwargs:
        return False
    try:
        conn = _get_connection(**kwargs)
        conn.autocommit(True)
        cur = conn.cursor()
        cur.execute(f"DROP USER {username}")
        conn.autocommit(False)
        conn.close()
        return True
    except Exception as e:  # pylint: disable=broad-except
        return f"Could not remove the user: {e}"
