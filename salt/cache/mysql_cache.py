# -*- coding: utf-8 -*-
"""
Minion data cache plugin for MySQL database.

.. versionadded:: develop

It is up to the system administrator to set up and configure the MySQL
infrastructure. All is needed for this plugin is a working MySQL server.

The module requires the `salt_cache` database to exists but creates its own
table if needed. The keys are indexed using the `bank` and `etcd_key` columns.

To enable this cache plugin, the master will need the python client for
MySQL installed. This can be easily installed with pip:

.. code-block:: bash

    pip install python-mysql

Optionally, depending on the MySQL agent configuration, the following values
could be set in the master config. These are the defaults:

.. code-block:: yaml

    mysql.host: 127.0.0.1
    mysql.port: 2379
    mysql.user: None
    mysql.password: None
    mysql.database: salt_cache
    mysql.table_name: cache

Related docs could be found in the `python-mysql documentation`_.

To use the mysql as a minion data cache backend, set the master ``cache`` config
value to ``mysql``:

.. code-block:: yaml

    cache: mysql


.. _`MySQL documentation`: https://github.com/coreos/mysql
.. _`python-mysql documentation`: http://python-mysql.readthedocs.io/en/latest/

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
from time import sleep

from salt.exceptions import SaltCacheError

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.cursors
    import MySQLdb.converters
    from MySQLdb.connections import OperationalError
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.cursors
        import MySQLdb.converters
        from MySQLdb.err import OperationalError
    except ImportError:
        MySQLdb = None


_DEFAULT_DATABASE_NAME = "salt_cache"
_DEFAULT_CACHE_TABLE_NAME = "cache"
_RECONNECT_INTERVAL_SEC = 0.050

log = logging.getLogger(__name__)
client = None
_mysql_kwargs = None
_table_name = None

# Module properties

__virtualname__ = "mysql"
__func_alias__ = {"ls": "list"}


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


def run_query(conn, query, retries=3):
    """
    Get a cursor and run a query. Reconnect up to `retries` times if
    needed.
    Returns: cursor, affected rows counter
    Raises: SaltCacheError, AttributeError, OperationalError
    """
    try:
        cur = conn.cursor()
        out = cur.execute(query)
        return cur, out
    except (AttributeError, OperationalError) as e:
        if retries == 0:
            raise
        # reconnect creating new client
        sleep(_RECONNECT_INTERVAL_SEC)
        if conn is None:
            log.debug("mysql_cache: creating db connection")
        else:
            log.info("mysql_cache: recreating db connection due to: %r", e)
        global client
        client = MySQLdb.connect(**_mysql_kwargs)
        return run_query(client, query, retries - 1)
    except Exception as e:  # pylint: disable=broad-except
        if len(query) > 150:
            query = query[:150] + "<...>"
        raise SaltCacheError("Error running {0}: {1}".format(query, e))


def _create_table():
    """
    Create table if needed
    """
    # Explicitely check if the table already exists as the library logs a
    # warning on CREATE TABLE
    query = """SELECT COUNT(TABLE_NAME) FROM information_schema.tables
        WHERE table_schema = '{0}' AND table_name = '{1}'""".format(
        _mysql_kwargs["db"], _table_name,
    )
    cur, _ = run_query(client, query)
    r = cur.fetchone()
    cur.close()
    if r[0] == 1:
        return

    query = """CREATE TABLE IF NOT EXISTS {0} (
      bank CHAR(255),
      etcd_key CHAR(255),
      data MEDIUMBLOB,
      PRIMARY KEY(bank, etcd_key)
    );""".format(
        _table_name
    )
    log.info("mysql_cache: creating table %s", _table_name)
    cur, _ = run_query(client, query)
    cur.close()


def _init_client():
    """Initialize connection and create table if needed
    """
    if client is not None:
        return

    global _mysql_kwargs, _table_name
    _mysql_kwargs = {
        "host": __opts__.get("mysql.host", "127.0.0.1"),
        "user": __opts__.get("mysql.user", None),
        "passwd": __opts__.get("mysql.password", None),
        "db": __opts__.get("mysql.database", _DEFAULT_DATABASE_NAME),
        "port": __opts__.get("mysql.port", 3306),
        "unix_socket": __opts__.get("mysql.unix_socket", None),
        "connect_timeout": __opts__.get("mysql.connect_timeout", None),
        "autocommit": True,
    }
    _table_name = __opts__.get("mysql.table_name", _table_name)
    # TODO: handle SSL connection parameters

    for k, v in _mysql_kwargs.items():
        if v is None:
            _mysql_kwargs.pop(k)
    kwargs_copy = _mysql_kwargs.copy()
    kwargs_copy["passwd"] = "<hidden>"
    log.info("mysql_cache: Setting up client with params: %r", kwargs_copy)
    # The MySQL client is created later on by run_query
    _create_table()


def store(bank, key, data):
    """
    Store a key value.
    """
    _init_client()
    data = __context__["serial"].dumps(data)
    query = (
        b"REPLACE INTO {0} (bank, etcd_key, data) values('{1}', '{2}', "
        b"'{3}')".format(_table_name, bank, key, data)
    )

    cur, cnt = run_query(client, query)
    cur.close()
    if cnt not in (1, 2):
        raise SaltCacheError(
            "Error storing {0} {1} returned {2}".format(bank, key, cnt)
        )


def fetch(bank, key):
    """
    Fetch a key value.
    """
    _init_client()
    query = "SELECT data FROM {0} WHERE bank='{1}' AND etcd_key='{2}'".format(
        _table_name, bank, key
    )
    cur, _ = run_query(client, query)
    r = cur.fetchone()
    cur.close()
    if r is None:
        return {}
    return __context__["serial"].loads(r[0])


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content.
    """
    _init_client()
    query = "DELETE FROM {0} WHERE bank='{1}'".format(_table_name, bank)
    if key is not None:
        query += " AND etcd_key='{0}'".format(key)

    cur, _ = run_query(client, query)
    cur.close()


def ls(bank):
    """
    Return an iterable object containing all entries stored in the specified
    bank.
    """
    _init_client()
    query = "SELECT etcd_key FROM {0} WHERE bank='{1}'".format(_table_name, bank)
    cur, _ = run_query(client, query)
    out = [row[0] for row in cur.fetchall()]
    cur.close()
    return out


def contains(bank, key):
    """
    Checks if the specified bank contains the specified key.
    """
    _init_client()
    query = "SELECT COUNT(data) FROM {0} WHERE bank='{1}' " "AND etcd_key='{2}'".format(
        _table_name, bank, key
    )
    cur, _ = run_query(client, query)
    r = cur.fetchone()
    cur.close()
    return r[0] == 1
