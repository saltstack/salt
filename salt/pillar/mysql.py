# -*- coding: utf-8 -*-
'''
Retrieve Pillar data by doing a MySQL query

MariaDB provides Python support through the MySQL Python package.
Therefore, you may use this module with both MySQL or MariaDB.

This module is a concrete implementation of the sql_base ext_pillar for MySQL.

:maturity: new
:depends: python-mysqldb
:platform: all

Legacy compatibility
=====================================

This module has an extra addition for backward compatibility.

If there's a keyword arg of mysql_query, that'll go first before other args.
This legacy compatibility translates to depth 1.

We do this so that it's backward compatible with older configs.
This is deprecated and slated to be removed in Carbon.

Configuring the mysql ext_pillar
=====================================

Use the 'mysql' key under ext_pillar for configuration of queries.

MySQL configuration of the MySQL returner is being used (mysql.db, mysql.user,
mysql.pass, mysql.port, mysql.host) for database connection info.

Required python modules: MySQLdb

Complete example
=====================================

.. code-block:: yaml

    mysql:
      user: 'salt'
      pass: 'super_secret_password'
      db: 'salt_db'

    ext_pillar:
      - mysql:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE %s'
            depth: 5
            as_list: True
            with_lists: [1,3]
'''
from __future__ import absolute_import

# Import python libs
from contextlib import contextmanager
import logging

# Import Salt libs
from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)

# Import third party libs
try:
    import MySQLdb
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


def __virtual__():
    if not HAS_MYSQL:
        return False
    return True


class MySQLExtPillar(SqlBaseExtPillar):
    '''
    This class receives and processes the database rows from MySQL.
    '''
    @classmethod
    def _db_name(cls):
        return 'MySQL'

    def _get_options(self):
        '''
        Returns options used for the MySQL connection.
        '''
        defaults = {'host': 'localhost',
                    'user': 'salt',
                    'pass': 'salt',
                    'db': 'salt',
                    'port': 3306}
        _options = {}
        _opts = __opts__.get('mysql', {})
        for attr in defaults:
            if attr not in _opts:
                log.debug('Using default for MySQL {0}'.format(attr))
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        '''
        Yield a MySQL cursor
        '''
        _options = self._get_options()
        conn = MySQLdb.connect(host=_options['host'],
                               user=_options['user'],
                               passwd=_options['pass'],
                               db=_options['db'], port=_options['port'])
        cursor = conn.cursor()
        try:
            yield cursor
        except MySQLdb.DatabaseError as err:
            log.exception('Error in ext_pillar MySQL: {0}'.format(err.args))
        finally:
            conn.close()

    def extract_queries(self, args, kwargs):
        '''
            This function normalizes the config block into a set of queries we
            can use.  The return is a list of consistently laid out dicts.
        '''
        return super(MySQLExtPillar, self).extract_queries(args, kwargs)


def ext_pillar(minion_id,
               pillar,
               *args,
               **kwargs):
    '''
    Execute queries against MySQL, merge and return as a dict
    '''
    return MySQLExtPillar().fetch(minion_id, pillar, *args, **kwargs)
