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
minion config::

    returner.sqlite3.database: /usr/lib/salt/salt.db
    returner.sqlite3.timeout: 5.0

Use the commands to create the sqlite3 database and tables::

    sqlite3 /usr/lib/salt/salt.db << EOF
    --
    -- Table structure for table 'jids'
    --

    CREATE TABLE jids (
      jid integer PRIMARY KEY,
      load TEXT NOT NULL
      );

    --
    -- Table structure for table 'salt_returns'
    --

    CREATE TABLE salt_returns (
      fun TEXT KEY,
      jid TEXT KEY,
      id TEXT KEY,
      date TEXT NOT NULL,
      full_ret TEXT NOT NULL,
      success TEXT NOT NULL
      );
    EOF
'''

# Import python libs
import logging
import json
import datetime

# Better safe than sorry here. Even though sqlite3 is included in python
try:
    import sqlite3
    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_SQLITE3:
        return False
    return 'sqlite3'


def _get_conn():
    '''
    Return a sqlite3 database connection
    '''
    # Possible todo: support detect_types, isolation_level, check_same_thread,
    # factory, cached_statements. Do we really need to though?
    if not __salt__['config.option']('returner.sqlite3.database'):
        raise Exception(
                'sqlite3 config option "returner.sqlite3.database" is missing')
    if not __salt__['config.option']('returner.sqlite3.timeout'):
        raise Exception(
                'sqlite3 config option "returner.sqlite3.timeout" is missing')
    log.debug('Connecting the sqlite3 database: {0} timeout: {1}'.format(
              __salt__['config.option']('returner.sqlite3.database'),
              __salt__['config.option']('returner.sqlite3.timeout')))
    conn = sqlite3.connect(
                  __salt__['config.option']('returner.sqlite3.database'),
        timeout=float(__salt__['config.option']('returner.sqlite3.timeout')))
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
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''INSERT INTO salt_returns
             (fun, jid, id, date, full_ret, success)
             VALUES (:fun, :jid, :id, :date, :full_ret, :success)'''
    cur.execute(sql,
                {'fun': ret['fun'],
                 'jid': ret['jid'],
                 'id': ret['id'],
                 'date': str(datetime.datetime.now()),
                 'full_ret': json.dumps(ret['return']),
                 'success': ret['success']})
    _close_conn(conn)


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    log.debug('sqlite3 returner <save_load> called jid:{0} load:{1}'
              .format(jid, load))
    conn = _get_conn()
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
    conn = _get_conn()
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
    conn = _get_conn()
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
    conn = _get_conn()
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
    log.debug('sqlite3 returner <get_fun> called')
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''SELECT jid FROM jids'''
    cur.execute(sql)
    data = cur.fetchall()
    ret = []
    for jid in data:
        ret.append(jid[0])
    _close_conn(conn)
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    log.debug('sqlite3 returner <get_minions> called')
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''SELECT DISTINCT id FROM salt_returns'''
    cur.execute(sql)
    data = cur.fetchall()
    ret = []
    for minion in data:
        ret.append(minion[0])
    _close_conn(conn)
    return ret
