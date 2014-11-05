# -*- coding: utf-8 -*-
'''
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

The ``driver`` refers to the sqlite3 module, ``database`` refers to the sqlite3
database file. ``table`` is the table within the db that will hold keys and
values (defaults to ``sdb``). The database and table will be created if they
do not exist.
'''
from __future__ import absolute_import

# Import python libs
import logging
import codecs
try:
    import sqlite3
    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False

# Import third party libs
import msgpack


DEFAULT_TABLE = 'sdb'

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    if not HAS_SQLITE3:
        return False
    return True


def _quote(s, errors="strict"):
    encodable = s.encode("utf-8", errors).decode("utf-8")

    nul_index = encodable.find("\x00")

    if nul_index >= 0:
        error = UnicodeEncodeError("NUL-terminated utf-8", encodable,
                                   nul_index, nul_index + 1, "NUL not allowed")
        error_handler = codecs.lookup_error(errors)
        replacement, _ = error_handler(error)
        encodable = encodable.replace("\x00", replacement)

    return "\"" + encodable.replace("\"", "\"\"") + "\""


def _connect(profile):
    db = profile['database']
    table = profile.get('table', DEFAULT_TABLE)
    idx = _quote(table + '_idx')
    table = _quote(table)

    conn = sqlite3.connect(db)
    cur = conn.cursor()

    try:
        cur.execute('CREATE TABLE {0} (key text, value blob)'.format(table))
        cur.execute('CREATE UNIQUE INDEX {0} ON {1} (key)'.format(idx, table))
    except sqlite3.OperationalError:
        pass

    return (conn, cur, table)


def set_(key, value, profile=None):
    if not profile:
        return False
    conn, cur, table = _connect(profile)
    value = buffer(msgpack.packb(value))
    conn.execute('INSERT OR REPLACE INTO {0} VALUES (?, ?)'.format(table),
                 (key, value))
    conn.commit()
    return True


def get(key, profile=None):
    if not profile:
        return None
    _, cur, table = _connect(profile)
    res = cur.execute('SELECT value FROM {0} WHERE key=?'.format(table),
                      (key,))
    res = res.fetchone()
    if not res:
        return None
    return msgpack.unpackb(res[0])
