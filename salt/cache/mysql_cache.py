"""
Minion data cache plugin for MySQL database.

.. versionadded:: 2018.3.0

It is up to the system administrator to set up and configure the MySQL
infrastructure. All is needed for this plugin is a working MySQL server.

.. warning::

    The mysql.database and mysql.table_name will be directly added into certain
    queries. Salt treats these as trusted input.

The module requires the database (default ``salt_cache``) to exist but creates
its own table if needed. The keys are indexed using the ``bank`` and
``etcd_key`` columns.

To enable this cache plugin, the master will need the python client for
MySQL installed. This can be easily installed with pip:

.. code-block:: bash

    pip install pymysql

Optionally, depending on the MySQL agent configuration, the following values
could be set in the master config. These are the defaults:

.. code-block:: yaml

    mysql.host: 127.0.0.1
    mysql.port: 2379
    mysql.user: None
    mysql.password: None
    mysql.database: salt_cache
    mysql.table_name: cache

Related docs can be found in the `python-mysql documentation`_.

To use the mysql as a minion data cache backend, set the master ``cache`` config
value to ``mysql``:

.. code-block:: yaml

    cache: mysql


.. _`MySQL documentation`: https://github.com/coreos/mysql
.. _`python-mysql documentation`: http://python-mysql.readthedocs.io/en/latest/

"""

import copy
import logging
import time

import salt.payload
import salt.utils.stringutils
from salt.exceptions import SaltCacheError

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.converters
    import MySQLdb.cursors
    from MySQLdb.connections import OperationalError
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.converters
        import MySQLdb.cursors
        from MySQLdb.err import OperationalError
    except ImportError:
        MySQLdb = None


_DEFAULT_DATABASE_NAME = "salt_cache"
_DEFAULT_CACHE_TABLE_NAME = "cache"
_RECONNECT_INTERVAL_SEC = 0.050

log = logging.getLogger(__name__)

# Module properties

__virtualname__ = "mysql"
__func_alias__ = {"ls": "list"}


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


def force_reconnect():
    """
    Force a reconnection to the MySQL database, by removing the client from
    Salt's __context__.
    """
    __context__.pop("mysql_client", None)


def run_query(conn, query, args=None, retries=3):
    """
    Get a cursor and run a query. Reconnect up to ``retries`` times if
    needed.
    Returns: cursor, affected rows counter
    Raises: SaltCacheError, AttributeError, OperationalError
    """
    if conn is None:
        conn = __context__.get("mysql_client")
    try:
        cur = conn.cursor()

        if not args:
            log.debug("Doing query: %s", query)
            out = cur.execute(query)
        else:
            log.debug("Doing query: %s args: %s ", query, repr(args))
            out = cur.execute(query, args)

        return cur, out
    except (AttributeError, OperationalError) as e:
        if retries == 0:
            raise
        # reconnect creating new client
        time.sleep(_RECONNECT_INTERVAL_SEC)
        if conn is None:
            log.debug("mysql_cache: creating db connection")
        else:
            log.info("mysql_cache: recreating db connection due to: %r", e)
        __context__["mysql_client"] = MySQLdb.connect(**__context__["mysql_kwargs"])
        return run_query(
            conn=__context__.get("mysql_client"),
            query=query,
            args=args,
            retries=(retries - 1),
        )
    except Exception as e:  # pylint: disable=broad-except
        if len(query) > 150:
            query = query[:150] + "<...>"
        raise SaltCacheError(
            "Error running {}{}: {}".format(
                query, "- args: {}".format(args) if args else "", e
            )
        )


def _create_table():
    """
    Create table if needed
    """
    # Explicitly check if the table already exists as the library logs a
    # warning on CREATE TABLE
    query = """SELECT COUNT(TABLE_NAME) FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s"""
    cur, _ = run_query(
        __context__.get("mysql_client"),
        query,
        args=(__context__["mysql_kwargs"]["db"], __context__["mysql_table_name"]),
    )
    r = cur.fetchone()
    cur.close()
    if r[0] == 1:
        query = """
        SELECT COUNT(TABLE_NAME)
        FROM
            information_schema.columns
        WHERE
            table_schema = %s
            AND table_name = %s
            AND column_name = 'last_update'
        """
        cur, _ = run_query(
            __context__["mysql_client"],
            query,
            args=(__context__["mysql_kwargs"]["db"], __context__["mysql_table_name"]),
        )
        r = cur.fetchone()
        cur.close()
        if r[0] == 1:
            return
        else:
            query = """
            ALTER TABLE {}.{}
            ADD COLUMN last_update TIMESTAMP NOT NULL
                                   DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP
            """.format(
                __context__["mysql_kwargs"]["db"], __context__["mysql_table_name"]
            )
            cur, _ = run_query(__context__["mysql_client"], query)
            cur.close()
            return

    query = """CREATE TABLE IF NOT EXISTS {} (
      bank CHAR(255),
      etcd_key CHAR(255),
      data MEDIUMBLOB,
      last_update TIMESTAMP NOT NULL
                  DEFAULT CURRENT_TIMESTAMP
                  ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY(bank, etcd_key)
    );""".format(
        __context__["mysql_table_name"]
    )
    log.info("mysql_cache: creating table %s", __context__["mysql_table_name"])
    cur, _ = run_query(__context__.get("mysql_client"), query)
    cur.close()


def _init_client():
    """Initialize connection and create table if needed"""
    if __context__.get("mysql_client") is not None:
        return

    opts = copy.deepcopy(__opts__)
    mysql_kwargs = {
        "autocommit": True,
        "host": opts.pop("mysql.host", "127.0.0.1"),
        "user": opts.pop("mysql.user", None),
        "passwd": opts.pop("mysql.password", None),
        "db": opts.pop("mysql.database", _DEFAULT_DATABASE_NAME),
        "port": opts.pop("mysql.port", 3306),
        "unix_socket": opts.pop("mysql.unix_socket", None),
        "connect_timeout": opts.pop("mysql.connect_timeout", None),
    }
    mysql_kwargs["autocommit"] = True

    __context__["mysql_table_name"] = opts.pop("mysql.table_name", "salt")

    # Gather up any additional MySQL configuration options
    for k in opts:
        if k.startswith("mysql."):
            _key = k.split(".")[1]
            mysql_kwargs[_key] = opts.get(k)

    # TODO: handle SSL connection parameters

    for k, v in copy.deepcopy(mysql_kwargs).items():
        if v is None:
            mysql_kwargs.pop(k)
    kwargs_copy = mysql_kwargs.copy()
    kwargs_copy["passwd"] = "<hidden>"
    log.info("mysql_cache: Setting up client with params: %r", kwargs_copy)
    __context__["mysql_kwargs"] = mysql_kwargs
    # The MySQL client is created later on by run_query
    _create_table()


def store(bank, key, data):
    """
    Store a key value.
    """
    _init_client()
    data = salt.payload.dumps(data)
    query = "REPLACE INTO {} (bank, etcd_key, data) values(%s,%s,%s)".format(
        __context__["mysql_table_name"]
    )
    args = (bank, key, data)

    cur, cnt = run_query(__context__.get("mysql_client"), query, args=args)
    cur.close()
    if cnt not in (1, 2):
        raise SaltCacheError("Error storing {} {} returned {}".format(bank, key, cnt))


def fetch(bank, key):
    """
    Fetch a key value.
    """
    _init_client()
    query = "SELECT data FROM {} WHERE bank=%s AND etcd_key=%s".format(
        __context__["mysql_table_name"]
    )
    cur, _ = run_query(__context__.get("mysql_client"), query, args=(bank, key))
    r = cur.fetchone()
    cur.close()
    if r is None:
        return {}
    return salt.payload.loads(r[0])


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content.
    """
    _init_client()
    query = "DELETE FROM {} WHERE bank=%s".format(__context__["mysql_table_name"])
    if key is None:
        data = (bank,)
    else:
        data = (bank, key)
        query += " AND etcd_key=%s"

    cur, _ = run_query(__context__["mysql_client"], query, args=data)
    cur.close()


def ls(bank):
    """
    Return an iterable object containing all entries stored in the specified
    bank.
    """
    _init_client()
    query = "SELECT etcd_key FROM {} WHERE bank=%s".format(
        __context__["mysql_table_name"]
    )
    cur, _ = run_query(__context__.get("mysql_client"), query, args=(bank,))
    out = [row[0] for row in cur.fetchall()]
    cur.close()
    return out


def contains(bank, key):
    """
    Checks if the specified bank contains the specified key.
    """
    _init_client()
    if key is None:
        data = (bank,)
        query = "SELECT COUNT(data) FROM {} WHERE bank=%s".format(
            __context__["mysql_table_name"]
        )
    else:
        data = (bank, key)
        query = "SELECT COUNT(data) FROM {} WHERE bank=%s AND etcd_key=%s".format(
            __context__["mysql_table_name"]
        )
    cur, _ = run_query(__context__.get("mysql_client"), query, args=data)
    r = cur.fetchone()
    cur.close()
    return r[0] == 1


def updated(bank, key):
    """
    Return the integer Unix epoch update timestamp of the specified bank and
    key.
    """
    _init_client()
    query = (
        "SELECT UNIX_TIMESTAMP(last_update) FROM {} WHERE bank=%s "
        "AND etcd_key=%s".format(__context__["mysql_table_name"])
    )
    data = (bank, key)
    cur, _ = run_query(__context__["mysql_client"], query=query, args=data)
    r = cur.fetchone()
    cur.close()
    return int(r[0]) if r else r
