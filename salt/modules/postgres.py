"""
Module to provide Postgres compatibility to salt.

:configuration: In order to connect to Postgres, certain configuration is
    required in /etc/salt/minion on the relevant minions. Some sample configs
    might look like::

        postgres.host: 'localhost'
        postgres.port: '5432'
        postgres.user: 'postgres' -> db user
        postgres.pass: ''
        postgres.maintenance_db: 'postgres'

    The default for the maintenance_db is 'postgres' and in most cases it can
    be left at the default setting.
    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar

To prevent Postgres commands from running arbitrarily long, a timeout (in seconds) can be set

    .. code-block:: yaml

        postgres.timeout: 60

    .. versionadded:: 3006.0

:note: This module uses MD5 hashing which may not be compliant with certain
    security audits.

:note: When installing postgres from the official postgres repos, on certain
    linux distributions, either the psql or the initdb binary is *not*
    automatically placed on the path. Add a configuration to the location
    of the postgres bin's path to the relevant minion for this module::

        postgres.bins_dir: '/usr/pgsql-9.5/bin/'
"""

# This pylint error is popping up where there are no colons?
# pylint: disable=E8203


import base64
import datetime
import hashlib
import hmac
import io
import logging
import os
import pipes
import re
import tempfile

import salt.utils.files
import salt.utils.itertools
import salt.utils.odict
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.saslprep import saslprep
from salt.utils.versions import LooseVersion

try:
    import csv

    HAS_CSV = True
except ImportError:
    HAS_CSV = False

try:
    from secrets import token_bytes
except ImportError:
    # python <3.6
    from os import urandom as token_bytes

log = logging.getLogger(__name__)


_DEFAULT_PASSWORDS_ENCRYPTION = "md5"
_DEFAULT_COMMAND_TIMEOUT_SECS = 0
_EXTENSION_NOT_INSTALLED = "EXTENSION NOT INSTALLED"
_EXTENSION_INSTALLED = "EXTENSION INSTALLED"
_EXTENSION_TO_UPGRADE = "EXTENSION TO UPGRADE"
_EXTENSION_TO_MOVE = "EXTENSION TO MOVE"
_EXTENSION_FLAGS = (
    _EXTENSION_NOT_INSTALLED,
    _EXTENSION_INSTALLED,
    _EXTENSION_TO_UPGRADE,
    _EXTENSION_TO_MOVE,
)
_PRIVILEGES_MAP = {
    "a": "INSERT",
    "C": "CREATE",
    "D": "TRUNCATE",
    "c": "CONNECT",
    "t": "TRIGGER",
    "r": "SELECT",
    "U": "USAGE",
    "T": "TEMPORARY",
    "w": "UPDATE",
    "X": "EXECUTE",
    "x": "REFERENCES",
    "d": "DELETE",
    "*": "GRANT",
}
_PRIVILEGES_OBJECTS = frozenset(
    (
        "schema",
        "tablespace",
        "language",
        "sequence",
        "table",
        "group",
        "database",
        "function",
    )
)
_PRIVILEGE_TYPE_MAP = {
    "table": "arwdDxt",
    "tablespace": "C",
    "language": "U",
    "sequence": "rwU",
    "schema": "UC",
    "database": "CTc",
    "function": "X",
}


def __virtual__():
    """
    Only load this module if the psql bin exist.
    initdb bin might also be used, but its presence will be detected on runtime.
    """
    utils = ["psql"]
    if not HAS_CSV:
        return False
    for util in utils:
        if not salt.utils.path.which(util):
            if not _find_pg_binary(util):
                return (False, "{} was not found".format(util))
    return True


def _find_pg_binary(util):
    """
    .. versionadded:: 2016.3.2

    Helper function to locate various psql related binaries
    """
    pg_bin_dir = __salt__["config.option"]("postgres.bins_dir")
    util_bin = salt.utils.path.which(util)
    if not util_bin:
        if pg_bin_dir:
            return salt.utils.path.which(os.path.join(pg_bin_dir, util))
    else:
        return util_bin


def _run_psql(cmd, runas=None, password=None, host=None, port=None, user=None):
    """
    Helper function to call psql, because the password requirement
    makes this too much code to be repeated in each function below
    """
    kwargs = {
        "reset_system_locale": False,
        "clean_env": True,
        "timeout": __salt__["config.option"](
            "postgres.timeout", default=_DEFAULT_COMMAND_TIMEOUT_SECS
        ),
    }
    if runas is None:
        if not host:
            host = __salt__["config.option"]("postgres.host")
        if not host or host.startswith("/"):
            if "FreeBSD" in __grains__["os_family"]:
                runas = "postgres"
            elif "OpenBSD" in __grains__["os_family"]:
                runas = "_postgresql"
            else:
                runas = "postgres"

    if user is None:
        user = runas

    if runas:
        kwargs["runas"] = runas

    if password is None:
        password = __salt__["config.option"]("postgres.pass")
    if password is not None:
        pgpassfile = salt.utils.files.mkstemp(text=True)
        with salt.utils.files.fopen(pgpassfile, "w") as fp_:
            fp_.write(
                salt.utils.stringutils.to_str(
                    "{}:{}:*:{}:{}".format(
                        "localhost" if not host or host.startswith("/") else host,
                        port if port else "*",
                        user if user else "*",
                        password,
                    )
                )
            )
            __salt__["file.chown"](pgpassfile, runas, "")
            kwargs["env"] = {"PGPASSFILE": pgpassfile}

    ret = __salt__["cmd.run_all"](cmd, python_shell=False, **kwargs)

    if ret.get("retcode", 0) != 0:
        log.error("Error connecting to Postgresql server")
    if password is not None and not __salt__["file.remove"](pgpassfile):
        log.warning("Remove PGPASSFILE failed")

    return ret


def _run_initdb(
    name,
    auth="password",
    user=None,
    password=None,
    encoding="UTF8",
    locale=None,
    runas=None,
    waldir=None,
    checksums=False,
):
    """
    Helper function to call initdb
    """
    if runas is None:
        if "FreeBSD" in __grains__["os_family"]:
            runas = "postgres"
        elif "OpenBSD" in __grains__["os_family"]:
            runas = "_postgresql"
        else:
            runas = "postgres"

    if user is None:
        user = runas
    _INITDB_BIN = _find_pg_binary("initdb")
    if not _INITDB_BIN:
        raise CommandExecutionError("initdb executable not found.")
    cmd = [
        _INITDB_BIN,
        "--pgdata={}".format(name),
        "--username={}".format(user),
        "--auth={}".format(auth),
        "--encoding={}".format(encoding),
    ]

    if locale is not None:
        cmd.append("--locale={}".format(locale))

    # intentionally use short option, as the long option name has been
    # renamed from "xlogdir" to "waldir" in PostgreSQL 10
    if waldir is not None:
        cmd.append("-X")
        cmd.append(waldir)

    if checksums:
        cmd.append("--data-checksums")

    if password is not None:
        pgpassfile = salt.utils.files.mkstemp(text=True)
        with salt.utils.files.fopen(pgpassfile, "w") as fp_:
            fp_.write(salt.utils.stringutils.to_str("{}".format(password)))
            __salt__["file.chown"](pgpassfile, runas, "")
        cmd.extend(["--pwfile={}".format(pgpassfile)])

    kwargs = dict(
        runas=runas,
        clean_env=True,
        timeout=__salt__["config.option"](
            "postgres.timeout", default=_DEFAULT_COMMAND_TIMEOUT_SECS
        ),
    )
    cmdstr = " ".join([pipes.quote(c) for c in cmd])
    ret = __salt__["cmd.run_all"](cmdstr, python_shell=False, **kwargs)

    if ret.get("retcode", 0) != 0:
        log.error("Error initilizing the postgres data directory")

    if password is not None and not __salt__["file.remove"](pgpassfile):
        log.warning("Removal of PGPASSFILE failed")

    return ret


def version(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    Return the version of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.version
    """
    query = "SELECT setting FROM pg_catalog.pg_settings WHERE name = 'server_version'"
    cmd = _psql_cmd(
        "-c",
        query,
        "-t",
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )
    ret = _run_psql(
        cmd, runas=runas, password=password, host=host, port=port, user=user
    )

    for line in salt.utils.itertools.split(ret["stdout"], "\n"):
        # Just return the first line
        return line


def _parsed_version(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    Returns the server version properly parsed and int casted for internal use.

    If the Postgres server does not respond, None will be returned.
    """

    psql_version = version(
        user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )

    if psql_version:
        return LooseVersion(psql_version)
    else:
        log.warning(
            "Attempt to parse version of Postgres server failed. "
            "Is the server responding?"
        )
        return None


def _connection_defaults(user=None, host=None, port=None, maintenance_db=None):
    """
    Returns a tuple of (user, host, port, db) with config, pillar, or default
    values assigned to missing values.
    """
    if not user:
        user = __salt__["config.option"]("postgres.user")
    if not host:
        host = __salt__["config.option"]("postgres.host")
    if not port:
        port = __salt__["config.option"]("postgres.port")
    if not maintenance_db:
        maintenance_db = __salt__["config.option"]("postgres.maintenance_db")

    return (user, host, port, maintenance_db)


def _psql_cmd(*args, **kwargs):
    """
    Return string with fully composed psql command.

    Accepts optional keyword arguments: user, host, port and maintenance_db,
    as well as any number of positional arguments to be added to the end of
    the command.
    """
    (user, host, port, maintenance_db) = _connection_defaults(
        kwargs.get("user"),
        kwargs.get("host"),
        kwargs.get("port"),
        kwargs.get("maintenance_db"),
    )
    _PSQL_BIN = _find_pg_binary("psql")
    cmd = [
        _PSQL_BIN,
        "--no-align",
        "--no-readline",
        "--no-psqlrc",
        "--no-password",
    ]  # Never prompt, handled in _run_psql.
    if user:
        cmd += ["--username", user]
    if host:
        cmd += ["--host", host]
    if port:
        cmd += ["--port", str(port)]
    if not maintenance_db:
        maintenance_db = "postgres"
    cmd.extend(["--dbname", maintenance_db])
    cmd.extend(args)
    return cmd


def _psql_prepare_and_run(
    cmd, host=None, port=None, maintenance_db=None, password=None, runas=None, user=None
):
    rcmd = _psql_cmd(
        host=host, user=user, port=port, maintenance_db=maintenance_db, *cmd
    )
    cmdret = _run_psql(
        rcmd, runas=runas, password=password, host=host, port=port, user=user
    )
    return cmdret


def psql_query(
    query,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
    write=False,
):
    """
    Run an SQL-Query and return the results as a list. This command
    only supports SELECT statements.  This limitation can be worked around
    with a query like this:

    WITH updated AS (UPDATE pg_authid SET rolconnlimit = 2000 WHERE
    rolname = 'rolename' RETURNING rolconnlimit) SELECT * FROM updated;

    query
        The query string.

    user
        Database username, if different from config or default.

    host
        Database host, if different from config or default.

    port
        Database port, if different from the config or default.

    maintenance_db
        The database to run the query against.

    password
        User password, if different from the config or default.

    runas
        User to run the command as.

    write
        Mark query as READ WRITE transaction.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.psql_query 'select * from pg_stat_activity'
    """
    ret = []

    csv_query = "COPY ({}) TO STDOUT WITH CSV HEADER".format(query.strip().rstrip(";"))

    # Mark transaction as R/W to achieve write will be allowed
    # Commit is necessary due to transaction
    if write:
        csv_query = "START TRANSACTION READ WRITE; {}; COMMIT TRANSACTION;".format(
            csv_query
        )

    # always use the same datestyle settings to allow parsing dates
    # regardless what server settings are configured
    cmdret = _psql_prepare_and_run(
        ["-v", "datestyle=ISO,MDY", "-c", csv_query],
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )
    if cmdret["retcode"] > 0:
        return ret

    csv_file = io.StringIO(cmdret["stdout"])
    header = {}
    for row in csv.reader(
        csv_file,
        delimiter=salt.utils.stringutils.to_str(","),
        quotechar=salt.utils.stringutils.to_str('"'),
    ):
        if not row:
            continue
        if not header:
            header = row
            continue
        ret.append(dict(zip(header, row)))

    # Remove 'COMMIT' message if query is inside R/W transction
    if write:
        ret = ret[0:-1]

    return ret


# Database related actions


def db_list(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    Return dictionary with information about databases of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_list
    """

    ret = {}

    query = (
        'SELECT datname as "Name", pga.rolname as "Owner", '
        'pg_encoding_to_char(encoding) as "Encoding", '
        'datcollate as "Collate", datctype as "Ctype", '
        'datacl as "Access privileges", spcname as "Tablespace" '
        "FROM pg_database pgd, pg_roles pga, pg_tablespace pgts "
        "WHERE pga.oid = pgd.datdba AND pgts.oid = pgd.dattablespace"
    )

    rows = psql_query(
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    for row in rows:
        ret[row["Name"]] = row
        ret[row["Name"]].pop("Name")

    return ret


def db_exists(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Checks if a database exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_exists 'dbname'
    """

    databases = db_list(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    return name in databases


# TODO properly implemented escaping
def _quote_ddl_value(value, quote="'"):
    if value is None:
        return None
    if quote in value:  # detect trivial sqli
        raise SaltInvocationError(
            "Unsupported character {} in value: {}".format(quote, value)
        )
    return "{quote}{value}{quote}".format(quote=quote, value=value)


def db_create(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    tablespace=None,
    encoding=None,
    lc_collate=None,
    lc_ctype=None,
    owner=None,
    template=None,
    runas=None,
):
    """
    Adds a databases to the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_create 'dbname'

        salt '*' postgres.db_create 'dbname' template=template_postgis

    """

    # Base query to create a database
    query = 'CREATE DATABASE "{}"'.format(name)

    # "With"-options to create a database
    with_args = salt.utils.odict.OrderedDict(
        [
            ("TABLESPACE", _quote_ddl_value(tablespace, '"')),
            # owner needs to be enclosed in double quotes so postgres
            # doesn't get thrown by dashes in the name
            ("OWNER", _quote_ddl_value(owner, '"')),
            ("TEMPLATE", template),
            ("ENCODING", _quote_ddl_value(encoding)),
            ("LC_COLLATE", _quote_ddl_value(lc_collate)),
            ("LC_CTYPE", _quote_ddl_value(lc_ctype)),
        ]
    )
    with_chunks = []
    for key, value in with_args.items():
        if value is not None:
            with_chunks += [key, "=", value]
    # Build a final query
    if with_chunks:
        with_chunks.insert(0, " WITH")
        query += " ".join(with_chunks)

    # Execute the command
    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    return ret["retcode"] == 0


def db_alter(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    tablespace=None,
    owner=None,
    owner_recurse=False,
    runas=None,
):
    """
    Change tablespace or/and owner of database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_alter dbname owner=otheruser
    """
    if not any((tablespace, owner)):
        return True  # Nothing todo?

    if owner and owner_recurse:
        ret = owner_to(
            name, owner, user=user, host=host, port=port, password=password, runas=runas
        )
    else:
        queries = []
        if owner:
            queries.append('ALTER DATABASE "{}" OWNER TO "{}"'.format(name, owner))
        if tablespace:
            queries.append(
                'ALTER DATABASE "{}" SET TABLESPACE "{}"'.format(name, tablespace)
            )
        for query in queries:
            ret = _psql_prepare_and_run(
                ["-c", query],
                user=user,
                host=host,
                port=port,
                maintenance_db=maintenance_db,
                password=password,
                runas=runas,
            )

    if ret["retcode"] != 0:
        return False

    return True


def db_remove(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Removes a databases from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_remove 'dbname'
    """
    for query in [
        'REVOKE CONNECT ON DATABASE "{db}" FROM public;'.format(db=name),
        "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname ="
        " '{db}' AND pid <> pg_backend_pid();".format(db=name),
        'DROP DATABASE "{db}";'.format(db=name),
    ]:
        ret = _psql_prepare_and_run(
            ["-c", query],
            user=user,
            host=host,
            port=port,
            runas=runas,
            maintenance_db=maintenance_db,
            password=password,
        )
        if ret["retcode"] != 0:
            raise Exception("Failed: ret={}".format(ret))
    return True


# Tablespace related actions


def tablespace_list(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    Return dictionary with information about tablespaces of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_list

    .. versionadded:: 2015.8.0
    """

    ret = {}

    query = (
        'SELECT spcname as "Name", pga.rolname as "Owner", spcacl as "ACL", '
        'spcoptions as "Opts", pg_tablespace_location(pgts.oid) as "Location" '
        "FROM pg_tablespace pgts, pg_roles pga WHERE pga.oid = pgts.spcowner"
    )

    rows = __salt__["postgres.psql_query"](
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    for row in rows:
        ret[row["Name"]] = row
        ret[row["Name"]].pop("Name")

    return ret


def tablespace_exists(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Checks if a tablespace exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_exists 'dbname'

    .. versionadded:: 2015.8.0
    """

    tablespaces = tablespace_list(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    return name in tablespaces


def tablespace_create(
    name,
    location,
    options=None,
    owner=None,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Adds a tablespace to the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_create tablespacename '/path/datadir'

    .. versionadded:: 2015.8.0
    """
    owner_query = ""
    options_query = ""
    if owner:
        owner_query = 'OWNER "{}"'.format(owner)
        # should come out looking like: 'OWNER postgres'
    if options:
        optionstext = ["{} = {}".format(k, v) for k, v in options.items()]
        options_query = "WITH ( {} )".format(", ".join(optionstext))
        # should come out looking like: 'WITH ( opt1 = 1.0, opt2 = 4.0 )'
    query = "CREATE TABLESPACE \"{}\" {} LOCATION '{}' {}".format(
        name, owner_query, location, options_query
    )

    # Execute the command
    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    return ret["retcode"] == 0


def tablespace_alter(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    new_name=None,
    new_owner=None,
    set_option=None,
    reset_option=None,
    runas=None,
):
    """
    Change tablespace name, owner, or options.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_alter tsname new_owner=otheruser
        salt '*' postgres.tablespace_alter index_space new_name=fast_raid
        salt '*' postgres.tablespace_alter test set_option="{'seq_page_cost': '1.1'}"
        salt '*' postgres.tablespace_alter tsname reset_option=seq_page_cost

    .. versionadded:: 2015.8.0
    """
    if not any([new_name, new_owner, set_option, reset_option]):
        return True  # Nothing todo?

    queries = []

    if new_name:
        queries.append('ALTER TABLESPACE "{}" RENAME TO "{}"'.format(name, new_name))
    if new_owner:
        queries.append('ALTER TABLESPACE "{}" OWNER TO "{}"'.format(name, new_owner))
    if set_option:
        queries.append(
            'ALTER TABLESPACE "{}" SET ({} = {})'.format(
                name, *(next(iter(set_option.items())))
            )
        )
    if reset_option:
        queries.append('ALTER TABLESPACE "{}" RESET ({})'.format(name, reset_option))

    for query in queries:
        ret = _psql_prepare_and_run(
            ["-c", query],
            user=user,
            host=host,
            port=port,
            maintenance_db=maintenance_db,
            password=password,
            runas=runas,
        )
        if ret["retcode"] != 0:
            return False

    return True


def tablespace_remove(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Removes a tablespace from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_remove tsname

    .. versionadded:: 2015.8.0
    """
    query = 'DROP TABLESPACE "{}"'.format(name)
    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        runas=runas,
        maintenance_db=maintenance_db,
        password=password,
    )
    return ret["retcode"] == 0


# User related actions


def user_list(
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
    return_password=False,
):
    """
    Return a dict with information about users of a Postgres server.

    Set return_password to True to get password hash in the result.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_list
    """

    ret = {}

    ver = _parsed_version(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    if ver:
        if ver >= LooseVersion("9.1"):
            replication_column = "pg_roles.rolreplication"
        else:
            replication_column = "NULL"
        if ver >= LooseVersion("9.5"):
            rolcatupdate_column = "NULL"
        else:
            rolcatupdate_column = "pg_roles.rolcatupdate"
    else:
        log.error("Could not retrieve Postgres version. Is Postgresql server running?")
        return False

    # will return empty string if return_password = False
    _x = lambda s: s if return_password else ""

    query = "".join(
        [
            'SELECT pg_roles.rolname as "name",pg_roles.rolsuper as "superuser",'
            ' pg_roles.rolinherit as "inherits privileges", pg_roles.rolcreaterole as'
            ' "can create roles", pg_roles.rolcreatedb as "can create databases", {0}'
            ' as "can update system catalogs", pg_roles.rolcanlogin as "can login", {1}'
            ' as "replication", pg_roles.rolconnlimit as "connections", (SELECT'
            " array_agg(pg_roles2.rolname)    FROM pg_catalog.pg_auth_members    JOIN"
            " pg_catalog.pg_roles pg_roles2 ON (pg_auth_members.roleid = pg_roles2.oid)"
            "    WHERE pg_auth_members.member = pg_roles.oid) as"
            ' "groups",pg_roles.rolvaliduntil::timestamp(0) as "expiry time",'
            ' pg_roles.rolconfig  as "defaults variables" ',
            _x(', COALESCE(pg_shadow.passwd, pg_authid.rolpassword) as "password" '),
            "FROM pg_roles ",
            _x("LEFT JOIN pg_authid ON pg_roles.oid = pg_authid.oid "),
            _x("LEFT JOIN pg_shadow ON pg_roles.oid = pg_shadow.usesysid"),
        ]
    ).format(rolcatupdate_column, replication_column)

    rows = psql_query(
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    def get_bool(rowdict, key):
        """
        Returns the boolean value of the key, instead of 't' and 'f' strings.
        """
        if rowdict[key] == "t":
            return True
        elif rowdict[key] == "f":
            return False
        else:
            return None

    for row in rows:
        retrow = {}
        for key in (
            "superuser",
            "inherits privileges",
            "can create roles",
            "can create databases",
            "can update system catalogs",
            "can login",
            "replication",
            "connections",
        ):
            retrow[key] = get_bool(row, key)
        for date_key in ("expiry time",):
            try:
                retrow[date_key] = datetime.datetime.strptime(
                    row[date_key], "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                retrow[date_key] = None
        retrow["defaults variables"] = row["defaults variables"]
        if return_password:
            retrow["password"] = row["password"]
        # use csv reader to handle quoted roles correctly
        retrow["groups"] = list(csv.reader([row["groups"].strip("{}")]))[0]
        ret[row["name"]] = retrow

    return ret


def role_get(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
    return_password=False,
):
    """
    Return a dict with information about users of a Postgres server.

    Set return_password to True to get password hash in the result.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.role_get postgres
    """
    all_users = user_list(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
        return_password=return_password,
    )
    try:
        return all_users.get(name, None)
    except AttributeError:
        log.error("Could not retrieve Postgres role. Is Postgres running?")
        return None


def user_exists(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Checks if a user exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_exists 'username'
    """
    return bool(
        role_get(
            name,
            user=user,
            host=host,
            port=port,
            maintenance_db=maintenance_db,
            password=password,
            runas=runas,
            return_password=False,
        )
    )


def _add_role_flag(string, test, flag, cond=None, prefix="NO", addtxt="", skip=False):
    if not skip:
        if cond is None:
            cond = test
        if test is not None:
            if cond:
                string = "{} {}".format(string, flag)
            else:
                string = "{0} {2}{1}".format(string, flag, prefix)
        if addtxt:
            string = "{} {}".format(string, addtxt)
    return string


def _maybe_encrypt_password(role, password, encrypted=_DEFAULT_PASSWORDS_ENCRYPTION):
    if password is not None:
        password = str(password)
    else:
        return None

    if encrypted is True:
        encrypted = "md5"
    if encrypted not in (False, "md5", "scram-sha-256"):
        raise ValueError("Unknown password algorithm: " + str(encrypted))

    if encrypted == "scram-sha-256" and not password.startswith("SCRAM-SHA-256"):
        password = _scram_sha_256(password)
    elif encrypted == "md5" and not password.startswith("md5"):
        log.warning("The md5 password algorithm was deprecated in PostgreSQL 10")
        password = _md5_password(role, password)
    elif encrypted is False:
        log.warning("Unencrypted passwords were removed in PostgreSQL 10")

    return password


def _verify_password(role, password, verifier, method):
    """
    Test the given password against the verifier.

    The given password may already be a verifier, in which case test for
     simple equality.
    """
    if method == "md5" or method is True:
        if password.startswith("md5"):
            expected = password
        else:
            expected = _md5_password(role, password)
    elif method == "scram-sha-256":
        if password.startswith("SCRAM-SHA-256"):
            expected = password
        else:
            match = re.match(r"^SCRAM-SHA-256\$(\d+):([^\$]+?)\$", verifier)
            if match:
                iterations = int(match.group(1))
                salt_bytes = base64.b64decode(match.group(2))
                expected = _scram_sha_256(
                    password, salt_bytes=salt_bytes, iterations=iterations
                )
            else:
                expected = object()
    elif method is False:
        expected = password
    else:
        expected = object()

    return verifier == expected


def _md5_password(role, password):
    return "md5{}".format(
        hashlib.md5(  # nosec
            salt.utils.stringutils.to_bytes("{}{}".format(password, role))
        ).hexdigest()
    )


def _scram_sha_256(password, salt_bytes=None, iterations=4096):
    """
    Build a SCRAM-SHA-256 password verifier.

    Ported from https://doxygen.postgresql.org/scram-common_8c.html
    """
    if salt_bytes is None:
        salt_bytes = token_bytes(16)
    password = salt.utils.stringutils.to_bytes(saslprep(password))
    salted_password = hashlib.pbkdf2_hmac("sha256", password, salt_bytes, iterations)
    stored_key = hmac.new(salted_password, b"Client Key", "sha256").digest()
    stored_key = hashlib.sha256(stored_key).digest()
    server_key = hmac.new(salted_password, b"Server Key", "sha256").digest()
    return "SCRAM-SHA-256${}:{}${}:{}".format(
        iterations,
        base64.b64encode(salt_bytes).decode("ascii"),
        base64.b64encode(stored_key).decode("ascii"),
        base64.b64encode(server_key).decode("ascii"),
    )


def _role_cmd_args(
    name,
    sub_cmd="",
    typ_="role",
    encrypted=None,
    login=None,
    connlimit=None,
    inherit=None,
    createdb=None,
    createroles=None,
    superuser=None,
    groups=None,
    replication=None,
    rolepassword=None,
    valid_until=None,
    db_role=None,
):
    if inherit is None:
        if typ_ in ["user", "group"]:
            inherit = True
    if login is None:
        if typ_ == "user":
            login = True
        if typ_ == "group":
            login = False
    # defaults to encrypted passwords
    if encrypted is None:
        encrypted = _DEFAULT_PASSWORDS_ENCRYPTION
    skip_passwd = False
    escaped_password = ""
    escaped_valid_until = ""
    if not (
        rolepassword is not None
        # first is passwd set
        # second is for handling NOPASSWD
        and (isinstance(rolepassword, str) and bool(rolepassword))
        or (isinstance(rolepassword, bool))
    ):
        skip_passwd = True
    if isinstance(rolepassword, str) and bool(rolepassword):
        escaped_password = "'{}'".format(
            _maybe_encrypt_password(
                name, rolepassword.replace("'", "''"), encrypted=encrypted
            )
        )
    if isinstance(valid_until, str) and bool(valid_until):
        escaped_valid_until = "'{}'".format(
            valid_until.replace("'", "''"),
        )
    skip_superuser = False
    if bool(db_role) and bool(superuser) == bool(db_role["superuser"]):
        skip_superuser = True
    flags = (
        {"flag": "INHERIT", "test": inherit},
        {"flag": "CREATEDB", "test": createdb},
        {"flag": "CREATEROLE", "test": createroles},
        {"flag": "SUPERUSER", "test": superuser, "skip": skip_superuser},
        {"flag": "REPLICATION", "test": replication},
        {"flag": "LOGIN", "test": login},
        {
            "flag": "CONNECTION LIMIT",
            "test": bool(connlimit),
            "addtxt": str(connlimit),
            "skip": connlimit is None,
        },
        {
            "flag": "ENCRYPTED",
            "test": (encrypted is not None and bool(rolepassword)),
            "skip": skip_passwd or isinstance(rolepassword, bool),
            "cond": bool(encrypted),
            "prefix": "UN",
        },
        {
            "flag": "PASSWORD",
            "test": bool(rolepassword),
            "skip": skip_passwd,
            "addtxt": escaped_password,
        },
        {
            "flag": "VALID UNTIL",
            "test": bool(valid_until),
            "skip": valid_until is None,
            "addtxt": escaped_valid_until,
        },
    )
    for data in flags:
        sub_cmd = _add_role_flag(sub_cmd, **data)
    if sub_cmd.endswith("WITH"):
        sub_cmd = sub_cmd.replace(" WITH", "")
    if groups:
        if isinstance(groups, list):
            groups = ",".join(groups)
        for group in groups.split(","):
            sub_cmd = '{}; GRANT "{}" TO "{}"'.format(sub_cmd, group, name)
    return sub_cmd


def _role_create(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    createroles=None,
    encrypted=None,
    superuser=None,
    login=None,
    connlimit=None,
    inherit=None,
    replication=None,
    rolepassword=None,
    valid_until=None,
    typ_="role",
    groups=None,
    runas=None,
):
    """
    Creates a Postgres role. Users and Groups are both roles in postgres.
    However, users can login, groups cannot.
    """

    # check if role exists
    if user_exists(
        name, user, host, port, maintenance_db, password=password, runas=runas
    ):
        log.info("%s '%s' already exists", typ_.capitalize(), name)
        return False

    sub_cmd = 'CREATE ROLE "{}" WITH'.format(name)
    sub_cmd = "{} {}".format(
        sub_cmd,
        _role_cmd_args(
            name,
            typ_=typ_,
            encrypted=encrypted,
            login=login,
            connlimit=connlimit,
            inherit=inherit,
            createdb=createdb,
            createroles=createroles,
            superuser=superuser,
            groups=groups,
            replication=replication,
            rolepassword=rolepassword,
            valid_until=valid_until,
        ),
    )
    ret = _psql_prepare_and_run(
        ["-c", sub_cmd],
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    return ret["retcode"] == 0


def user_create(
    username,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    createroles=None,
    inherit=None,
    login=None,
    connlimit=None,
    encrypted=None,
    superuser=None,
    replication=None,
    rolepassword=None,
    valid_until=None,
    groups=None,
    runas=None,
):
    """
    Creates a Postgres user.

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.user_create 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword' valid_until='valid_until'
    """
    return _role_create(
        username,
        typ_="user",
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        createdb=createdb,
        createroles=createroles,
        inherit=inherit,
        login=login,
        connlimit=connlimit,
        encrypted=encrypted,
        superuser=superuser,
        replication=replication,
        rolepassword=rolepassword,
        valid_until=valid_until,
        groups=groups,
        runas=runas,
    )


def _role_update(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    typ_="role",
    createroles=None,
    inherit=None,
    login=None,
    connlimit=None,
    encrypted=None,
    superuser=None,
    replication=None,
    rolepassword=None,
    valid_until=None,
    groups=None,
    runas=None,
):
    """
    Updates a postgres role.
    """
    role = role_get(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
        return_password=False,
    )

    # check if user exists
    if not bool(role):
        log.info("%s '%s' could not be found", typ_.capitalize(), name)
        return False

    sub_cmd = 'ALTER ROLE "{}" WITH'.format(name)
    sub_cmd = "{} {}".format(
        sub_cmd,
        _role_cmd_args(
            name,
            encrypted=encrypted,
            login=login,
            connlimit=connlimit,
            inherit=inherit,
            createdb=createdb,
            createroles=createroles,
            superuser=superuser,
            groups=groups,
            replication=replication,
            rolepassword=rolepassword,
            valid_until=valid_until,
            db_role=role,
        ),
    )
    ret = _psql_prepare_and_run(
        ["-c", sub_cmd],
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    return ret["retcode"] == 0


def user_update(
    username,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    createroles=None,
    encrypted=None,
    superuser=None,
    inherit=None,
    login=None,
    connlimit=None,
    replication=None,
    rolepassword=None,
    valid_until=None,
    groups=None,
    runas=None,
):
    """
    Updates a Postgres user.

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.user_update 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword' valid_until='valid_until'
    """
    return _role_update(
        username,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        typ_="user",
        inherit=inherit,
        login=login,
        connlimit=connlimit,
        createdb=createdb,
        createroles=createroles,
        encrypted=encrypted,
        superuser=superuser,
        replication=replication,
        rolepassword=rolepassword,
        valid_until=valid_until,
        groups=groups,
        runas=runas,
    )


def _role_remove(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Removes a role from the Postgres Server
    """

    # check if user exists
    if not user_exists(
        name, user, host, port, maintenance_db, password=password, runas=runas
    ):
        log.info("User '%s' does not exist", name)
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE "{}"'.format(name)
    _psql_prepare_and_run(
        ["-c", sub_cmd],
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    if not user_exists(
        name, user, host, port, maintenance_db, password=password, runas=runas
    ):
        return True
    else:
        log.info("Failed to delete user '%s'.", name)
        return False


def available_extensions(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    List available postgresql extensions

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.available_extensions

    """
    exts = []
    query = "select * from pg_available_extensions();"
    ret = psql_query(
        query,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    exts = {}
    for row in ret:
        if "default_version" in row and "name" in row:
            exts[row["name"]] = row
    return exts


def installed_extensions(
    user=None, host=None, port=None, maintenance_db=None, password=None, runas=None
):
    """
    List installed postgresql extensions

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.installed_extensions

    """
    exts = []
    query = (
        "select a.*, b.nspname as schema_name "
        "from pg_extension a,  pg_namespace b where a.extnamespace = b.oid;"
    )
    ret = psql_query(
        query,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    exts = {}
    for row in ret:
        if "extversion" in row and "extname" in row:
            exts[row["extname"]] = row
    return exts


def get_available_extension(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Get info about an available postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.get_available_extension plpgsql

    """
    return available_extensions(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    ).get(name, None)


def get_installed_extension(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Get info about an installed postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.get_installed_extension plpgsql

    """
    return installed_extensions(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    ).get(name, None)


def is_available_extension(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Test if a specific extension is available

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.is_available_extension

    """
    exts = available_extensions(
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    if name.lower() in [a.lower() for a in exts]:
        return True
    return False


def _pg_is_older_ext_ver(a, b):
    """
    Compare versions of extensions using `looseversion.LooseVersion`.

    Returns ``True`` if version a is lesser than b.
    """
    return LooseVersion(a) < LooseVersion(b)


def is_installed_extension(
    name,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Test if a specific extension is installed

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.is_installed_extension

    """
    installed_ext = get_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    return bool(installed_ext)


def create_metadata(
    name,
    ext_version=None,
    schema=None,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Get lifecycle information about an extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.create_metadata adminpack

    """
    installed_ext = get_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    ret = [_EXTENSION_NOT_INSTALLED]
    if installed_ext:
        ret = [_EXTENSION_INSTALLED]
        if ext_version is not None and _pg_is_older_ext_ver(
            installed_ext.get("extversion", ext_version), ext_version
        ):
            ret.append(_EXTENSION_TO_UPGRADE)
        if (
            schema is not None
            and installed_ext.get("extrelocatable", "f") == "t"
            and installed_ext.get("schema_name", schema) != schema
        ):
            ret.append(_EXTENSION_TO_MOVE)
    return ret


def drop_extension(
    name,
    if_exists=None,
    restrict=None,
    cascade=None,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Drop an installed postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.drop_extension 'adminpack'

    """
    if cascade is None:
        cascade = True
    if if_exists is None:
        if_exists = False
    if restrict is None:
        restrict = False
    args = ["DROP EXTENSION"]
    if if_exists:
        args.append("IF EXISTS")
    args.append(name)
    if cascade:
        args.append("CASCADE")
    if restrict:
        args.append("RESTRICT")
    args.append(";")
    cmd = " ".join(args)
    if is_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    ):
        _psql_prepare_and_run(
            ["-c", cmd],
            runas=runas,
            host=host,
            user=user,
            port=port,
            maintenance_db=maintenance_db,
            password=password,
        )
    ret = not is_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    if not ret:
        log.info("Failed to drop ext: %s", name)
    return ret


def create_extension(
    name,
    if_not_exists=None,
    schema=None,
    ext_version=None,
    from_version=None,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Install a postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.create_extension 'adminpack'

    """
    if if_not_exists is None:
        if_not_exists = True
    mtdata = create_metadata(
        name,
        ext_version=ext_version,
        schema=schema,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    installed = _EXTENSION_NOT_INSTALLED not in mtdata
    installable = is_available_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    if installable:
        if not installed:
            args = ["CREATE EXTENSION"]
            if if_not_exists:
                args.append("IF NOT EXISTS")
            args.append('"{}"'.format(name))
            sargs = []
            if schema:
                sargs.append('SCHEMA "{}"'.format(schema))
            if ext_version:
                sargs.append("VERSION {}".format(ext_version))
            if from_version:
                sargs.append("FROM {}".format(from_version))
            if sargs:
                args.append("WITH")
                args.extend(sargs)
            args.append(";")
            cmd = " ".join(args).strip()
        else:
            args = []
            if schema and _EXTENSION_TO_MOVE in mtdata:
                args.append(
                    'ALTER EXTENSION "{}" SET SCHEMA "{}";'.format(name, schema)
                )
            if ext_version and _EXTENSION_TO_UPGRADE in mtdata:
                args.append(
                    'ALTER EXTENSION "{}" UPDATE TO {};'.format(name, ext_version)
                )
            cmd = " ".join(args).strip()
        if cmd:
            _psql_prepare_and_run(
                ["-c", cmd],
                runas=runas,
                host=host,
                user=user,
                port=port,
                maintenance_db=maintenance_db,
                password=password,
            )
    mtdata = create_metadata(
        name,
        ext_version=ext_version,
        schema=schema,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )
    ret = True
    for i in _EXTENSION_FLAGS:
        if (i in mtdata) and (i != _EXTENSION_INSTALLED):
            ret = False
    if not ret:
        log.info("Failed to create ext: %s", name)
    return ret


def user_remove(
    username,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Removes a user from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_remove 'username'
    """
    return _role_remove(
        username,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )


# Group related actions


def group_create(
    groupname,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    createroles=None,
    encrypted=None,
    login=None,
    inherit=None,
    superuser=None,
    replication=None,
    rolepassword=None,
    groups=None,
    runas=None,
):
    """
    Creates a Postgres group. A group is postgres is similar to a user, but
    cannot login.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.group_create 'groupname' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    """
    return _role_create(
        groupname,
        user=user,
        typ_="group",
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        createdb=createdb,
        createroles=createroles,
        encrypted=encrypted,
        login=login,
        inherit=inherit,
        superuser=superuser,
        replication=replication,
        rolepassword=rolepassword,
        groups=groups,
        runas=runas,
    )


def group_update(
    groupname,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    createdb=None,
    createroles=None,
    encrypted=None,
    inherit=None,
    login=None,
    superuser=None,
    replication=None,
    rolepassword=None,
    groups=None,
    runas=None,
):
    """
    Updates a postgres group

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.group_update 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    """
    return _role_update(
        groupname,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        createdb=createdb,
        typ_="group",
        createroles=createroles,
        encrypted=encrypted,
        login=login,
        inherit=inherit,
        superuser=superuser,
        replication=replication,
        rolepassword=rolepassword,
        groups=groups,
        runas=runas,
    )


def group_remove(
    groupname,
    user=None,
    host=None,
    port=None,
    maintenance_db=None,
    password=None,
    runas=None,
):
    """
    Removes a group from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.group_remove 'groupname'
    """
    return _role_remove(
        groupname,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )


def owner_to(
    dbname, ownername, user=None, host=None, port=None, password=None, runas=None
):
    """
    Set the owner of all schemas, functions, tables, views and sequences to
    the given username.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.owner_to 'dbname' 'username'
    """

    sqlfile = tempfile.NamedTemporaryFile()
    sqlfile.write("begin;\n")
    sqlfile.write('alter database "{}" owner to "{}";\n'.format(dbname, ownername))

    queries = (
        # schemas
        (
            "alter schema {n} owner to {owner};",
            "select quote_ident(schema_name) as n from information_schema.schemata;",
        ),
        # tables and views
        (
            "alter table {n} owner to {owner};",
            "select quote_ident(table_schema)||'.'||quote_ident(table_name) as "
            "n from information_schema.tables where table_schema not in "
            "('pg_catalog', 'information_schema');",
        ),
        # functions
        (
            "alter function {n} owner to {owner};",
            "select p.oid::regprocedure::text as n from pg_catalog.pg_proc p "
            "join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where "
            "ns.nspname not in ('pg_catalog', 'information_schema') "
            " and not p.proisagg;",
        ),
        # aggregate functions
        (
            "alter aggregate {n} owner to {owner};",
            "select p.oid::regprocedure::text as n from pg_catalog.pg_proc p "
            "join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where "
            "ns.nspname not in ('pg_catalog', 'information_schema') "
            "and p.proisagg;",
        ),
        # sequences
        (
            "alter sequence {n} owner to {owner};",
            "select quote_ident(sequence_schema)||'.'||"
            "quote_ident(sequence_name) as n from information_schema.sequences;",
        ),
    )

    for fmt, query in queries:
        ret = psql_query(
            query,
            user=user,
            host=host,
            port=port,
            maintenance_db=dbname,
            password=password,
            runas=runas,
        )
        for row in ret:
            sqlfile.write(fmt.format(owner=ownername, n=row["n"]) + "\n")

    sqlfile.write("commit;\n")
    sqlfile.flush()
    os.chmod(sqlfile.name, 0o644)  # ensure psql can read the file

    # run the generated sqlfile in the db
    cmdret = _psql_prepare_and_run(
        ["-f", sqlfile.name],
        user=user,
        runas=runas,
        host=host,
        port=port,
        password=password,
        maintenance_db=dbname,
    )
    return cmdret


# Schema related actions


def schema_create(
    dbname,
    name,
    owner=None,
    user=None,
    db_user=None,
    db_password=None,
    db_host=None,
    db_port=None,
):
    """
    Creates a Postgres schema.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_create dbname name owner='owner' \\
                user='user' \\
                db_user='user' db_password='password'
                db_host='hostname' db_port='port'
    """

    # check if schema exists
    if schema_exists(
        dbname,
        name,
        user=user,
        db_user=db_user,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
    ):
        log.info("'%s' already exists in '%s'", name, dbname)
        return False

    sub_cmd = 'CREATE SCHEMA "{}"'.format(name)
    if owner is not None:
        sub_cmd = '{} AUTHORIZATION "{}"'.format(sub_cmd, owner)

    ret = _psql_prepare_and_run(
        ["-c", sub_cmd],
        user=db_user,
        password=db_password,
        port=db_port,
        host=db_host,
        maintenance_db=dbname,
        runas=user,
    )

    return ret["retcode"] == 0


def schema_remove(
    dbname, name, user=None, db_user=None, db_password=None, db_host=None, db_port=None
):
    """
    Removes a schema from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_remove dbname schemaname

    dbname
        Database name we work on

    schemaname
        The schema's name we'll remove

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

    """

    # check if schema exists
    if not schema_exists(
        dbname,
        name,
        user=None,
        db_user=db_user,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
    ):
        log.info("Schema '%s' does not exist in '%s'", name, dbname)
        return False

    # schema exists, proceed
    sub_cmd = 'DROP SCHEMA "{}"'.format(name)
    _psql_prepare_and_run(
        ["-c", sub_cmd],
        runas=user,
        maintenance_db=dbname,
        host=db_host,
        user=db_user,
        port=db_port,
        password=db_password,
    )

    if not schema_exists(
        dbname,
        name,
        user,
        db_user=db_user,
        db_password=db_password,
        db_host=db_host,
        db_port=db_port,
    ):
        return True
    else:
        log.info("Failed to delete schema '%s'.", name)
        return False


def schema_exists(
    dbname, name, user=None, db_user=None, db_password=None, db_host=None, db_port=None
):
    """
    Checks if a schema exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_exists dbname schemaname

    dbname
        Database name we query on

    name
       Schema name we look for

    user
        The system user the operation should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default

    """
    return bool(
        schema_get(
            dbname,
            name,
            user=user,
            db_user=db_user,
            db_host=db_host,
            db_port=db_port,
            db_password=db_password,
        )
    )


def schema_get(
    dbname, name, user=None, db_user=None, db_password=None, db_host=None, db_port=None
):
    """
    Return a dict with information about schemas in a database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_get dbname name

    dbname
        Database name we query on

    name
       Schema name we look for

    user
        The system user the operation should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    """
    all_schemas = schema_list(
        dbname,
        user=user,
        db_user=db_user,
        db_host=db_host,
        db_port=db_port,
        db_password=db_password,
    )
    try:
        return all_schemas.get(name, None)
    except AttributeError:
        log.error("Could not retrieve Postgres schema. Is Postgres running?")
        return False


def schema_list(
    dbname, user=None, db_user=None, db_password=None, db_host=None, db_port=None
):
    """
    Return a dict with information about schemas in a Postgres database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_list dbname

    dbname
        Database name we query on

    user
        The system user the operation should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    """

    ret = {}

    query = "".join(
        [
            "SELECT "
            'pg_namespace.nspname as "name",'
            'pg_namespace.nspacl as "acl", '
            'pg_roles.rolname as "owner" '
            "FROM pg_namespace "
            "LEFT JOIN pg_roles ON pg_roles.oid = pg_namespace.nspowner "
        ]
    )

    rows = psql_query(
        query,
        runas=user,
        host=db_host,
        user=db_user,
        port=db_port,
        maintenance_db=dbname,
        password=db_password,
    )

    for row in rows:
        retrow = {}
        for key in ("owner", "acl"):
            retrow[key] = row[key]
        ret[row["name"]] = retrow

    return ret


def language_list(
    maintenance_db, user=None, host=None, port=None, password=None, runas=None
):
    """
    .. versionadded:: 2016.3.0

    Return a list of languages in a database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.language_list dbname

    maintenance_db
        The database to check

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """

    ret = {}
    query = 'SELECT lanname AS "Name" FROM pg_language'

    rows = psql_query(
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    for row in rows:
        ret[row["Name"]] = row["Name"]

    return ret


def language_exists(
    name, maintenance_db, user=None, host=None, port=None, password=None, runas=None
):
    """
    .. versionadded:: 2016.3.0

    Checks if language exists in a database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.language_exists plpgsql dbname

    name
       Language to check for

    maintenance_db
        The database to check in

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of

    """

    languages = language_list(
        maintenance_db, user=user, host=host, port=port, password=password, runas=runas
    )

    return name in languages


def language_create(
    name, maintenance_db, user=None, host=None, port=None, password=None, runas=None
):
    """
    .. versionadded:: 2016.3.0

    Installs a language into a database

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.language_create plpgsql dbname

    name
       Language to install

    maintenance_db
        The database to install the language in

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """

    if language_exists(name, maintenance_db):
        log.info("Language %s already exists in %s", name, maintenance_db)
        return False

    query = "CREATE LANGUAGE {}".format(name)

    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )

    return ret["retcode"] == 0


def language_remove(
    name, maintenance_db, user=None, host=None, port=None, password=None, runas=None
):
    """
    .. versionadded:: 2016.3.0

    Removes a language from a database

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.language_remove plpgsql dbname

    name
       Language to remove

    maintenance_db
        The database to install the language in

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """

    if not language_exists(name, maintenance_db):
        log.info("Language %s does not exist in %s", name, maintenance_db)
        return False

    query = "DROP LANGUAGE {}".format(name)

    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        runas=runas,
        maintenance_db=maintenance_db,
        password=password,
    )

    return ret["retcode"] == 0


def _make_privileges_list_query(name, object_type, prepend):
    """
    Generate the SQL required for specific object type
    """
    if object_type == "table":
        query = (
            " ".join(
                [
                    "SELECT relacl AS name",
                    "FROM pg_catalog.pg_class c",
                    "JOIN pg_catalog.pg_namespace n",
                    "ON n.oid = c.relnamespace",
                    "WHERE nspname = '{0}'",
                    "AND relname = '{1}'",
                    "AND relkind in ('r', 'v')",
                    "ORDER BY relname",
                ]
            )
        ).format(prepend, name)
    elif object_type == "sequence":
        query = (
            " ".join(
                [
                    "SELECT relacl AS name",
                    "FROM pg_catalog.pg_class c",
                    "JOIN pg_catalog.pg_namespace n",
                    "ON n.oid = c.relnamespace",
                    "WHERE nspname = '{0}'",
                    "AND relname = '{1}'",
                    "AND relkind = 'S'",
                    "ORDER BY relname",
                ]
            )
        ).format(prepend, name)
    elif object_type == "schema":
        query = (
            " ".join(
                [
                    "SELECT nspacl AS name",
                    "FROM pg_catalog.pg_namespace",
                    "WHERE nspname = '{0}'",
                    "ORDER BY nspname",
                ]
            )
        ).format(name)
    elif object_type == "function":
        query = (
            " ".join(
                [
                    "SELECT proacl AS name",
                    "FROM pg_catalog.pg_proc p",
                    "JOIN pg_catalog.pg_namespace n",
                    "ON n.oid = p.pronamespace",
                    "WHERE nspname = '{0}'",
                    "AND p.oid::regprocedure::text = '{1}'",
                    "ORDER BY proname, proargtypes",
                ]
            )
        ).format(prepend, name)
    elif object_type == "tablespace":
        query = (
            " ".join(
                [
                    "SELECT spcacl AS name",
                    "FROM pg_catalog.pg_tablespace",
                    "WHERE spcname = '{0}'",
                    "ORDER BY spcname",
                ]
            )
        ).format(name)
    elif object_type == "language":
        query = (
            " ".join(
                [
                    "SELECT lanacl AS name",
                    "FROM pg_catalog.pg_language",
                    "WHERE lanname = '{0}'",
                    "ORDER BY lanname",
                ]
            )
        ).format(name)
    elif object_type == "database":
        query = (
            " ".join(
                [
                    "SELECT datacl AS name",
                    "FROM pg_catalog.pg_database",
                    "WHERE datname = '{0}'",
                    "ORDER BY datname",
                ]
            )
        ).format(name)
    elif object_type == "group":
        query = (
            " ".join(
                [
                    "SELECT rolname, admin_option",
                    "FROM pg_catalog.pg_auth_members m",
                    "JOIN pg_catalog.pg_roles r",
                    "ON m.member=r.oid",
                    "WHERE m.roleid IN",
                    "(SELECT oid",
                    "FROM pg_catalog.pg_roles",
                    "WHERE rolname='{0}')",
                    "ORDER BY rolname",
                ]
            )
        ).format(name)

    return query


def _get_object_owner(
    name,
    object_type,
    prepend="public",
    maintenance_db=None,
    user=None,
    host=None,
    port=None,
    password=None,
    runas=None,
):
    """
    Return the owner of a postgres object
    """
    if object_type == "table":
        query = (
            " ".join(
                [
                    "SELECT tableowner AS name",
                    "FROM pg_tables",
                    "WHERE schemaname = '{0}'",
                    "AND tablename = '{1}'",
                ]
            )
        ).format(prepend, name)
    elif object_type == "sequence":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_catalog.pg_class c",
                    "JOIN pg_roles r",
                    "ON c.relowner = r.oid",
                    "JOIN pg_catalog.pg_namespace n",
                    "ON n.oid = c.relnamespace",
                    "WHERE relkind='S'",
                    "AND nspname='{0}'",
                    "AND relname = '{1}'",
                ]
            )
        ).format(prepend, name)
    elif object_type == "schema":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_namespace n",
                    "JOIN pg_roles r",
                    "ON n.nspowner = r.oid",
                    "WHERE nspname = '{0}'",
                ]
            )
        ).format(name)
    elif object_type == "function":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_catalog.pg_proc p",
                    "JOIN pg_catalog.pg_namespace n",
                    "ON n.oid = p.pronamespace",
                    "JOIN pg_catalog.pg_roles r",
                    "ON p.proowner = r.oid",
                    "WHERE nspname = '{0}'",
                    "AND p.oid::regprocedure::text = '{1}'",
                    "ORDER BY proname, proargtypes",
                ]
            )
        ).format(prepend, name)
    elif object_type == "tablespace":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_tablespace t",
                    "JOIN pg_roles r",
                    "ON t.spcowner = r.oid",
                    "WHERE spcname = '{0}'",
                ]
            )
        ).format(name)
    elif object_type == "language":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_language l",
                    "JOIN pg_roles r",
                    "ON l.lanowner = r.oid",
                    "WHERE lanname = '{0}'",
                ]
            )
        ).format(name)
    elif object_type == "database":
        query = (
            " ".join(
                [
                    "SELECT rolname AS name",
                    "FROM pg_database d",
                    "JOIN pg_roles r",
                    "ON d.datdba = r.oid",
                    "WHERE datname = '{0}'",
                ]
            )
        ).format(name)

    rows = psql_query(
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )
    try:
        ret = rows[0]["name"]
    except IndexError:
        ret = None

    return ret


def _validate_privileges(object_type, privs, privileges):
    """
    Validate the supplied privileges
    """
    if object_type != "group":
        _perms = [_PRIVILEGES_MAP[perm] for perm in _PRIVILEGE_TYPE_MAP[object_type]]
        _perms.append("ALL")

        if object_type not in _PRIVILEGES_OBJECTS:
            raise SaltInvocationError(
                "Invalid object_type: {} provided".format(object_type)
            )

        if not set(privs).issubset(set(_perms)):
            raise SaltInvocationError(
                "Invalid privilege(s): {} provided for object {}".format(
                    privileges, object_type
                )
            )
    else:
        if privileges:
            raise SaltInvocationError(
                "The privileges option should not be set for object_type group"
            )


def _mod_priv_opts(object_type, privileges):
    """
    Format options
    """
    object_type = object_type.lower()
    privileges = "" if privileges is None else privileges
    _privs = re.split(r"\s?,\s?", privileges.upper())

    return object_type, privileges, _privs


def _process_priv_part(perms):
    """
    Process part
    """
    _tmp = {}
    previous = None
    for perm in perms:
        if previous is None:
            _tmp[_PRIVILEGES_MAP[perm]] = False
            previous = _PRIVILEGES_MAP[perm]
        else:
            if perm == "*":
                _tmp[previous] = True
            else:
                _tmp[_PRIVILEGES_MAP[perm]] = False
                previous = _PRIVILEGES_MAP[perm]
    return _tmp


def privileges_list(
    name,
    object_type,
    prepend="public",
    maintenance_db=None,
    user=None,
    host=None,
    port=None,
    password=None,
    runas=None,
):
    """
    .. versionadded:: 2016.3.0

    Return a list of privileges for the specified object.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.privileges_list table_name table maintenance_db=db_name

    name
       Name of the object for which the permissions should be returned

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

    prepend
        Table and Sequence object types live under a schema so this should be
        provided if the object is not under the default `public` schema

    maintenance_db
        The database to connect to

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """
    object_type = object_type.lower()
    query = _make_privileges_list_query(name, object_type, prepend)

    if object_type not in _PRIVILEGES_OBJECTS:
        raise SaltInvocationError(
            "Invalid object_type: {} provided".format(object_type)
        )

    rows = psql_query(
        query,
        runas=runas,
        host=host,
        user=user,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
    )

    ret = {}

    for row in rows:
        if object_type != "group":
            result = row["name"]
            result = result.strip("{}")
            parts = result.split(",")
            for part in parts:
                perms_part, _ = part.split("/")
                rolename, perms = perms_part.split("=")
                if rolename == "":
                    rolename = "public"
                _tmp = _process_priv_part(perms)
                ret[rolename] = _tmp
        else:
            if row["admin_option"] == "t":
                admin_option = True
            else:
                admin_option = False

            ret[row["rolname"]] = admin_option

    return ret


def has_privileges(
    name,
    object_name,
    object_type,
    privileges=None,
    grant_option=None,
    prepend="public",
    maintenance_db=None,
    user=None,
    host=None,
    port=None,
    password=None,
    runas=None,
):
    """
    .. versionadded:: 2016.3.0

    Check if a role has the specified privileges on an object

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.has_privileges user_name table_name table \\
        SELECT,INSERT maintenance_db=db_name

    name
       Name of the role whose privileges should be checked on object_type

    object_name
       Name of the object on which the check is to be performed

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

    privileges
       Comma separated list of privileges to check, from the list below:

       - INSERT
       - CREATE
       - TRUNCATE
       - CONNECT
       - TRIGGER
       - SELECT
       - USAGE
       - TEMPORARY
       - UPDATE
       - EXECUTE
       - REFERENCES
       - DELETE
       - ALL

    grant_option
        If grant_option is set to True, the grant option check is performed

    prepend
        Table and Sequence object types live under a schema so this should be
        provided if the object is not under the default `public` schema

    maintenance_db
        The database to connect to

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """
    object_type, privileges, _privs = _mod_priv_opts(object_type, privileges)

    _validate_privileges(object_type, _privs, privileges)

    if object_type != "group":
        owner = _get_object_owner(
            object_name,
            object_type,
            prepend=prepend,
            maintenance_db=maintenance_db,
            user=user,
            host=host,
            port=port,
            password=password,
            runas=runas,
        )
        if owner is not None and name == owner:
            return True

    _privileges = privileges_list(
        object_name,
        object_type,
        prepend=prepend,
        maintenance_db=maintenance_db,
        user=user,
        host=host,
        port=port,
        password=password,
        runas=runas,
    )

    if name in _privileges:
        if object_type == "group":
            if grant_option:
                retval = _privileges[name]
            else:
                retval = True
            return retval
        else:
            _perms = _PRIVILEGE_TYPE_MAP[object_type]
            if grant_option:
                perms = {_PRIVILEGES_MAP[perm]: True for perm in _perms}
                retval = perms == _privileges[name]
            else:
                perms = [_PRIVILEGES_MAP[perm] for perm in _perms]
                if "ALL" in _privs:
                    retval = sorted(perms) == sorted(_privileges[name])
                else:
                    retval = set(_privs).issubset(set(_privileges[name]))
            return retval

    return False


def privileges_grant(
    name,
    object_name,
    object_type,
    privileges=None,
    grant_option=None,
    prepend="public",
    maintenance_db=None,
    user=None,
    host=None,
    port=None,
    password=None,
    runas=None,
):
    """
    .. versionadded:: 2016.3.0

    Grant privileges on a postgres object

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.privileges_grant user_name table_name table \\
        SELECT,UPDATE maintenance_db=db_name

    name
       Name of the role to which privileges should be granted

    object_name
       Name of the object on which the grant is to be performed

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

    privileges
       Comma separated list of privileges to grant, from the list below:

       - INSERT
       - CREATE
       - TRUNCATE
       - CONNECT
       - TRIGGER
       - SELECT
       - USAGE
       - TEMPORARY
       - UPDATE
       - EXECUTE
       - REFERENCES
       - DELETE
       - ALL

    grant_option
        If grant_option is set to True, the recipient of the privilege can
        in turn grant it to others

    prepend
        Table and Sequence object types live under a schema so this should be
        provided if the object is not under the default `public` schema

    maintenance_db
        The database to connect to

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """
    object_type, privileges, _privs = _mod_priv_opts(object_type, privileges)

    _validate_privileges(object_type, _privs, privileges)

    if has_privileges(
        name,
        object_name,
        object_type,
        privileges,
        prepend=prepend,
        maintenance_db=maintenance_db,
        user=user,
        host=host,
        port=port,
        password=password,
        runas=runas,
    ):
        log.info(
            "The object: %s of type: %s already has privileges: %s set",
            object_name,
            object_type,
            privileges,
        )
        return False

    _grants = ",".join(_privs)

    if object_type in ["table", "sequence"]:
        on_part = '{}."{}"'.format(prepend, object_name)
    elif object_type == "function":
        on_part = "{}".format(object_name)
    else:
        on_part = '"{}"'.format(object_name)

    if grant_option:
        if object_type == "group":
            query = 'GRANT {} TO "{}" WITH ADMIN OPTION'.format(object_name, name)
        elif object_type in ("table", "sequence") and object_name.upper() == "ALL":
            query = 'GRANT {} ON ALL {}S IN SCHEMA {} TO "{}" WITH GRANT OPTION'.format(
                _grants, object_type.upper(), prepend, name
            )
        else:
            query = 'GRANT {} ON {} {} TO "{}" WITH GRANT OPTION'.format(
                _grants, object_type.upper(), on_part, name
            )
    else:
        if object_type == "group":
            query = 'GRANT {} TO "{}"'.format(object_name, name)
        elif object_type in ("table", "sequence") and object_name.upper() == "ALL":
            query = 'GRANT {} ON ALL {}S IN SCHEMA {} TO "{}"'.format(
                _grants, object_type.upper(), prepend, name
            )
        else:
            query = 'GRANT {} ON {} {} TO "{}"'.format(
                _grants, object_type.upper(), on_part, name
            )

    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )

    return ret["retcode"] == 0


def privileges_revoke(
    name,
    object_name,
    object_type,
    privileges=None,
    prepend="public",
    maintenance_db=None,
    user=None,
    host=None,
    port=None,
    password=None,
    runas=None,
):
    """
    .. versionadded:: 2016.3.0

    Revoke privileges on a postgres object

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.privileges_revoke user_name table_name table \\
        SELECT,UPDATE maintenance_db=db_name

    name
       Name of the role whose privileges should be revoked

    object_name
       Name of the object on which the revoke is to be performed

    object_type
       The object type, which can be one of the following:

       - table
       - sequence
       - schema
       - tablespace
       - language
       - database
       - group
       - function

    privileges
       Comma separated list of privileges to revoke, from the list below:

       - INSERT
       - CREATE
       - TRUNCATE
       - CONNECT
       - TRIGGER
       - SELECT
       - USAGE
       - TEMPORARY
       - UPDATE
       - EXECUTE
       - REFERENCES
       - DELETE
       - ALL

    maintenance_db
        The database to connect to

    user
        database username if different from config or default

    password
        user password if any password for a specified user

    host
        Database host if different from config or default

    port
        Database port if different from config or default

    runas
        System user all operations should be performed on behalf of
    """
    object_type, privileges, _privs = _mod_priv_opts(object_type, privileges)

    _validate_privileges(object_type, _privs, privileges)

    if not has_privileges(
        name,
        object_name,
        object_type,
        privileges,
        prepend=prepend,
        maintenance_db=maintenance_db,
        user=user,
        host=host,
        port=port,
        password=password,
        runas=runas,
    ):
        log.info(
            "The object: %s of type: %s does not have privileges: %s set",
            object_name,
            object_type,
            privileges,
        )
        return False

    _grants = ",".join(_privs)

    if object_type in ["table", "sequence"]:
        on_part = "{}.{}".format(prepend, object_name)
    else:
        on_part = object_name

    if object_type == "group":
        query = "REVOKE {} FROM {}".format(object_name, name)
    else:
        query = "REVOKE {} ON {} {} FROM {}".format(
            _grants, object_type.upper(), on_part, name
        )

    ret = _psql_prepare_and_run(
        ["-c", query],
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )

    return ret["retcode"] == 0


def datadir_init(
    name,
    auth="password",
    user=None,
    password=None,
    encoding="UTF8",
    locale=None,
    waldir=None,
    checksums=False,
    runas=None,
):
    """
    .. versionadded:: 2016.3.0

    Initializes a postgres data directory

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.datadir_init '/var/lib/pgsql/data'

    name
        The name of the directory to initialize

    auth
        The default authentication method for local connections

    password
        The password to set for the postgres user

    user
        The database superuser name

    encoding
        The default encoding for new databases

    locale
        The default locale for new databases

    waldir
        The transaction log (WAL) directory (default is to keep WAL
        inside the data directory)

        .. versionadded:: 2019.2.0

    checksums
        If True, the cluster will be created with data page checksums.

        .. note:: Data page checksums are supported since PostgreSQL 9.3.

        .. versionadded:: 2019.2.0

    runas
        The system user the operation should be performed on behalf of

    """
    if datadir_exists(name):
        log.info("%s already exists", name)
        return False

    ret = _run_initdb(
        name,
        auth=auth,
        user=user,
        password=password,
        encoding=encoding,
        locale=locale,
        waldir=waldir,
        checksums=checksums,
        runas=runas,
    )
    return ret["retcode"] == 0


def datadir_exists(name):
    """
    .. versionadded:: 2016.3.0

    Checks if postgres data directory has been initialized

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.datadir_exists '/var/lib/pgsql/data'

    name
        Name of the directory to check
    """
    _version_file = os.path.join(name, "PG_VERSION")
    _config_file = os.path.join(name, "postgresql.conf")

    return os.path.isfile(_version_file) and os.path.isfile(_config_file)
