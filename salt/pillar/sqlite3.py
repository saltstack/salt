"""
Retrieve Pillar data by doing a SQLite3 query

.. versionadded:: 2015.8.0

``sqlite3`` is included in the stdlib since Python 2.5.

This module is a concrete implementation of the sql_base ext_pillar for
SQLite3.

:platform: all

Configuring the sqlite3 ext_pillar
==================================

Use the 'sqlite3' key under ext_pillar for configuration of queries.

SQLite3 database connection configuration requires the following values
configured in the master config:

Note, timeout is in seconds.

.. code-block:: yaml

    sqlite3.database: /var/lib/salt/pillar.db
    sqlite3.timeout: 5.0


Complete Example
================

.. code-block:: yaml

    sqlite3:
      database: '/var/lib/salt/pillar.db'
      timeout: 5.0

    ext_pillar:
      - sqlite3:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE ?'
            depth: 5
            as_list: True
            with_lists: [1,3]
"""

import logging
import sqlite3
from contextlib import contextmanager

from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    return True


class SQLite3ExtPillar(SqlBaseExtPillar):
    """
    This class receives and processes the database rows from SQLite3.
    """

    @classmethod
    def _db_name(cls):
        return "SQLite3"

    def _get_options(self):
        """
        Returns options used for the SQLite3 connection.
        """
        defaults = {"database": "/var/lib/salt/pillar.db", "timeout": 5.0}
        _options = {}
        _opts = {}
        if "sqlite3" in __opts__ and "database" in __opts__["sqlite3"]:
            _opts = __opts__.get("sqlite3", {})
        for attr in defaults:
            if attr not in _opts:
                log.debug("Using default for SQLite3 pillar %s", attr)
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        """
        Yield a SQLite3 cursor
        """
        _options = self._get_options()
        conn = sqlite3.connect(
            _options.get("database"), timeout=float(_options.get("timeout"))
        )
        cursor = conn.cursor()
        try:
            yield cursor
        except sqlite3.Error as err:
            log.exception("Error in ext_pillar SQLite3: %s", err.args)
        finally:
            conn.close()


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """
    Execute queries against SQLite3, merge and return as a dict
    """
    return SQLite3ExtPillar().fetch(minion_id, pillar, *args, **kwargs)
