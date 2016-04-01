# -*- coding: utf-8 -*-
'''
Retrieve Pillar data by doing a SQLite3 query

sqlite3 is included in the stdlib since python2.5.

This module is a concrete implementation of the sql_base ext_pillar for SQLite3.

:maturity: new
:platform: all

Configuring the sqlite3 ext_pillar
=====================================

Use the 'sqlite3' key under ext_pillar for configuration of queries.

SQLite3 database connection configuration requires the following values
configured in the master config:

Note, timeout is in seconds.

.. code-block:: yaml

    pillar.sqlite3.database: /var/lib/salt/pillar.db
    pillar.sqlite3.timeout: 5.0


Complete example
=====================================

.. code-block:: yaml

    pillar:
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
'''
from __future__ import absolute_import

# Import python libs
from contextlib import contextmanager
import logging
import sqlite3

# Import Salt libs
from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    return True


class SQLite3ExtPillar(SqlBaseExtPillar):
    '''
    This class receives and processes the database rows from SQLite3.
    '''
    @classmethod
    def _db_name(cls):
        return 'SQLite3'

    def _get_options(self):
        '''
        Returns options used for the SQLite3 connection.
        '''
        defaults = {'database': '/var/lib/salt/pillar.db',
                    'timeout': 5.0}
        _options = {}
        _opts = __opts__.get('pillar', {}).get('sqlite3', {})
        if 'database' not in _opts:
            _sqlite3_opts = __opts__.get('pillar', {}).get('master', {})\
                .get('pillar', {}).get('sqlite3')
            if _sqlite3_opts is not None:
                _opts = _sqlite3_opts
        for attr in defaults:
            if attr not in _opts:
                log.debug('Using default for SQLite3 pillar {0}'.format(attr))
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        '''
        Yield a SQLite3 cursor
        '''
        _options = self._get_options()
        conn = sqlite3.connect(_options.get('database'),
                               timeout=float(_options.get('timeout')))
        cursor = conn.cursor()
        try:
            yield cursor
        except sqlite3.Error as err:
            log.exception('Error in ext_pillar SQLite3: {0}'.format(err.args))
        finally:
            conn.close()


def ext_pillar(minion_id,
               pillar,
               *args,
               **kwargs):
    '''
    Execute queries against SQLite3, merge and return as a dict
    '''
    return SQLite3ExtPillar().fetch(minion_id, pillar, *args, **kwargs)
