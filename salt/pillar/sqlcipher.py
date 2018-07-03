# -*- coding: utf-8 -*-
'''
Retrieve Pillar data by running a SQLCipher query

.. versionadded:: 2016.3.0

Python SQLCipher support is provided by the pysqlcipher
Python package. You need this module installed to query
Pillar data from a SQLCipher database.

This module is a concrete implementation of the sql_base
ext_pillar for SQLCipher.

:maturity: new
:depends: pysqlcipher (for py2) or pysqlcipher3 (for py3)
:platform: all

Configuring the sqlcipher ext_pillar
====================================

Use the 'sqlcipher' key under ext_pillar for configuration of queries.

SQLCipher database connection configuration requires the following values
configured in the master config:

   * ``sqlcipher.database`` - The SQLCipher database to connect to.
     Defaults to ``'/var/lib/salt/pillar-sqlcipher.db'``.
   * ``sqlcipher.pass`` - The SQLCipher database decryption password.
   * ``sqlcipher.timeout`` - The connection timeout in seconds.

Example configuration

.. code-block:: yaml

    sqlcipher:
      database: /var/lib/salt/pillar-sqlcipher.db
      pass: strong_pass_phrase
      timeout: 5.0

Complete example
=================

.. code-block:: yaml

    sqlcipher:
      database: '/var/lib/salt/pillar-sqlcipher.db'
      pass: strong_pass_phrase
      timeout: 5.0

    ext_pillar:
      - sqlcipher:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE ?'
            depth: 5
            as_list: True
            with_lists: [1,3]
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
from contextlib import contextmanager
import logging

# Import Salt libs
from salt.pillar.sql_base import SqlBaseExtPillar

# Set up logging
log = logging.getLogger(__name__)

# Import third party libs
try:
    from pysqlcipher import dbapi2 as sqlcipher
    HAS_SQLCIPHER = True
except ImportError:
    HAS_SQLCIPHER = False


def __virtual__():
    if not HAS_SQLCIPHER:
        return False
    return True


class SQLCipherExtPillar(SqlBaseExtPillar):
    '''
    This class receives and processes the database rows from SQLCipher.
    '''
    @classmethod
    def _db_name(cls):
        return 'SQLCipher'

    def _get_options(self):
        '''
        Returns options used for the SQLCipher connection.
        '''
        defaults = {'database': '/var/lib/salt/pillar-sqlcipher.db',
                    'pass': 'strong_pass_phrase',
                    'timeout': 5.0}
        _options = {}
        _opts = __opts__.get('sqlcipher', {})

        for attr in defaults:
            if attr not in _opts:
                log.debug('Using default for SQLCipher pillar %s', attr)
                _options[attr] = defaults[attr]
                continue
            _options[attr] = _opts[attr]
        return _options

    @contextmanager
    def _get_cursor(self):
        '''
        Yield a SQLCipher cursor
        '''
        _options = self._get_options()
        conn = sqlcipher.connect(_options.get('database'),
                                 timeout=float(_options.get('timeout')))
        conn.execute('pragma key="{0}"'.format(_options.get('pass')))
        cursor = conn.cursor()
        try:
            yield cursor
        except sqlcipher.Error as err:
            log.exception('Error in ext_pillar SQLCipher: %s', err.args)
        finally:
            conn.close()


def ext_pillar(minion_id,
               pillar,
               *args,
               **kwargs):
    '''
    Execute queries against SQLCipher, merge and return as a dict
    '''
    return SQLCipherExtPillar().fetch(minion_id, pillar, *args, **kwargs)
