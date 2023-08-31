"""
SQLite sdb Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

This module allows access to sqlite3 using an ``sdb://`` URI

Like all sdb modules, the sqlite3 module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. For example:

.. code-block:: yaml

    mysqlite:
      driver: sqlite3
      database: /tmp/sdb.sqlite
      table: sdb
      create_table: True

The ``driver`` refers to the sqlite3 module, ``database`` refers to the sqlite3
database file. ``table`` is the table within the db that will hold keys and
values (defaults to ``sdb``). The database and table will be created if they
do not exist.

Advanced Usage:
===============

Instead of a table name, it is possible to provide custom SQL statements to
create the table(s) and get and set values.

.. code-block:: yaml

    myadvanced
      driver: sqlite3
      database: /tmp/sdb-advanced.sqlite
    create_statements:
      - "CREATE TABLE advanced (a text, b text, c blob, d blob)"
      - "CREATE INDEX myidx ON advanced (a)"
    get_query: "SELECT d FROM advanced WHERE a=:key"
    set_query: "INSERT OR REPLACE INTO advanced (a, d) VALUES (:key, :value)"
"""

import codecs
import logging

import salt.utils.msgpack

try:
    import sqlite3

    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False


DEFAULT_TABLE = "sdb"

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only load if sqlite3 is available.
    """
    if not HAS_SQLITE3:
        return False
    return True


def _quote(s, errors="strict"):
    encodable = s.encode("utf-8", errors).decode("utf-8")

    nul_index = encodable.find("\x00")

    if nul_index >= 0:
        error = UnicodeEncodeError(
            "NUL-terminated utf-8",
            encodable,
            nul_index,
            nul_index + 1,
            "NUL not allowed",
        )
        error_handler = codecs.lookup_error(errors)
        replacement, _ = error_handler(error)
        encodable = encodable.replace("\x00", replacement)

    return '"' + encodable.replace('"', '""') + '"'


def _connect(profile):
    db = profile["database"]
    table = None
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    stmts = profile.get("create_statements")
    table = profile.get("table", DEFAULT_TABLE)
    idx = _quote(table + "_idx")
    table = _quote(table)

    try:
        if stmts:
            for sql in stmts:
                cur.execute(sql)
        elif profile.get("create_table", True):
            cur.execute("CREATE TABLE {} (key text, value blob)".format(table))
            cur.execute("CREATE UNIQUE INDEX {} ON {} (key)".format(idx, table))
    except sqlite3.OperationalError:
        pass

    return (conn, cur, table)


def set_(key, value, profile=None):
    """
    Set a key/value pair in sqlite3
    """
    if not profile:
        return False
    conn, cur, table = _connect(profile)
    value = memoryview(salt.utils.msgpack.packb(value))
    q = profile.get(
        "set_query",
        "INSERT OR REPLACE INTO {} VALUES (:key, :value)".format(table),
    )
    conn.execute(q, {"key": key, "value": value})
    conn.commit()
    return True


def get(key, profile=None):
    """
    Get a value from sqlite3
    """
    if not profile:
        return None
    _, cur, table = _connect(profile)
    q = profile.get("get_query", "SELECT value FROM {} WHERE key=:key".format(table))
    res = cur.execute(q, {"key": key})
    res = res.fetchone()
    if not res:
        return None
    return salt.utils.msgpack.unpackb(res[0], raw=False)
