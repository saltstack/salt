"""
Retrieve Pillar data by doing a MySQL query

MariaDB provides Python support through the MySQL Python package.
Therefore, you may use this module with both MySQL or MariaDB.

This module is a concrete implementation of the sql_base ext_pillar for MySQL.

:maturity: new
:depends: python-mysqldb
:platform: all

Configuring the mysql ext_pillar
================================

Use the 'mysql' key under ext_pillar for configuration of queries.

MySQL configuration of the MySQL returner is being used (mysql.db, mysql.user,
mysql.pass, mysql.port, mysql.host) for database connection info.

Required python modules: MySQLdb

Complete example
================

.. code-block:: yaml

    mysql:
      user: 'salt'
      pass: 'super_secret_password'
      db: 'salt_db'
      port: 3306
      ssl:
        cert: /etc/mysql/client-cert.pem
        key: /etc/mysql/client-key.pem

    ext_pillar:
      - mysql:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE %s'
            depth: 5
            as_list: True
            with_lists: [1,3]
"""

import logging
from contextlib import contextmanager

from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.converters
    import MySQLdb.cursors
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.converters
        import MySQLdb.cursors
    except ImportError:
        MySQLdb = None


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


class MySQLExtPillar(SqlBaseExtPillar):
    """
    This class receives and processes the database rows from MySQL.
    """

    @classmethod
    def _db_name(cls):
        return "MySQL"

    def _get_options(self):
        """
        Returns options used for the MySQL connection.
        """
        defaults = {
            "host": "localhost",
            "user": "salt",
            "pass": "salt",
            "db": "salt",
            "port": 3306,
            "ssl": {},
        }
        _options = {}
        _opts = __opts__.get("mysql", {})
        for attr in defaults:
            if attr not in _opts:
                log.debug("Using default for MySQL %s", attr)
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        """
        Yield a MySQL cursor
        """
        _options = self._get_options()
        conn = MySQLdb.connect(
            host=_options["host"],
            user=_options["user"],
            passwd=_options["pass"],
            db=_options["db"],
            port=_options["port"],
            ssl=_options["ssl"],
        )
        cursor = conn.cursor()
        try:
            yield cursor
        except MySQLdb.DatabaseError as err:
            log.exception("Error in ext_pillar MySQL: %s", err.args)
        finally:
            conn.close()

    def extract_queries(self, args, kwargs):  # pylint: disable=useless-super-delegation
        """
        This function normalizes the config block into a set of queries we
        can use.  The return is a list of consistently laid out dicts.
        """
        return super().extract_queries(args, kwargs)


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """
    Execute queries against MySQL, merge and return as a dict
    """
    return MySQLExtPillar().fetch(minion_id, pillar, *args, **kwargs)
