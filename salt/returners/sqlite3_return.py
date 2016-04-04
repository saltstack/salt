# -*- coding: utf-8 -*-
'''
Insert minion return data into a sqlite3 database

:maintainer:    Mickey Malone <mickey.malone@gmail.com>
:maturity:      New
:depends:       None
:platform:      All

Sqlite3 is a serverless database that lives in a single file.
In order to use this returner the database file must exist,
have the appropriate schema defined, and be accessible to the
user whom the minion process is running as. This returner
requires the following values configured in the master or
minion config:

.. code-block:: yaml

    sqlite3.database: /usr/lib/salt/salt.db
    sqlite3.timeout: 5.0

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.sqlite3.database: /usr/lib/salt/salt.db
    alternative.sqlite3.timeout: 5.0

Use the commands to create the sqlite3 database and tables:

.. code-block:: sql

    sqlite3 /usr/lib/salt/salt.db << EOF
    --
    -- Table structure for table 'jids'
    --

    CREATE TABLE jids (
      jid TEXT PRIMARY KEY,
      load TEXT NOT NULL
      );

    --
    -- Table structure for table 'salt_returns'
    --

    CREATE TABLE salt_returns (
      fun TEXT KEY,
      jid TEXT KEY,
      id TEXT KEY,
      fun_args TEXT,
      date TEXT NOT NULL,
      full_ret TEXT NOT NULL,
      success TEXT NOT NULL
      );
    EOF

To use the sqlite returner, append '--return sqlite3' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return sqlite3

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return sqlite3 --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return sqlite3 --return_kwargs '{"db": "/var/lib/salt/another-salt.db"}'

'''
from __future__ import absolute_import

# Import python libs
import logging
import json
import datetime

# Import Salt libs
import salt.utils.jid
import salt.returners

# Better safe than sorry here. Even though sqlite3 is included in python
try:
    import sqlite3
    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'sqlite3'


def __virtual__():
    if not HAS_SQLITE3:
        return False
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the SQLite3 options from salt.
    '''
    attrs = {'database': 'database',
             'timeout': 'timeout'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_conn(ret=None):
    '''
    Return a sqlite3 database connection
    '''
    # Possible todo: support detect_types, isolation_level, check_same_thread,
    # factory, cached_statements. Do we really need to though?
    _options = _get_options(ret)
    database = _options.get('database')
    timeout = _options.get('timeout')

    if not database:
        raise Exception(
                'sqlite3 config option "sqlite3.database" is missing')
    if not timeout:
        raise Exception(
                'sqlite3 config option "sqlite3.timeout" is missing')
    log.debug('Connecting the sqlite3 database: {0} timeout: {1}'.format(
              database,
              timeout))
    conn = sqlite3.connect(database, timeout=float(timeout))
    return conn


def _close_conn(conn):
    '''
    Close the sqlite3 database connection
    '''
    log.debug('Closing the sqlite3 database connection')
    conn.commit()
    conn.close()


def returner(ret):
    '''
    Insert minion return data into the sqlite3 database
    '''
    log.debug('sqlite3 returner <returner> called with data: {0}'.format(ret))
    conn = _get_conn(ret)
    cur = conn.cursor()
    sql = '''INSERT INTO salt_returns
             (fun, jid, id, fun_args, date, full_ret, success)
             VALUES (:fun, :jid, :id, :fun_args, :date, :full_ret, :success)'''
    cur.execute(sql,
                {'fun': ret['fun'],
                 'jid': ret['jid'],
                 'id': ret['id'],
                 'fun_args': str(ret['fun_args']) if ret.get('fun_args') else None,
                 'date': str(datetime.datetime.now()),
                 'full_ret': json.dumps(ret['return']),
                 'success': ret.get('success', '')})
    _close_conn(conn)


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    log.debug('sqlite3 returner <save_load> called jid:{0} load:{1}'
              .format(jid, load))
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''INSERT INTO jids (jid, load) VALUES (:jid, :load)'''
    cur.execute(sql,
                {'jid': jid,
                 'load': json.dumps(load)})
    _close_conn(conn)


def get_load(jid):
    '''
    Return the load from a specified jid
    '''
    log.debug('sqlite3 returner <get_load> called jid: {0}'.format(jid))
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT load FROM jids WHERE jid = :jid'''
    cur.execute(sql,
                {'jid': jid})
    data = cur.fetchone()
    if data:
        return json.loads(data)
    _close_conn(conn)
    return {}


def get_jid(jid):
    '''
    Return the information returned from a specified jid
    '''
    log.debug('sqlite3 returner <get_jid> called jid: {0}'.format(jid))
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT id, full_ret FROM salt_returns WHERE jid = :jid'''
    cur.execute(sql,
                {'jid': jid})
    data = cur.fetchone()
    log.debug('query result: {0}'.format(data))
    ret = {}
    if data and len(data) > 1:
        ret = {str(data[0]): {u'return': json.loads(data[1])}}
        log.debug("ret: {0}".format(ret))
    _close_conn(conn)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    log.debug('sqlite3 returner <get_fun> called fun: {0}'.format(fun))
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT s.id, s.full_ret, s.jid
            FROM salt_returns s
            JOIN ( SELECT MAX(jid) AS jid FROM salt_returns GROUP BY fun, id) max
            ON s.jid = max.jid
            WHERE s.fun = :fun
            '''
    cur.execute(sql,
                {'fun': fun})
    data = cur.fetchall()
    ret = {}
    if data:
        # Pop the jid off the list since it is not
        # needed and I am trying to get a perfect
        # pylint score :-)
        data.pop()
        for minion, ret in data:
            ret[minion] = json.loads(ret)
    _close_conn(conn)
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    log.debug('sqlite3 returner <get_jids> called')
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT jid, load FROM jids'''
    cur.execute(sql)
    data = cur.fetchall()
    ret = {}
    for jid, load in data:
        ret[jid] = salt.utils.jid.format_jid_instance(jid, json.loads(load))
    _close_conn(conn)
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    log.debug('sqlite3 returner <get_minions> called')
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT DISTINCT id FROM salt_returns'''
    cur.execute(sql)
    data = cur.fetchall()
    ret = []
    for minion in data:
        ret.append(minion[0])
    _close_conn(conn)
    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
