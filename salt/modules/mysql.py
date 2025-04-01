"""
Module to provide MySQL compatibility to salt.

:depends:   - Python module: MySQLdb, mysqlclient, or PyMYSQL

:configuration: In order to connect to MySQL, certain configuration is required
    in either the relevant minion config (/etc/salt/minion), or pillar.

    Some sample configs might look like::

        mysql.host: 'localhost'
        mysql.port: 3306
        mysql.user: 'root'
        mysql.pass: ''
        mysql.db: 'mysql'
        mysql.unix_socket: '/tmp/mysql.sock'
        mysql.charset: 'utf8'

    You can also use a defaults file::

        mysql.default_file: '/etc/mysql/debian.cnf'

.. versionchanged:: 2014.1.0
    \'charset\' connection argument added. This is a MySQL charset, not a python one.
.. versionchanged:: 0.16.2
    Connection arguments from the minion config file can be overridden on the
    CLI by using the arguments defined :mod:`here <salt.states.mysql_user>`.
    Additionally, it is now possible to setup a user with no password.
"""

import copy
import hashlib
import logging
import os
import re
import shlex
import sys
import time

import salt.utils.data
import salt.utils.files
import salt.utils.stringutils

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.converters
    import MySQLdb.cursors
    from MySQLdb import OperationalError
    from MySQLdb.constants import CLIENT, FIELD_TYPE, FLAG
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.converters
        import MySQLdb.cursors
        from MySQLdb import OperationalError
        from MySQLdb.constants import CLIENT, FIELD_TYPE, FLAG
    except ImportError:
        MySQLdb = None

try:
    import sqlparse

    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False

log = logging.getLogger(__name__)

__grants__ = [
    "ALL PRIVILEGES",
    "ALTER",
    "ALTER ROUTINE",
    "BACKUP_ADMIN",
    "BINLOG_ADMIN",
    "BINLOG ADMIN",  # MariaDB since 10.5.2
    "BINLOG MONITOR",  # MariaDB since 10.5.2
    "BINLOG REPLAY",  # MariaDB since 10.5.2
    "CONNECTION_ADMIN",
    "CONNECTION ADMIN",  # MariaDB since 10.5.2
    "CREATE",
    "CREATE ROLE",
    "CREATE ROUTINE",
    "CREATE TABLESPACE",
    "CREATE TEMPORARY TABLES",
    "CREATE USER",
    "CREATE VIEW",
    "DELETE",
    "DELETE HISTORY",  # MariaDB since 10.3.4
    "DROP",
    "DROP ROLE",
    "ENCRYPTION_KEY_ADMIN",
    "EVENT",
    "EXECUTE",
    "FEDERATED ADMIN",  # MariaDB since 10.5.2
    "FILE",
    "GRANT OPTION",
    "GROUP_REPLICATION_ADMIN",
    "INDEX",
    "INSERT",
    "LOCK TABLES",
    "PERSIST_RO_VARIABLES_ADMIN",
    "PROCESS",
    "READ_ONLY ADMIN",  # MariaDB since 10.5.2
    "REFERENCES",
    "RELOAD",
    "REPLICA MONITOR",  # MariaDB since 10.5.9
    "REPLICATION CLIENT",
    "REPLICATION MASTER ADMIN",  # MariaDB since 10.5.2
    "REPLICATION REPLICA",  # MariaDB since 10.5.1
    "REPLICATION SLAVE",
    "REPLICATION_SLAVE_ADMIN",
    "REPLICATION SLAVE ADMIN",  # MariaDB since 10.5.2
    "RESOURCE_GROUP_ADMIN",
    "RESOURCE_GROUP_USER",
    "ROLE_ADMIN",
    "SELECT",
    "SET USER",  # MariaDB since 10.5.2
    "SET_USER_ID",
    "SERVICE_CONNECTION_ADMIN",  # MySQL since 8.0.14
    "SHOW DATABASES",
    "SHOW VIEW",
    "SHUTDOWN",
    "SLAVE MONITOR",  # MariaDB since 10.5.9
    "SUPER",
    "SYSTEM_VARIABLES_ADMIN",
    "TRIGGER",
    "UPDATE",
    "USAGE",
    "XA_RECOVER_ADMIN",
]

__ssl_options_parameterized__ = ["CIPHER", "ISSUER", "SUBJECT"]
__ssl_options__ = __ssl_options_parameterized__ + ["SSL", "X509"]

__all_privileges__ = [
    "ALTER",
    "ALTER ROUTINE",
    "BACKUP_ADMIN",
    "BINLOG_ADMIN",
    "CONNECTION_ADMIN",
    "CREATE",
    "CREATE ROLE",
    "CREATE ROUTINE",
    "CREATE TABLESPACE",
    "CREATE TEMPORARY TABLES",
    "CREATE USER",
    "CREATE VIEW",
    "DELETE",
    "DROP",
    "DROP ROLE",
    "ENCRYPTION_KEY_ADMIN",
    "EVENT",
    "EXECUTE",
    "FILE",
    "GROUP_REPLICATION_ADMIN",
    "INDEX",
    "INSERT",
    "LOCK TABLES",
    "PERSIST_RO_VARIABLES_ADMIN",
    "PROCESS",
    "REFERENCES",
    "RELOAD",
    "REPLICATION CLIENT",
    "REPLICATION SLAVE",
    "REPLICATION_SLAVE_ADMIN",
    "RESOURCE_GROUP_ADMIN",
    "RESOURCE_GROUP_USER",
    "ROLE_ADMIN",
    "SELECT",
    "SET_USER_ID",
    "SHOW DATABASES",
    "SHOW VIEW",
    "SHUTDOWN",
    "SUPER",
    "SYSTEM_VARIABLES_ADMIN",
    "TRIGGER",
    "UPDATE",
    "XA_RECOVER_ADMIN",
]

r'''
DEVELOPER NOTE: ABOUT arguments management, escapes, formats, arguments and
security of SQL.

A general rule of SQL security is to use queries with _execute call in this
code using args parameter to let MySQLdb manage the arguments proper escaping.
Another way of escaping values arguments could be '{0!r}'.format(), using
__repr__ to ensure things get properly used as strings. But this could lead
to three problems:

 * In ANSI mode, which is available on MySQL, but not by default, double
quotes " should not be used as a string delimiters, in ANSI mode this is an
identifier delimiter (like `).

 * Some rare exploits with bad multibytes management, either on python or
MySQL could defeat this barrier, bindings internal escape functions
should manage theses cases.

 * Unicode strings in Python 2 will include the 'u' before the repr'ed string,
   like so:

    Python 2.7.10 (default, May 26 2015, 04:16:29)
    [GCC 5.1.0] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> u'something something {0!r}'.format(u'foo')
    u"something something u'foo'"

So query with arguments should use a paramstyle defined in PEP249:

http://www.python.org/dev/peps/pep-0249/#paramstyle
We use pyformat, which means 'SELECT * FROM foo WHERE bar=%(myval)s'
used with {'myval': 'some user input'}

So far so good. But this cannot be used for identifier escapes. Identifiers
are database names, table names and column names. Theses names are not values
and do not follow the same escape rules (see quote_identifier function for
details on `_ and % escape policies on identifiers). Using value escaping on
identifier could fool the SQL engine (badly escaping quotes and not doubling
` characters. So for identifiers a call to quote_identifier should be done and
theses identifiers should then be added in strings with format, but without
__repr__ filter.

Note also that when using query with arguments in _execute all '%' characters
used in the query should get escaped to '%%' fo MySQLdb, but should not be
escaped if the query runs without arguments. This is managed by _execute() and
quote_identifier. This is not the same as escaping '%' to '\%' or '_' to '\%'
when using a LIKE query (example in db_exists), as this escape is there to
avoid having _ or % characters interpreted in LIKE queries. The string parted
of the first query could become (still used with args dictionary for myval):
'SELECT * FROM {0} WHERE bar=%(myval)s'.format(quote_identifier('user input'))

Check integration tests if you find a hole in theses strings and escapes rules

Finally some examples to sum up.

Given a name f_o%o`b'a"r, in python that would be """f_o%o`b'a"r""". I'll
avoid python syntax for clarity:

The MySQL way of writing this name is:

value                         : 'f_o%o`b\'a"r' (managed by MySQLdb)
identifier                    : `f_o%o``b'a"r`
db identifier in general GRANT: `f\_o\%o``b'a"r`
db identifier in table GRANT  : `f_o%o``b'a"r`
in mySQLdb, query with args   : `f_o%%o``b'a"r` (as identifier)
in mySQLdb, query without args: `f_o%o``b'a"r` (as identifier)
value in a LIKE query         : 'f\_o\%o`b\'a"r' (quotes managed by MySQLdb)

And theses could be mixed, in a like query value with args: 'f\_o\%%o`b\'a"r'
'''


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


def __mysql_hash_password(password):
    _password = hashlib.sha1(password.encode()).digest()
    _password = f"*{hashlib.sha1(_password).hexdigest().upper()}"
    return _password


def __check_table(name, table, **connection_args):
    dbc = _connect(**connection_args)
    if dbc is None:
        return {}
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    s_name = quote_identifier(name)
    s_table = quote_identifier(table)
    # identifiers cannot be used as values
    qry = f"CHECK TABLE {s_name}.{s_table}"
    _execute(cur, qry)
    results = cur.fetchall()
    log.debug(results)
    return results


def __repair_table(name, table, **connection_args):
    dbc = _connect(**connection_args)
    if dbc is None:
        return {}
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    s_name = quote_identifier(name)
    s_table = quote_identifier(table)
    # identifiers cannot be used as values
    qry = f"REPAIR TABLE {s_name}.{s_table}"
    _execute(cur, qry)
    results = cur.fetchall()
    log.debug(results)
    return results


def __optimize_table(name, table, **connection_args):
    dbc = _connect(**connection_args)
    if dbc is None:
        return {}
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    s_name = quote_identifier(name)
    s_table = quote_identifier(table)
    # identifiers cannot be used as values
    qry = f"OPTIMIZE TABLE {s_name}.{s_table}"
    _execute(cur, qry)
    results = cur.fetchall()
    log.debug(results)
    return results


def __password_column(**connection_args):
    if "mysql.password_column" in __context__:
        return __context__["mysql.password_column"]

    dbc = _connect(**connection_args)
    if dbc is None:
        return "Password"
    cur = dbc.cursor()
    qry = (
        "SELECT column_name from information_schema.COLUMNS "
        "WHERE table_schema=%(schema)s and table_name=%(table)s "
        "and column_name=%(column)s"
    )
    args = {"schema": "mysql", "table": "user", "column": "Password"}
    _execute(cur, qry, args)
    if int(cur.rowcount) > 0:
        __context__["mysql.password_column"] = "Password"
    else:
        __context__["mysql.password_column"] = "authentication_string"

    return __context__["mysql.password_column"]


def __get_auth_plugin(user, host, **connection_args):
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    try:
        qry = "SELECT plugin FROM mysql.user WHERE User=%(user)s and Host=%(host)s"
        args = {"user": user, "host": host}
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return "mysql_native_password"
    results = cur.fetchall()
    log.debug(results)

    if results:
        return results[0].get("plugin", "mysql_native_password")
    else:
        return "mysql_native_password"


def _connect(**kwargs):
    """
    wrap authentication credentials here
    """
    connargs = dict()

    def _connarg(name, key=None, get_opts=True):
        """
        Add key to connargs, only if name exists in our kwargs or,
        if get_opts is true, as mysql.<name> in __opts__ or __pillar__

        If get_opts is true, evaluate in said order - kwargs, opts
        then pillar. To avoid collision with other functions,
        kwargs-based connection arguments are prefixed with 'connection_'
        (i.e. 'connection_host', 'connection_user', etc.).
        """
        if key is None:
            key = name

        if name in kwargs:
            connargs[key] = kwargs[name]
        elif get_opts:
            prefix = "connection_"
            if name.startswith(prefix):
                try:
                    name = name[len(prefix) :]
                except IndexError:
                    return
            val = __salt__["config.option"](f"mysql.{name}", None)
            if val is not None:
                connargs[key] = val

    # If a default file is explicitly passed to kwargs, don't grab the
    # opts/pillar settings, as it can override info in the defaults file
    if "connection_default_file" in kwargs:
        get_opts = False
    else:
        get_opts = True

    connargs["client_flag"] = 0

    available_client_flags = {}
    for flag in dir(CLIENT):
        if not flag.startswith("__"):
            available_client_flags[flag.lower()] = getattr(CLIENT, flag)

    for flag in kwargs.get("client_flags", []):
        if available_client_flags.get(flag):
            connargs["client_flag"] |= available_client_flags[flag]
        else:
            log.error("MySQL client flag %s not valid, ignoring.", flag)

    _connarg("connection_host", "host", get_opts)
    _connarg("connection_user", "user", get_opts)
    _connarg("connection_pass", "passwd", get_opts)
    _connarg("connection_port", "port", get_opts)
    _connarg("connection_db", "db", get_opts)
    _connarg("connection_conv", "conv", get_opts)
    _connarg("connection_unix_socket", "unix_socket", get_opts)
    _connarg("connection_default_file", "read_default_file", get_opts)
    _connarg("connection_default_group", "read_default_group", get_opts)
    # MySQLdb states that this is required for charset usage
    # but in fact it's more than it's internally activated
    # when charset is used, activating use_unicode here would
    # retrieve utf8 strings as unicode() objects in salt
    # and we do not want that.
    # _connarg('connection_use_unicode', 'use_unicode')
    connargs["use_unicode"] = False
    _connarg("connection_charset", "charset")
    # Ensure MySQldb knows the format we use for queries with arguments
    MySQLdb.paramstyle = "pyformat"

    for key in copy.deepcopy(connargs):
        if not connargs[key]:
            del connargs[key]

    if (
        connargs.get("passwd", True) is None
    ):  # If present but set to None. (Extreme edge case.)
        log.warning("MySQL password of None found. Attempting passwordless login.")
        connargs.pop("passwd")
    try:
        dbc = MySQLdb.connect(**connargs)
    except OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return None
    except MySQLdb.err.InternalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return None

    dbc.autocommit(True)
    return dbc


def _grant_to_tokens(grant):
    """

    This should correspond fairly closely to the YAML rendering of a
    mysql_grants state which comes out as follows:

     OrderedDict([
        ('whatever_identifier',
         OrderedDict([
            ('mysql_grants.present',
             [
              OrderedDict([('database', 'testdb.*')]),
              OrderedDict([('user', 'testuser')]),
              OrderedDict([('grant', 'ALTER, SELECT, LOCK TABLES')]),
              OrderedDict([('host', 'localhost')])
             ]
            )
         ])
        )
     ])

    :param grant: An un-parsed MySQL GRANT statement str, like
        "GRANT SELECT, ALTER, LOCK TABLES ON `mydb`.* TO 'testuser'@'localhost'"
        or a dictionary with 'qry' and 'args' keys for 'user' and 'host'.
    :return:
        A Python dict with the following keys/values:
            - user: MySQL User
            - host: MySQL host
            - grant: [grant1, grant2] (ala SELECT, USAGE, etc)
            - database: MySQL DB
    """
    log.debug("_grant_to_tokens entry '%s'", grant)
    dict_mode = False
    if isinstance(grant, dict):
        dict_mode = True
        # Everything coming in dictionary form was made for a MySQLdb execute
        # call and contain a '%%' escaping of '%' characters for MySQLdb
        # that we should remove here.
        grant_sql = grant.get("qry", "undefined").replace("%%", "%")
        sql_args = grant.get("args", {})
        host = sql_args.get("host", "undefined")
        user = sql_args.get("user", "undefined")
    else:
        grant_sql = grant
        user = ""
    # the replace part is for presence of ` character in the db name
    # the shell escape is \` but mysql escape is ``. Spaces should not be
    # exploded as users or db names could contain spaces.
    # Examples of splitting:
    # "GRANT SELECT, LOCK TABLES, UPDATE, CREATE ON `test ``(:=saltdb)`.*
    #                                   TO 'foo'@'localhost' WITH GRANT OPTION"
    # ['GRANT', 'SELECT', ',', 'LOCK', 'TABLES', ',', 'UPDATE', ',', 'CREATE',
    #  'ON', '`test `', '`(:=saltdb)`', '.', '*', 'TO', "'foo'", '@',
    # "'localhost'", 'WITH', 'GRANT', 'OPTION']
    #
    # 'GRANT SELECT, INSERT, UPDATE, CREATE ON `te s.t\'"sa;ltdb`.`tbl ``\'"xx`
    #                                   TO \'foo \' bar\'@\'localhost\''
    # ['GRANT', 'SELECT', ',', 'INSERT', ',', 'UPDATE', ',', 'CREATE', 'ON',
    #  '`te s.t\'"sa;ltdb`', '.', '`tbl `', '`\'"xx`', 'TO', "'foo '", "bar'",
    #  '@', "'localhost'"]
    #
    # "GRANT USAGE ON *.* TO 'user \";--,?:&/\\'@'localhost'"
    # ['GRANT', 'USAGE', 'ON', '*', '.', '*', 'TO', '\'user ";--,?:&/\\\'',
    #  '@', "'localhost'"]
    lex = shlex.shlex(grant_sql)
    lex.quotes = "'`"
    lex.whitespace_split = False
    lex.commenters = ""
    lex.wordchars += '"'
    exploded_grant = list(lex)
    grant_tokens = []
    multiword_statement = []
    position_tracker = 1  # Skip the initial 'GRANT' word token
    database = ""
    phrase = "grants"
    column = False
    current_grant = ""

    for token in exploded_grant[position_tracker:]:

        if token == "," and phrase == "grants":
            position_tracker += 1
            continue

        if token == "(" and phrase == "grants":
            position_tracker += 1
            column = True
            continue

        if token == ")" and phrase == "grants":
            position_tracker += 1
            column = False
            continue

        if token == "ON" and phrase == "grants":
            phrase = "db"
            position_tracker += 1
            continue

        elif token == "TO" and phrase == "tables":
            phrase = "user"
            position_tracker += 1
            continue

        elif token == "@" and phrase == "pre-host":
            phrase = "host"
            position_tracker += 1
            continue

        if phrase == "grants":
            # Read-ahead
            if (
                exploded_grant[position_tracker + 1] == ","
                or exploded_grant[position_tracker + 1] == "ON"
                or exploded_grant[position_tracker + 1] in ["(", ")"]
            ):
                # End of token detected
                if multiword_statement:
                    multiword_statement.append(token)
                    grant_tokens.append(" ".join(multiword_statement))
                    multiword_statement = []
                else:
                    if not column:
                        current_grant = token
                    else:
                        token = f"{current_grant}.{token}"
                    grant_tokens.append(token)
            else:  # This is a multi-word, ala LOCK TABLES
                multiword_statement.append(token)

        elif phrase == "db":
            # the shlex splitter may have split on special database characters `
            database += token
            # Read-ahead
            try:
                if exploded_grant[position_tracker + 1] == ".":
                    phrase = "tables"
            except IndexError:
                break

        elif phrase == "tables":
            database += token

        elif phrase == "user":
            if dict_mode:
                break
            else:
                user += token
                # Read-ahead
                if exploded_grant[position_tracker + 1] == "@":
                    phrase = "pre-host"

        elif phrase == "host":
            host = token
            break

        position_tracker += 1

    try:
        if not dict_mode:
            user = user.strip("'")
            host = host.strip("'")
        log.debug(
            "grant to token '%s'::'%s'::'%s'::'%s'", user, host, grant_tokens, database
        )
    except UnboundLocalError:
        host = ""

    return dict(user=user, host=host, grant=grant_tokens, database=database)


def _resolve_grant_aliases(grants, server_version):
    """

    There can be a situation where the database supports grants "A" and "B", where
    "B" is an alias for "A". In that case, when you want to grant "B" to a user,
    the database will actually report it added "A". We need to resolve those
    aliases to not report (wrong) errors.

    :param grants: the tokenized grants

    :param server_version: version string of the connected database

    """
    if "MariaDB" not in server_version:
        return grants

    mariadb_version_compare_replication_replica = "10.5.1"
    mariadb_version_compare_binlog_monitor = "10.5.2"
    mariadb_version_compare_slave_monitor = "10.5.9"

    resolved_tokens = []

    for token in grants:
        if (
            salt.utils.versions.version_cmp(
                server_version, mariadb_version_compare_replication_replica
            )
            >= 0
        ):
            if token == "REPLICATION REPLICA":
                # https://mariadb.com/kb/en/grant/#replication-replica
                resolved_tokens.append("REPLICATION SLAVE")
                continue

        if (
            salt.utils.versions.version_cmp(
                server_version, mariadb_version_compare_binlog_monitor
            )
            >= 0
        ):
            if token == "REPLICATION CLIENT":
                # https://mariadb.com/kb/en/grant/#replication-client
                resolved_tokens.append("BINLOG MONITOR")
                continue

        if (
            salt.utils.versions.version_cmp(
                server_version, mariadb_version_compare_slave_monitor
            )
            >= 0
        ):
            if token == "REPLICA MONITOR":
                # https://mariadb.com/kb/en/grant/#replica-monitor
                resolved_tokens.append("SLAVE MONITOR")
                continue

        resolved_tokens.append(token)

    return resolved_tokens


def quote_identifier(identifier, for_grants=False):
    r"""
    Return an identifier name (column, table, database, etc) escaped for MySQL

    This means surrounded by "`" character and escaping this character inside.
    It also means doubling the '%' character for MySQLdb internal usage.

    :param identifier: the table, column or database identifier

    :param for_grants: is False by default, when using database names on grant
     queries you should set it to True to also escape "_" and "%" characters as
     requested by MySQL. Note that theses characters should only be escaped when
     requesting grants on the database level (`my\_\%db`.*) but not for table
     level grants (`my_%db`.`foo`)

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.quote_identifier 'foo`bar'
    """
    if for_grants:
        return (
            "`"
            + identifier.replace("`", "``").replace("_", r"\_").replace("%", r"%%")
            + "`"
        )
    else:
        return "`" + identifier.replace("`", "``").replace("%", "%%") + "`"


def _execute(cur, qry, args=None):
    """
    Internal wrapper around MySQLdb cursor.execute() function

    MySQLDb does not apply the same filters when arguments are used with the
    query. For example '%' characters on the query must be encoded as '%%' and
    will be restored as '%' when arguments are applied. But when there're no
    arguments the '%%' is not managed. We cannot apply Identifier quoting in a
    predictable way if the query are not always applying the same filters. So
    this wrapper ensure this escape is not made if no arguments are used.
    """
    if args is None or args == {}:
        qry = qry.replace("%%", "%")
        log.debug("Doing query: %s", qry)
        return cur.execute(qry)
    else:
        log.debug("Doing query: %s args: %s ", qry, repr(args))
        return cur.execute(qry, args)


def _sanitize_comments(content):
    # Remove comments which might affect line by line parsing
    # Regex should remove any text beginning with # (or --) not inside of ' or "
    if not HAS_SQLPARSE:
        log.error(
            "_sanitize_comments unavailable, no python sqlparse library installed."
        )
        return content

    return sqlparse.format(content, strip_comments=True)


def query(database, query, **connection_args):
    """
    Run an arbitrary SQL query and return the results or
    the number of affected rows.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.query mydb "UPDATE mytable set myfield=1 limit 1"

    Return data:

    .. code-block:: python

        {'query time': {'human': '39.0ms', 'raw': '0.03899'}, 'rows affected': 1L}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.query mydb "SELECT id,name,cash from users limit 3"

    Return data:

    .. code-block:: python

        {'columns': ('id', 'name', 'cash'),
            'query time': {'human': '1.0ms', 'raw': '0.001'},
            'results': ((1L, 'User 1', Decimal('110.000000')),
                        (2L, 'User 2', Decimal('215.636756')),
                        (3L, 'User 3', Decimal('0.040000'))),
            'rows returned': 3L}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.query mydb 'INSERT into users values (null,"user 4", 5)'

    Return data:

    .. code-block:: python

        {'query time': {'human': '25.6ms', 'raw': '0.02563'}, 'rows affected': 1L}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.query mydb 'DELETE from users where id = 4 limit 1'

    Return data:

    .. code-block:: python

        {'query time': {'human': '39.0ms', 'raw': '0.03899'}, 'rows affected': 1L}

    Jinja Example: Run a query on ``mydb`` and use row 0, column 0's data.

    .. code-block:: jinja

        {{ salt['mysql.query']('mydb', 'SELECT info from mytable limit 1')['results'][0][0] }}
    """
    # Doesn't do anything about sql warnings, e.g. empty values on an insert.
    # I don't think it handles multiple queries at once, so adding "commit"
    # might not work.

    # The following 3 lines stops MySQLdb from converting the MySQL results
    # into Python objects. It leaves them as strings.
    orig_conv = MySQLdb.converters.conversions
    conv_iter = iter(orig_conv)
    conv = dict(zip(conv_iter, [str] * len(orig_conv)))

    # some converters are lists, do not break theses
    conv_mysqldb = {"MYSQLDB": True}
    if conv_mysqldb.get(MySQLdb.__package__.upper()):
        conv[FIELD_TYPE.BLOB] = [
            (FLAG.BINARY, str),
        ]
        conv[FIELD_TYPE.STRING] = [
            (FLAG.BINARY, str),
        ]
        conv[FIELD_TYPE.VAR_STRING] = [
            (FLAG.BINARY, str),
        ]
        conv[FIELD_TYPE.VARCHAR] = [
            (FLAG.BINARY, str),
        ]

    connection_args.update({"connection_db": database, "connection_conv": conv})
    dbc = _connect(**connection_args)
    if dbc is None:
        return {}
    cur = dbc.cursor()
    start = time.time()
    log.debug("Using db: %s to run query %s", database, query)
    try:
        affected = _execute(cur, query)
    except OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False
    results = cur.fetchall()
    elapsed = time.time() - start
    if elapsed < 0.200:
        elapsed_h = str(round(elapsed * 1000, 1)) + "ms"
    else:
        elapsed_h = str(round(elapsed, 2)) + "s"

    ret = {}
    ret["query time"] = {"human": elapsed_h, "raw": str(round(elapsed, 5))}
    select_keywords = ["SELECT", "SHOW", "DESC"]
    select_query = False
    for keyword in select_keywords:
        if query.upper().strip().startswith(keyword):
            select_query = True
            break
    if select_query:
        ret["rows returned"] = affected
        columns = ()
        for column in cur.description:
            columns += (column[0],)
        ret["columns"] = columns
        ret["results"] = results
        return ret
    else:
        ret["rows affected"] = affected
        return ret


def file_query(database, file_name, **connection_args):
    """
    Run an arbitrary SQL query from the specified file and return the
    the number of affected rows.

    .. versionadded:: 2017.7.0

    database

        database to run script inside

    file_name

        File name of the script.  This can be on the minion, or a file that is reachable by the fileserver

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.file_query mydb file_name=/tmp/sqlfile.sql
        salt '*' mysql.file_query mydb file_name=salt://sqlfile.sql

    Return data:

    .. code-block:: python

        {'query time': {'human': '39.0ms', 'raw': '0.03899'}, 'rows affected': 1L}

    """
    if not HAS_SQLPARSE:
        log.error("mysql.file_query unavailable, no python sqlparse library installed.")
        return False

    if any(
        file_name.startswith(proto)
        for proto in ("salt://", "http://", "https://", "swift://", "s3://")
    ):
        file_name = __salt__["cp.cache_file"](file_name)

    if os.path.exists(file_name):
        with salt.utils.files.fopen(file_name, "r") as ifile:
            contents = salt.utils.stringutils.to_unicode(ifile.read())
    else:
        log.error('File "%s" does not exist', file_name)
        return False

    query_string = ""
    ret = {
        "rows returned": 0,
        "columns": [],
        "results": [],
        "rows affected": 0,
        "query time": {"raw": 0},
    }

    contents = _sanitize_comments(contents)
    # Walk the each line of the sql file to get accurate row affected results
    for line in contents.splitlines():
        if not re.search(r"[^-;]+;", line):  # keep appending lines that don't end in ;
            query_string = query_string + line
        else:
            query_string = (
                query_string + line
            )  # append lines that end with ; and run query
            query_result = query(database, query_string, **connection_args)
            query_string = ""

            if query_result is False:
                # Fail out on error
                return False

            if "query time" in query_result:
                ret["query time"]["raw"] += float(query_result["query time"]["raw"])
            if "rows returned" in query_result:
                ret["rows returned"] += query_result["rows returned"]
            if "columns" in query_result:
                ret["columns"].append(query_result["columns"])
            if "results" in query_result:
                ret["results"].append(query_result["results"])
            if "rows affected" in query_result:
                ret["rows affected"] += query_result["rows affected"]

    ret["query time"]["human"] = str(round(float(ret["query time"]["raw"]), 2)) + "s"
    ret["query time"]["raw"] = round(float(ret["query time"]["raw"]), 5)

    # Remove empty keys in ret
    ret = {k: v for k, v in ret.items() if v}

    return ret


def status(**connection_args):
    """
    Return the status of a MySQL server using the output from the ``SHOW
    STATUS`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.status
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return {}
    cur = dbc.cursor()
    qry = "SHOW STATUS"
    try:
        _execute(cur, qry)
    except OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return {}

    ret = {}
    for _ in range(cur.rowcount):
        row = cur.fetchone()
        ret[row[0]] = row[1]
    return ret


def version(**connection_args):
    """
    Return the version of a MySQL server using the output from the ``SELECT
    VERSION()`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.version
    """
    if "mysql.version" in __context__:
        return __context__["mysql.version"]

    dbc = _connect(**connection_args)
    if dbc is None:
        return ""
    cur = dbc.cursor()
    qry = "SELECT VERSION()"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return ""

    try:
        __context__["mysql.version"] = salt.utils.data.decode(cur.fetchone()[0])
        return __context__["mysql.version"]
    except IndexError:
        return ""


def slave_lag(**connection_args):
    """
    Return the number of seconds that a slave SQL server is lagging behind the
    master, if the host is not a slave it will return -1.  If the server is
    configured to be a slave for replication but slave IO is not running then
    -2 will be returned. If there was an error connecting to the database or
    checking the slave status, -3 will be returned.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.slave_lag
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return -3
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    qry = "show slave status"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return -3

    results = cur.fetchone()
    if cur.rowcount == 0:
        # Server is not a slave if master is not defined.  Return empty tuple
        # in this case.  Could probably check to see if Slave_IO_Running and
        # Slave_SQL_Running are both set to 'Yes' as well to be really really
        # sure that it is a slave.
        return -1
    else:
        if results["Slave_IO_Running"] == "Yes":
            return results["Seconds_Behind_Master"]
        else:
            # Replication is broken if you get here.
            return -2


def free_slave(**connection_args):
    """
    Frees a slave from its master.  This is a WIP, do not use.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.free_slave
    """
    slave_db = _connect(**connection_args)
    if slave_db is None:
        return ""
    slave_cur = slave_db.cursor(MySQLdb.cursors.DictCursor)
    slave_cur.execute("show slave status")
    slave_status = slave_cur.fetchone()
    master = {"host": slave_status["Master_Host"]}

    try:
        # Try to connect to the master and flush logs before promoting to
        # master.  This may fail if the master is no longer available.
        # I am also assuming that the admin password is the same on both
        # servers here, and only overriding the host option in the connect
        # function.
        master_db = _connect(**master)
        if master_db is None:
            return ""
        master_cur = master_db.cursor()
        master_cur.execute("flush logs")
        master_db.close()
    except MySQLdb.OperationalError:
        pass

    slave_cur.execute("stop slave")
    slave_cur.execute("reset master")
    slave_cur.execute("change master to MASTER_HOST=")
    slave_cur.execute("show slave status")
    results = slave_cur.fetchone()

    if results is None:
        return "promoted"
    else:
        return "failed"


# Database related actions
def db_list(**connection_args):
    """
    Return a list of databases of a MySQL server using the output
    from the ``SHOW DATABASES`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_list
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    qry = "SHOW DATABASES"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return []

    ret = []
    results = cur.fetchall()
    for dbs in results:
        ret.append(dbs[0])

    log.debug(ret)
    return ret


def alter_db(name, character_set=None, collate=None, **connection_args):
    """
    Modify database using ``ALTER DATABASE %(dbname)s CHARACTER SET %(charset)s
    COLLATE %(collation)s;`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.alter_db testdb charset='latin1'
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    existing = db_get(name, **connection_args)
    # escaping database name is not required because of backticks in query expression
    qry = "ALTER DATABASE `{}` CHARACTER SET {} COLLATE {};".format(
        name,
        character_set or existing.get("character_set"),
        collate or existing.get("collate"),
    )
    args = {}
    try:
        if _execute(cur, qry, args):
            log.info("DB '%s' altered", name)
            return True
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
    return False


def db_get(name, **connection_args):
    """
    Return a list of databases of a MySQL server using the output
    from the ``SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM
    INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='dbname';`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_get test
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    qry = (
        "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM "
        "INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%(dbname)s;"
    )
    args = {"dbname": name}
    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return []

    if cur.rowcount:
        rows = cur.fetchall()
        return {"character_set": rows[0][0], "collate": rows[0][1]}
    return {}


def db_tables(name, **connection_args):
    """
    Shows the tables in the given MySQL database (if exists)

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_tables 'database'
    """
    if not db_exists(name, **connection_args):
        log.info("Database '%s' does not exist", name)
        return False

    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    s_name = quote_identifier(name)
    # identifiers cannot be used as values
    qry = f"SHOW TABLES IN {s_name}"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return []

    ret = []
    results = cur.fetchall()
    for table in results:
        ret.append(table[0])
    log.debug(ret)
    return ret


def db_exists(name, **connection_args):
    """
    Checks if a database exists on the MySQL server.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_exists 'dbname'
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    # Warn: here db identifier is not backtyped but should be
    #  escaped as a string value. Note also that LIKE special characters
    # '_' and '%' should also be escaped.
    args = {"dbname": name}
    qry = "SHOW DATABASES LIKE %(dbname)s;"
    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False
    cur.fetchall()
    return cur.rowcount == 1


def db_create(name, character_set=None, collate=None, **connection_args):
    """
    Adds a databases to the MySQL server.

    name
        The name of the database to manage

    character_set
        The character set, if left empty the MySQL default will be used

    collate
        The collation, if left empty the MySQL default will be used

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_create 'dbname'
        salt '*' mysql.db_create 'dbname' 'utf8' 'utf8_general_ci'
    """
    # check if db exists
    if db_exists(name, **connection_args):
        log.info("DB '%s' already exists", name)
        return False

    # db doesn't exist, proceed
    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    s_name = quote_identifier(name)
    # identifiers cannot be used as values
    qry = f"CREATE DATABASE IF NOT EXISTS {s_name}"
    args = {}
    if character_set is not None:
        qry += " CHARACTER SET %(character_set)s"
        args["character_set"] = character_set
    if collate is not None:
        qry += " COLLATE %(collate)s"
        args["collate"] = collate
    qry += ";"

    try:
        if _execute(cur, qry, args):
            log.info("DB '%s' created", name)
            return True
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
    return False


def db_remove(name, **connection_args):
    """
    Removes a databases from the MySQL server.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_remove 'dbname'
    """
    # check if db exists
    if not db_exists(name, **connection_args):
        log.info("DB '%s' does not exist", name)
        return False

    if name in ("mysql", "information_scheme"):
        log.info("DB '%s' may not be removed", name)
        return False

    # db does exists, proceed
    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    s_name = quote_identifier(name)
    # identifiers cannot be used as values
    qry = f"DROP DATABASE {s_name};"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    if not db_exists(name, **connection_args):
        log.info("Database '%s' has been removed", name)
        return True

    log.info("Database '%s' has not been removed", name)
    return False


# User related actions
def user_list(**connection_args):
    """
    Return a list of users on a MySQL server

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.user_list
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    try:
        qry = "SELECT User,Host FROM mysql.user"
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return []
    results = cur.fetchall()
    log.debug(results)
    return results


def _mysql_user_exists(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    passwordless=False,
    unix_socket=False,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):

    server_version = salt.utils.data.decode(version(**connection_args))
    compare_version = "8.0.11"
    qry = "SELECT User,Host FROM mysql.user WHERE User = %(user)s AND Host = %(host)s"
    args = {}
    args["user"] = user
    args["host"] = host

    if salt.utils.data.is_true(passwordless):
        if salt.utils.data.is_true(unix_socket):
            qry += " AND plugin=%(unix_socket)s"
            args["unix_socket"] = "auth_socket"
        else:
            qry += " AND " + password_column + " = ''"
    elif password:
        if salt.utils.versions.version_cmp(server_version, compare_version) >= 0:
            if auth_plugin == "mysql_native_password":
                _password = __mysql_hash_password(str(password))
                qry += " AND " + password_column + " = %(password)s"
                args["password"] = str(_password)
            else:
                err = "Unable to verify password."
                log.error(err)
                __context__["mysql.error"] = err
        else:
            qry += " AND " + password_column + " = PASSWORD(%(password)s)"
            args["password"] = str(password)
    elif password_hash:
        qry += " AND " + password_column + " = %(password)s"
        args["password"] = password_hash

    return qry, args


def _mariadb_user_exists(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    passwordless=False,
    unix_socket=False,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):

    qry = "SELECT User,Host FROM mysql.user WHERE User = %(user)s AND Host = %(host)s"
    args = {}
    args["user"] = user
    args["host"] = host

    if salt.utils.data.is_true(passwordless):
        if salt.utils.data.is_true(unix_socket):
            qry += " AND plugin=%(unix_socket)s"
            args["unix_socket"] = "unix_socket"
        else:
            qry += " AND " + password_column + " = ''"
    elif password:
        qry += " AND " + password_column + " = PASSWORD(%(password)s)"
        args["password"] = str(password)
    elif password_hash:
        qry += " AND " + password_column + " = %(password)s"
        args["password"] = password_hash

    return qry, args


def user_exists(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    passwordless=False,
    unix_socket=False,
    password_column=None,
    **connection_args,
):
    """
    Checks if a user exists on the MySQL server. A login can be checked to see
    if passwordless login is permitted by omitting ``password`` and
    ``password_hash``, and using ``passwordless=True``.

    .. versionadded:: 0.16.2
        The ``passwordless`` option was added.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.user_exists 'username' 'hostname' 'password'
        salt '*' mysql.user_exists 'username' 'hostname' password_hash='hash'
        salt '*' mysql.user_exists 'username' passwordless=True
        salt '*' mysql.user_exists 'username' password_column='authentication_string'
    """
    run_verify = False
    server_version = salt.utils.data.decode(version(**connection_args))
    if not server_version and password:
        # Did we fail to connect with the user we are checking
        # Its password might have previously change with the same command/state

        # Clear the previous error
        __context__["mysql.error"] = None
        connection_args["connection_pass"] = password

        server_version = salt.utils.data.decode(version(**connection_args))
        if not server_version:
            last_err = __context__["mysql.error"]
            err = (
                "MySQL Error: Unable to fetch current server version. Last error was:"
                ' "{}"'.format(last_err)
            )
            log.error(err)
            return False

    dbc = _connect(**connection_args)
    # Did we fail to connect with the user we are checking
    # Its password might have previously change with the same command/state
    if (
        dbc is None
        and __context__["mysql.error"].startswith(
            f"MySQL Error 1045: Access denied for user '{user}'@"
        )
        and password
    ):
        # Clear the previous error
        __context__["mysql.error"] = None
        connection_args["connection_pass"] = password
        dbc = _connect(**connection_args)
    if dbc is None:
        return False

    if not password_column:
        password_column = __password_column(**connection_args)

    auth_plugin = __get_auth_plugin(user, host, **connection_args)

    cur = dbc.cursor()
    if "MariaDB" in server_version:
        qry, args = _mariadb_user_exists(
            user,
            host,
            password,
            password_hash,
            passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )
    else:
        qry, args = _mysql_user_exists(
            user,
            host,
            password,
            password_hash,
            passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )

    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    return cur.rowcount == 1


def user_info(user, host="localhost", **connection_args):
    """
    Get full info on a MySQL user

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.user_info root localhost
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return False

    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    qry = "SELECT * FROM mysql.user WHERE User = %(user)s AND Host = %(host)s"
    args = {}
    args["user"] = user
    args["host"] = host

    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False
    result = cur.fetchone()
    log.debug(result)
    return result


def _mysql_user_create(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=False,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):

    server_version = salt.utils.data.decode(version(**connection_args))
    compare_version = "8.0.11"

    qry = "CREATE USER %(user)s@%(host)s"
    args = {}
    args["user"] = user
    args["host"] = host
    if unix_socket:
        if not plugin_status("auth_socket", **connection_args):
            err = "The auth_socket plugin is not enabled."
            log.error(err)
            __context__["mysql.error"] = err
            qry = False
        else:
            if host == "localhost":
                qry += " IDENTIFIED WITH auth_socket"
            else:
                log.error("Auth via unix_socket can be set only for host=localhost")
                __context__["mysql.error"] = err
                qry = False
    else:
        if not salt.utils.data.is_true(allow_passwordless):
            if password is not None:
                if (
                    salt.utils.versions.version_cmp(server_version, compare_version)
                    >= 0
                ):
                    args["auth_plugin"] = auth_plugin
                    qry += " IDENTIFIED WITH %(auth_plugin)s BY %(password)s"
                else:
                    qry += " IDENTIFIED BY %(password)s"
                args["password"] = str(password)
            elif password_hash is not None:
                if (
                    salt.utils.versions.version_cmp(server_version, compare_version)
                    >= 0
                ):
                    args["auth_plugin"] = auth_plugin
                    qry += " IDENTIFIED WITH %(auth_plugin)s AS %(password)s"
                else:
                    qry += " IDENTIFIED BY PASSWORD %(password)s"
                args["password"] = password_hash
            else:
                log.error(
                    "password or password_hash must be specified, unless "
                    "allow_passwordless=True"
                )
                qry = False
    return qry, args


def _mariadb_user_create(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=False,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):

    qry = "CREATE USER %(user)s@%(host)s"
    args = {}
    args["user"] = user
    args["host"] = host
    if unix_socket:
        if not plugin_status("unix_socket", **connection_args):
            err = "The unix_socket plugin is not enabled."
            log.error(err)
            __context__["mysql.error"] = err
            qry = False
        else:
            if host == "localhost":
                qry += " IDENTIFIED VIA unix_socket"
            else:
                log.error("Auth via unix_socket can be set only for host=localhost")
                __context__["mysql.error"] = err
                qry = False
    else:
        if not salt.utils.data.is_true(allow_passwordless):
            if password is not None:
                qry += " IDENTIFIED BY %(password)s"
                args["password"] = str(password)
            elif password_hash is not None:
                qry += " IDENTIFIED BY PASSWORD %(password)s"
                args["password"] = password_hash
            else:
                log.error(
                    "password or password_hash must be specified, unless "
                    "allow_passwordless=True"
                )
                qry = False
    return qry, args


def user_create(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=False,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):
    """
    Creates a MySQL user

    host
        Host for which this user/password combo applies

    password
        The password to use for the new user. Will take precedence over the
        ``password_hash`` option if both are specified.

    password_hash
        The password in hashed form. Be sure to quote the password because YAML
        doesn't like the ``*``. A password hash can be obtained from the mysql
        command-line client like so::

            mysql> SELECT PASSWORD('mypass');
            +-------------------------------------------+
            | PASSWORD('mypass')                        |
            +-------------------------------------------+
            | *6C8989366EAF75BB670AD8EA7A7FC1176A95CEF4 |
            +-------------------------------------------+
            1 row in set (0.00 sec)

    allow_passwordless
        If ``True``, then ``password`` and ``password_hash`` can be omitted (or
        set to ``None``) to permit a passwordless login.

    unix_socket
        If ``True`` and allow_passwordless is ``True`` then will be used unix_socket auth plugin.

    password_column
        The password column to use in the user table.

    auth_plugin
        The authentication plugin to use, default is to use the mysql_native_password plugin.

    .. versionadded:: 0.16.2
        The ``allow_passwordless`` option was added.

    CLI Examples:

    .. code-block:: bash

        salt '*' mysql.user_create 'username' 'hostname' 'password'
        salt '*' mysql.user_create 'username' 'hostname' password_hash='hash'
        salt '*' mysql.user_create 'username' 'hostname' allow_passwordless=True
    """
    server_version = salt.utils.data.decode(version(**connection_args))
    if not server_version and password:
        # Did we fail to connect with the user we are checking
        # Its password might have previously change with the same command/state

        # Clear the previous error
        __context__["mysql.error"] = None
        connection_args["connection_pass"] = password

        server_version = salt.utils.data.decode(version(**connection_args))
        if not server_version:
            last_err = __context__["mysql.error"]
            err = (
                "MySQL Error: Unable to fetch current server version. Last error was:"
                ' "{}"'.format(last_err)
            )
            log.error(err)
            return False

    if user_exists(user, host, **connection_args):
        log.info("User '%s'@'%s' already exists", user, host)
        return False

    dbc = _connect(**connection_args)
    if dbc is None:
        return False

    if not password_column:
        password_column = __password_column(**connection_args)

    cur = dbc.cursor()
    if "MariaDB" in server_version:
        qry, args = _mariadb_user_create(
            user,
            host,
            password,
            password_hash,
            allow_passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )
    else:
        qry, args = _mysql_user_create(
            user,
            host,
            password,
            password_hash,
            allow_passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )

    if isinstance(qry, bool):
        return qry

    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    if user_exists(
        user,
        host,
        password,
        password_hash,
        password_column=password_column,
        **connection_args,
    ):
        msg = f"User '{user}'@'{host}' has been created"
        if not any((password, password_hash)):
            msg += " with passwordless login"
        log.info(msg)
        return True

    log.info("User '%s'@'%s' was not created", user, host)
    return False


def _mysql_user_chpass(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=None,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):
    server_version = salt.utils.data.decode(version(**connection_args))
    compare_version = "8.0.11"

    args = {}

    if password is not None:
        if salt.utils.versions.version_cmp(server_version, compare_version) >= 0:
            password_sql = "%(password)s"
        else:
            password_sql = "PASSWORD(%(password)s)"
        args["password"] = password
    elif password_hash is not None:
        password_sql = "%(password)s"
        args["password"] = password_hash
    elif not salt.utils.data.is_true(allow_passwordless):
        log.error(
            "password or password_hash must be specified, unless "
            "allow_passwordless=True"
        )
        return False
    else:
        password_sql = "''"

    args["user"] = user
    args["host"] = host

    if salt.utils.versions.version_cmp(server_version, compare_version) >= 0:
        args["auth_plugin"] = auth_plugin
        qry = "ALTER USER %(user)s@%(host)s IDENTIFIED WITH %(auth_plugin)s "
        if password is not None:
            qry += "BY %(password)s;"
        elif password_hash is not None:
            qry += "AS %(password)s;"
    else:
        qry = (
            "UPDATE mysql.user SET "
            + password_column
            + "="
            + password_sql
            + " WHERE User=%(user)s AND Host = %(host)s;"
        )
    if salt.utils.data.is_true(allow_passwordless) and salt.utils.data.is_true(
        unix_socket
    ):
        if host == "localhost":
            if not plugin_status("auth_socket", **connection_args):
                err = "The auth_socket plugin is not enabled."
                log.error(err)
                __context__["mysql.error"] = err
                qry = False
            else:
                args["unix_socket"] = "auth_socket"
                if (
                    salt.utils.versions.version_cmp(server_version, compare_version)
                    >= 0
                ):
                    qry = (
                        "ALTER USER %(user)s@%(host)s IDENTIFIED WITH %(unix_socket)s"
                        " AS %(user)s;"
                    )
                else:
                    qry = (
                        "UPDATE mysql.user SET "
                        + password_column
                        + "="
                        + password_sql
                        + ", plugin=%(unix_socket)s"
                        + " WHERE User=%(user)s AND Host = %(host)s;"
                    )
        else:
            log.error("Auth via unix_socket can be set only for host=localhost")

    return qry, args


def _mariadb_user_chpass(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=None,
    password_column=None,
    auth_plugin="mysql_native_password",
    **connection_args,
):

    server_version = salt.utils.data.decode(version(**connection_args))
    compare_version = "10.4"

    args = {}

    if password is not None:
        password_sql = "PASSWORD(%(password)s)"
        args["password"] = password
    elif password_hash is not None:
        password_sql = "%(password)s"
        args["password"] = password_hash
    elif not salt.utils.data.is_true(allow_passwordless):
        log.error(
            "password or password_hash must be specified, unless "
            "allow_passwordless=True"
        )
        return False
    else:
        password_sql = "''"

    args["user"] = user
    args["host"] = host

    if salt.utils.versions.version_cmp(server_version, compare_version) >= 0:
        args["auth_plugin"] = auth_plugin
        qry = "ALTER USER %(user)s@%(host)s IDENTIFIED VIA %(auth_plugin)s USING "
        qry += password_sql
    else:
        qry = (
            "UPDATE mysql.user SET "
            + password_column
            + "="
            + password_sql
            + " WHERE User=%(user)s AND Host = %(host)s;"
        )
    if salt.utils.data.is_true(allow_passwordless) and salt.utils.data.is_true(
        unix_socket
    ):
        if host == "localhost":
            if not plugin_status("unix_socket", **connection_args):
                err = "The unix_socket plugin is not enabled."
                log.error(err)
                __context__["mysql.error"] = err
                qry = False
            else:
                args["unix_socket"] = "unix_socket"
                qry = (
                    "UPDATE mysql.user SET "
                    + password_column
                    + "="
                    + password_sql
                    + ", plugin=%(unix_socket)s"
                    + " WHERE User=%(user)s AND Host = %(host)s;"
                )
        else:
            log.error("Auth via unix_socket can be set only for host=localhost")

    return qry, args


def user_chpass(
    user,
    host="localhost",
    password=None,
    password_hash=None,
    allow_passwordless=False,
    unix_socket=None,
    password_column=None,
    **connection_args,
):
    """
    Change password for a MySQL user

    host
        Host for which this user/password combo applies

    password
        The password to set for the new user. Will take precedence over the
        ``password_hash`` option if both are specified.

    password_hash
        The password in hashed form. Be sure to quote the password because YAML
        doesn't like the ``*``. A password hash can be obtained from the mysql
        command-line client like so::

            mysql> SELECT PASSWORD('mypass');
            +-------------------------------------------+
            | PASSWORD('mypass')                        |
            +-------------------------------------------+
            | *6C8989366EAF75BB670AD8EA7A7FC1176A95CEF4 |
            +-------------------------------------------+
            1 row in set (0.00 sec)

    allow_passwordless
        If ``True``, then ``password`` and ``password_hash`` can be omitted (or
        set to ``None``) to permit a passwordless login.

    .. versionadded:: 0.16.2
        The ``allow_passwordless`` option was added.

    CLI Examples:

    .. code-block:: bash

        salt '*' mysql.user_chpass frank localhost newpassword
        salt '*' mysql.user_chpass frank localhost password_hash='hash'
        salt '*' mysql.user_chpass frank localhost allow_passwordless=True
    """
    server_version = salt.utils.data.decode(version(**connection_args))
    if not server_version and password:
        # Did we fail to connect with the user we are checking
        # Its password might have previously change with the same command/state

        # Clear the previous error
        __context__["mysql.error"] = None
        connection_args["connection_pass"] = password

        server_version = salt.utils.data.decode(version(**connection_args))
        if not server_version:
            last_err = __context__["mysql.error"]
            err = (
                "MySQL Error: Unable to fetch current server version. Last error was:"
                ' "{}"'.format(last_err)
            )
            log.error(err)
            return False

    if not user_exists(user, host, **connection_args):
        log.info("User '%s'@'%s' does not exists", user, host)
        return False

    dbc = _connect(**connection_args)

    if dbc is None:
        return False

    if not password_column:
        password_column = __password_column(**connection_args)

    auth_plugin = __get_auth_plugin(user, host, **connection_args)

    cur = dbc.cursor()

    if "MariaDB" in server_version:
        qry, args = _mariadb_user_chpass(
            user,
            host,
            password,
            password_hash,
            allow_passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )
    else:
        qry, args = _mysql_user_chpass(
            user,
            host,
            password,
            password_hash,
            allow_passwordless,
            unix_socket,
            password_column=password_column,
            auth_plugin=auth_plugin,
            **connection_args,
        )

    try:
        result = _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    compare_version = "10.4.0" if "MariaDB" in server_version else "8.0.11"
    res = False
    if salt.utils.versions.version_cmp(server_version, compare_version) >= 0:
        _execute(cur, "FLUSH PRIVILEGES;")
        res = True
    else:
        if result:
            _execute(cur, "FLUSH PRIVILEGES;")
            res = True

    if res:
        log.info(
            "Password for user '%s'@'%s' has been %s",
            user,
            host,
            "changed" if any((password, password_hash)) else "cleared",
        )
        return True
    else:
        log.info(
            "Password for user '%s'@'%s' was not %s",
            user,
            host,
            "changed" if any((password, password_hash)) else "cleared",
        )
        return False


def user_remove(user, host="localhost", **connection_args):
    """
    Delete MySQL user

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.user_remove frank localhost
    """
    if not user_exists(user, host, **connection_args):
        err = "User '%s'@'%s' does not exists", user, host
        __context__["mysql.error"] = err
        log.info(err)
        return False

    dbc = _connect(**connection_args)
    if dbc is None:
        return False

    cur = dbc.cursor()
    qry = "DROP USER %(user)s@%(host)s"
    args = {}
    args["user"] = user
    args["host"] = host
    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    if not user_exists(user, host, **connection_args):
        log.info("User '%s'@'%s' has been removed", user, host)
        return True

    log.info("User '%s'@'%s' has NOT been removed", user, host)
    return False


def tokenize_grant(grant):
    """
    External wrapper function
    :param grant:
    :return: dict

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.tokenize_grant \
            "GRANT SELECT, INSERT ON testdb.* TO 'testuser'@'localhost'"
    """
    return _grant_to_tokens(grant)


# Maintenance
def db_check(name, table=None, **connection_args):
    """
    Repairs the full database or just a given table

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_check dbname
        salt '*' mysql.db_check dbname dbtable
    """
    ret = []
    if table is None:
        # we need to check all tables
        tables = db_tables(name, **connection_args)
        for table in tables:
            log.info("Checking table '%s' in db '%s'..", name, table)
            ret.append(__check_table(name, table, **connection_args))
    else:
        log.info("Checking table '%s' in db '%s'..", name, table)
        ret = __check_table(name, table, **connection_args)
    return ret


def db_repair(name, table=None, **connection_args):
    """
    Repairs the full database or just a given table

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_repair dbname
    """
    ret = []
    if table is None:
        # we need to repair all tables
        tables = db_tables(name, **connection_args)
        for table in tables:
            log.info("Repairing table '%s' in db '%s'..", name, table)
            ret.append(__repair_table(name, table, **connection_args))
    else:
        log.info("Repairing table '%s' in db '%s'..", name, table)
        ret = __repair_table(name, table, **connection_args)
    return ret


def db_optimize(name, table=None, **connection_args):
    """
    Optimizes the full database or just a given table

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.db_optimize dbname
    """
    ret = []
    if table is None:
        # we need to optimize all tables
        tables = db_tables(name, **connection_args)
        for table in tables:
            log.info("Optimizing table '%s' in db '%s'..", name, table)
            ret.append(__optimize_table(name, table, **connection_args))
    else:
        log.info("Optimizing table '%s' in db '%s'..", name, table)
        ret = __optimize_table(name, table, **connection_args)
    return ret


# Grants
def __grant_normalize(grant):
    # MySQL normalizes ALL to ALL PRIVILEGES, we do the same so that
    # grant_exists and grant_add ALL work correctly
    if grant.strip().upper() == "ALL":
        grant = "ALL PRIVILEGES"

    # Grants are paste directly in SQL, must filter it
    exploded_grants = __grant_split(grant)
    for chkgrant, _ in exploded_grants:
        if chkgrant.strip().upper() not in __grants__:
            raise Exception(f"Invalid grant : '{chkgrant}'")

    return grant


def __grant_split(grant):
    pattern = re.compile(r"([\w\s]+)(\([^)(]*\))?\s*,?")
    return pattern.findall(grant)


def __ssl_option_sanitize(ssl_option):
    new_ssl_option = []

    # Like most other "salt dsl" YAML structures, ssl_option is a list of single-element dicts
    for opt in ssl_option:
        key = next(iter(opt.keys()))

        normal_key = key.strip().upper()

        if normal_key not in __ssl_options__:
            raise Exception(f"Invalid SSL option : '{key}'")

        if normal_key in __ssl_options_parameterized__:
            # SSL option parameters (cipher, issuer, subject) are pasted directly to SQL so
            # we need to sanitize for single quotes...
            new_ssl_option.append(
                "{} '{}'".format(normal_key, opt[key].replace("'", ""))
            )
        # omit if falsey
        elif opt[key]:
            new_ssl_option.append(normal_key)

    return " REQUIRE " + " AND ".join(new_ssl_option)


def __grant_generate(
    grant,
    database,
    user,
    host="localhost",
    grant_option=False,
    escape=True,
    ssl_option=False,
):
    """
    Validate grants and build the query that could set the given grants

    Note that this query contains arguments for user and host but not for
    grants or database.
    """
    # TODO: Re-order the grant so it is according to the
    #       SHOW GRANTS for xxx@yyy query (SELECT comes first, etc)
    grant = re.sub(r"\s*,\s*", ", ", grant).upper()

    grant = __grant_normalize(grant)

    db_part = database.rpartition(".")
    dbc = db_part[0]
    table = db_part[2]

    if escape:
        if dbc != "*":
            # _ and % are authorized on GRANT queries and should get escaped
            # on the db name, but only if not requesting a table level grant
            dbc = quote_identifier(dbc, for_grants=table == "*")
        if table != "*":
            table = quote_identifier(table)
    # identifiers cannot be used as values, and same thing for grants
    qry = f"GRANT {grant} ON {dbc}.{table} TO %(user)s@%(host)s"
    args = {}
    args["user"] = user
    args["host"] = host
    if ssl_option and isinstance(ssl_option, list):
        qry += __ssl_option_sanitize(ssl_option)
    if salt.utils.data.is_true(grant_option):
        qry += " WITH GRANT OPTION"
    log.debug("Grant Query generated: %s args %s", qry, repr(args))
    return {"qry": qry, "args": args}


def user_grants(user, host="localhost", **connection_args):
    """
    Shows the grants for the given MySQL user (if it exists)

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.user_grants 'frank' 'localhost'
    """
    if not user_exists(user, host, **connection_args):
        log.info("User '%s'@'%s' does not exist", user, host)
        return False

    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    qry = "SHOW GRANTS FOR %(user)s@%(host)s"
    args = {}
    args["user"] = user
    args["host"] = host
    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    ret = []
    results = salt.utils.data.decode(cur.fetchall())
    for grant in results:
        tmp = grant[0].split(" IDENTIFIED BY")[0]
        if "WITH GRANT OPTION" in grant[0] and "WITH GRANT OPTION" not in tmp:
            tmp = f"{tmp} WITH GRANT OPTION"
        ret.append(tmp)
    log.debug(ret)
    return ret


def grant_exists(
    grant,
    database,
    user,
    host="localhost",
    grant_option=False,
    escape=True,
    **connection_args,
):
    """
    Checks to see if a grant exists in the database

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.grant_exists \
             'SELECT,INSERT,UPDATE,...' 'database.*' 'frank' 'localhost'
    """

    server_version = salt.utils.data.decode(version(**connection_args))
    if not server_version:
        last_err = __context__["mysql.error"]
        err = 'MySQL Error: Unable to fetch current server version. Last error was: "{}"'.format(
            last_err
        )
        log.error(err)
        return False
    if "ALL" in grant.upper():
        if (
            salt.utils.versions.version_cmp(server_version, "8.0") >= 0
            and "MariaDB" not in server_version
            and database == "*.*"
        ):
            grant = ",".join([i for i in __all_privileges__])
        else:
            grant = "ALL PRIVILEGES"

    try:
        target = __grant_generate(grant, database, user, host, grant_option, escape)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Error during grant generation.")
        log.error(exc)
        return False

    grants = user_grants(user, host, **connection_args)

    if grants is False:
        log.error(
            "Grant does not exist or may not be ordered properly. In some cases, "
            "this could also indicate a connection error. Check your configuration."
        )
        return False

    # Combine grants that match the same database
    _grants = {}
    for grant in grants:
        grant_token = _grant_to_tokens(grant)
        grant_token["grant"] = _resolve_grant_aliases(
            grant_token["grant"], server_version
        )
        if grant_token["database"] not in _grants:
            _grants[grant_token["database"]] = {
                "user": grant_token["user"],
                "database": grant_token["database"],
                "host": grant_token["host"],
                "grant": grant_token["grant"],
            }
        else:
            _grants[grant_token["database"]]["grant"].extend(grant_token["grant"])

    target_tokens = _grant_to_tokens(target)
    target_tokens["grant"] = _resolve_grant_aliases(
        target_tokens["grant"], server_version
    )
    for database, grant_tokens in _grants.items():
        try:
            _grant_tokens = {}
            _target_tokens = {}

            _grant_matches = [
                True if i in grant_tokens["grant"] else False
                for i in target_tokens["grant"]
            ]

            for item in ["user", "database", "host"]:
                _grant_tokens[item] = (
                    grant_tokens[item]
                    .replace('"', "")
                    .replace("\\", "")
                    .replace("`", "")
                )
                _target_tokens[item] = (
                    target_tokens[item]
                    .replace('"', "")
                    .replace("\\", "")
                    .replace("`", "")
                )

            if (
                _grant_tokens["user"] == _target_tokens["user"]
                and _grant_tokens["database"] == _target_tokens["database"]
                and _grant_tokens["host"] == _target_tokens["host"]
                and all(_grant_matches)
            ):
                return True
            else:
                log.debug("grants mismatch '%s'<>'%s'", grant_tokens, target_tokens)

        except Exception as exc:  # pylint: disable=broad-except
            # Fallback to strict parsing
            log.exception(exc)
            if grants is not False and target in grants:
                log.debug("Grant exists.")
                return True

    log.debug("Grant does not exist, or is perhaps not ordered properly?")
    return False


def grant_add(
    grant,
    database,
    user,
    host="localhost",
    grant_option=False,
    escape=True,
    ssl_option=False,
    **connection_args,
):
    """
    Adds a grant to the MySQL server.

    For database, make sure you specify database.table or database.*

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.grant_add \
            'SELECT,INSERT,UPDATE,...' 'database.*' 'frank' 'localhost'
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()

    # Avoid spaces problems
    grant = grant.strip()
    try:
        qry = __grant_generate(
            grant, database, user, host, grant_option, escape, ssl_option
        )
    except Exception:  # pylint: disable=broad-except
        log.error("Error during grant generation")
        return False
    try:
        _execute(cur, qry["qry"], qry["args"])
    except (MySQLdb.OperationalError, MySQLdb.ProgrammingError) as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False
    if grant_exists(
        grant, database, user, host, grant_option, escape, **connection_args
    ):
        log.info(
            "Grant '%s' on '%s' for user '%s' has been added", grant, database, user
        )
        return True

    log.info(
        "Grant '%s' on '%s' for user '%s' has NOT been added", grant, database, user
    )
    return False


def grant_revoke(
    grant,
    database,
    user,
    host="localhost",
    grant_option=False,
    escape=True,
    **connection_args,
):
    """
    Removes a grant from the MySQL server.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.grant_revoke \
            'SELECT,INSERT,UPDATE' 'database.*' 'frank' 'localhost'
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()

    grant = __grant_normalize(grant)

    if salt.utils.data.is_true(grant_option):
        grant += ", GRANT OPTION"

    db_part = database.rpartition(".")
    dbc = db_part[0]
    table = db_part[2]
    if dbc != "*":
        # _ and % are authorized on GRANT queries and should get escaped
        # on the db name, but only if not requesting a table level grant
        s_database = quote_identifier(dbc, for_grants=table == "*")
    if dbc == "*":
        # add revoke for *.*
        # before the modification query send to mysql will looks like
        # REVOKE SELECT ON `*`.* FROM %(user)s@%(host)s
        s_database = dbc
    if table != "*":
        table = quote_identifier(table)
    # identifiers cannot be used as values, same thing for grants
    qry = f"REVOKE {grant} ON {s_database}.{table} FROM %(user)s@%(host)s;"
    args = {}
    args["user"] = user
    args["host"] = host

    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    if not grant_exists(
        grant, database, user, host, grant_option, escape, **connection_args
    ):
        log.info(
            "Grant '%s' on '%s' for user '%s' has been revoked",
            grant,
            database,
            user,
        )
        return True

    log.info(
        "Grant '%s' on '%s' for user '%s' has NOT been revoked",
        grant,
        database,
        user,
    )
    return False


def processlist(**connection_args):
    """
    Retrieves the processlist from the MySQL server via
    "SHOW FULL PROCESSLIST".

    Returns: a list of dicts, with each dict representing a process:

    .. code-block:: python

        {'Command': 'Query',
        'Host': 'localhost',
        'Id': 39,
        'Info': 'SHOW FULL PROCESSLIST',
        'Rows_examined': 0,
        'Rows_read': 1,
        'Rows_sent': 0,
        'State': None,
        'Time': 0,
        'User': 'root',
        'db': 'mysql'}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.processlist

    """
    ret = []

    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    _execute(cur, "SHOW FULL PROCESSLIST")
    hdr = [c[0] for c in cur.description]
    for _ in range(cur.rowcount):
        row = cur.fetchone()
        idx_r = {}
        for idx_j, value_j in enumerate(hdr):
            idx_r[hdr[idx_j]] = row[idx_j]
        ret.append(idx_r)
    cur.close()
    return ret


def __do_query_into_hash(conn, sql_str):
    """
    Perform the query that is passed to it (sql_str).

    Returns:
       results in a dict.

    """
    mod = sys._getframe().f_code.co_name
    log.debug("%s<--(%s)", mod, sql_str)

    rtn_results = []

    cursor = None
    try:
        cursor = conn.cursor()
    except MySQLdb.MySQLError:
        log.error("%s: Can't get cursor for SQL->%s", mod, sql_str)
        if cursor:
            cursor.close()
        log.debug("%s-->", mod)
        return rtn_results

    try:
        _execute(cursor, sql_str)
    except MySQLdb.MySQLError:
        log.error("%s: try to execute : SQL->%s", mod, sql_str)
        cursor.close()
        log.debug("%s-->", mod)
        return rtn_results

    qrs = cursor.fetchall()

    for row_data in qrs:
        col_cnt = 0
        row = {}
        for col_data in cursor.description:
            col_name = col_data[0]
            row[col_name] = row_data[col_cnt]
            col_cnt += 1

        rtn_results.append(row)

    cursor.close()
    log.debug("%s-->", mod)
    return rtn_results


def get_master_status(**connection_args):
    """
    Retrieves the master status from the minion.

    Returns::

        {'host.domain.com': {'Binlog_Do_DB': '',
                         'Binlog_Ignore_DB': '',
                         'File': 'mysql-bin.000021',
                         'Position': 107}}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.get_master_status

    """
    mod = sys._getframe().f_code.co_name
    log.debug("%s<--", mod)
    conn = _connect(**connection_args)
    if conn is None:
        return []
    rtnv = __do_query_into_hash(conn, "SHOW MASTER STATUS")
    conn.close()

    # check for if this minion is not a master
    if not rtnv:
        rtnv.append([])

    log.debug("%s-->%s", mod, len(rtnv[0]))
    return rtnv[0]


def get_slave_status(**connection_args):
    """
    Retrieves the slave status from the minion.

    Returns::

        {'host.domain.com': {'Connect_Retry': 60,
                       'Exec_Master_Log_Pos': 107,
                       'Last_Errno': 0,
                       'Last_Error': '',
                       'Last_IO_Errno': 0,
                       'Last_IO_Error': '',
                       'Last_SQL_Errno': 0,
                       'Last_SQL_Error': '',
                       'Master_Host': 'comet.scion-eng.com',
                       'Master_Log_File': 'mysql-bin.000021',
                       'Master_Port': 3306,
                       'Master_SSL_Allowed': 'No',
                       'Master_SSL_CA_File': '',
                       'Master_SSL_CA_Path': '',
                       'Master_SSL_Cert': '',
                       'Master_SSL_Cipher': '',
                       'Master_SSL_Key': '',
                       'Master_SSL_Verify_Server_Cert': 'No',
                       'Master_Server_Id': 1,
                       'Master_User': 'replu',
                       'Read_Master_Log_Pos': 107,
                       'Relay_Log_File': 'klo-relay-bin.000071',
                       'Relay_Log_Pos': 253,
                       'Relay_Log_Space': 553,
                       'Relay_Master_Log_File': 'mysql-bin.000021',
                       'Replicate_Do_DB': '',
                       'Replicate_Do_Table': '',
                       'Replicate_Ignore_DB': '',
                       'Replicate_Ignore_Server_Ids': '',
                       'Replicate_Ignore_Table': '',
                       'Replicate_Wild_Do_Table': '',
                       'Replicate_Wild_Ignore_Table': '',
                       'Seconds_Behind_Master': 0,
                       'Skip_Counter': 0,
                       'Slave_IO_Running': 'Yes',
                       'Slave_IO_State': 'Waiting for master to send event',
                       'Slave_SQL_Running': 'Yes',
                       'Until_Condition': 'None',
                       'Until_Log_File': '',
                       'Until_Log_Pos': 0}}

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.get_slave_status

    """
    mod = sys._getframe().f_code.co_name
    log.debug("%s<--", mod)
    conn = _connect(**connection_args)
    if conn is None:
        return []
    rtnv = __do_query_into_hash(conn, "SHOW SLAVE STATUS")
    conn.close()

    # check for if this minion is not a slave
    if not rtnv:
        rtnv.append([])

    log.debug("%s-->%s", mod, len(rtnv[0]))
    return rtnv[0]


def showvariables(**connection_args):
    """
    Retrieves the show variables from the minion.

    Returns::
        show variables full dict

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.showvariables

    """
    mod = sys._getframe().f_code.co_name
    log.debug("%s<--", mod)
    conn = _connect(**connection_args)
    if conn is None:
        return []
    rtnv = __do_query_into_hash(conn, "SHOW VARIABLES")
    conn.close()
    if not rtnv:
        rtnv.append([])

    log.debug("%s-->%s", mod, len(rtnv[0]))
    return rtnv


def showglobal(**connection_args):
    """
    Retrieves the show global variables from the minion.

    Returns::
        show global variables full dict

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.showglobal

    """
    mod = sys._getframe().f_code.co_name
    log.debug("%s<--", mod)
    conn = _connect(**connection_args)
    if conn is None:
        return []
    rtnv = __do_query_into_hash(conn, "SHOW GLOBAL VARIABLES")
    conn.close()
    if not rtnv:
        rtnv.append([])

    log.debug("%s-->%s", mod, len(rtnv[0]))
    return rtnv


def verify_login(user, password=None, **connection_args):
    """
    Attempt to login using the provided credentials.
    If successful, return true.  Otherwise, return False.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.verify_login root password
    """
    # Override the connection args for username and password
    connection_args["connection_user"] = user
    connection_args["connection_pass"] = password

    dbc = _connect(**connection_args)
    if dbc is None:
        # Clear the mysql.error if unable to connect
        # if the connection fails, we simply return False
        if "mysql.error" in __context__:
            del __context__["mysql.error"]
        return False
    return True


def plugins_list(**connection_args):
    """
    Return a list of plugins and their status
    from the ``SHOW PLUGINS`` query.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.plugins_list
    """
    dbc = _connect(**connection_args)
    if dbc is None:
        return []
    cur = dbc.cursor()
    qry = "SHOW PLUGINS"
    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return []

    ret = []
    results = cur.fetchall()
    for dbs in results:
        ret.append({"name": dbs[0], "status": dbs[1]})

    log.debug(ret)
    return ret


def plugin_add(name, soname=None, **connection_args):
    """
    Add a plugina.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.plugin_add auth_socket
    """
    if not name:
        log.error("Plugin name is required.")
        return False

    if plugin_status(name, **connection_args):
        log.error("Plugin %s is already installed.", name)
        return True

    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    qry = f"INSTALL PLUGIN {name}"

    if soname:
        qry += f' SONAME "{soname}"'
    else:
        qry += f' SONAME "{name}.so"'

    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    return True


def plugin_remove(name, **connection_args):
    """
    Remove a plugin.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.plugin_remove auth_socket
    """
    if not name:
        log.error("Plugin name is required.")
        return False

    if not plugin_status(name, **connection_args):
        log.error("Plugin %s is not installed.", name)
        return True

    dbc = _connect(**connection_args)
    if dbc is None:
        return False
    cur = dbc.cursor()
    qry = f"UNINSTALL PLUGIN {name}"
    args = {}
    args["name"] = name

    try:
        _execute(cur, qry)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return False

    return True


def plugin_status(name, **connection_args):
    """
    Return the status of a plugin.

    CLI Example:

    .. code-block:: bash

        salt '*' mysql.plugin_status auth_socket
    """
    if not name:
        log.error("Plugin name is required.")
        return False

    dbc = _connect(**connection_args)
    if dbc is None:
        return ""
    cur = dbc.cursor()
    qry = (
        "SELECT PLUGIN_STATUS FROM INFORMATION_SCHEMA.PLUGINS WHERE PLUGIN_NAME ="
        " %(name)s"
    )
    args = {}
    args["name"] = name

    try:
        _execute(cur, qry, args)
    except MySQLdb.OperationalError as exc:
        err = "MySQL Error {}: {}".format(*exc.args)
        __context__["mysql.error"] = err
        log.error(err)
        return ""

    try:
        status = cur.fetchone()
        if status is None:
            return ""
        else:
            return status[0]
    except IndexError:
        return ""
