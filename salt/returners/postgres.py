# -*- coding: utf-8 -*-
'''
Return data to a postgresql server

:maintainer:    None
:maturity:      New
:depends:       psycopg2
:platform:      all

To enable this returner the minion will need the psycopg2 installed and
the following values configured in the minion or master config::

    returner.postgres.host: 'salt'
    returner.postgres.user: 'salt'
    returner.postgres.passwd: 'salt'
    returner.postgres.db: 'salt'
    returner.postgres.port: 5432

Running the following commands as the postgres user should create the database
correctly::

    psql << EOF
    CREATE ROLE salt WITH PASSWORD 'salt';
    CREATE DATABASE salt WITH OWNER salt;
    EOF

    psql -h localhost -U salt << EOF
    --
    -- Table structure for table 'jids'
    --

    DROP TABLE IF EXISTS jids;
    CREATE TABLE jids (
      jid   varchar(20) PRIMARY KEY,
      load  text NOT NULL
    );

    --
    -- Table structure for table 'salt_returns'
    --

    DROP TABLE IF EXISTS salt_returns;
    CREATE TABLE salt_returns (
      added     TIMESTAMP WITH TIME ZONE DEFAULT now(),
      fun       text NOT NULL,
      jid       varchar(20) NOT NULL,
      return    text NOT NULL,
      id        text NOT NULL,
      success   boolean
    );
    CREATE INDEX ON salt_returns (added);
    CREATE INDEX ON salt_returns (id);
    CREATE INDEX ON salt_returns (jid);
    CREATE INDEX ON salt_returns (fun);
    EOF

Required python modules: psycopg2

  To use the postgres returner, append '--return postgres' to the salt command. ex:

    salt '*' test.ping --return postgres
'''
# Let's not allow PyLint complain about string substitution
# pylint: disable=W1321,E1321

# Import python libs
import json

# Import Salt libs
import salt.utils

# Import third party libs
try:
    import psycopg2
    #import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


def __virtual__():
    if not HAS_POSTGRES:
        return False
    return 'postgres'


def _get_conn():
    '''
    Return a postgres connection.
    '''
    if 'config.option' in __salt__:
        return psycopg2.connect(
                host=__salt__['config.option']('returner.postgres.host'),
                user=__salt__['config.option']('returner.postgres.user'),
                password=__salt__['config.option']('returner.postgres.passwd'),
                database=__salt__['config.option']('returner.postgres.db'),
                port=__salt__['config.option']('returner.postgres.port'))
    else:
        cfg = __opts__
        return psycopg2.connect(
                host=cfg.get('returner.postgres.host', None),
                user=cfg.get('returner.postgres.user', None),
                password=cfg.get('returner.postgres.passwd', None),
                database=cfg.get('returner.postgres.db', None),
                port=cfg.get('returner.postgres.port', None))


def _close_conn(conn):
    '''
    Close the Postgres connection
    '''
    conn.commit()
    conn.close()


def returner(ret):
    '''
    Return data to a postgres server
    '''
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''INSERT INTO salt_returns
            (fun, jid, return, id, success)
            VALUES (%s, %s, %s, %s, %s)'''
    cur.execute(
        sql, (
            ret['fun'],
            ret['jid'],
            json.dumps(ret['return']),
            ret['id'],
            ret['success']
        )
    )
    _close_conn(conn)


def save_load(jid, load):
    '''
    Save the load to the specified jid id
    '''
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''INSERT INTO jids (jid, load) VALUES (%s, %s)'''

    cur.execute(sql, (jid, json.dumps(load)))
    _close_conn(conn)


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''SELECT load FROM jids WHERE jid = %s;'''

    cur.execute(sql, (jid,))
    data = cur.fetchone()
    if data:
        return json.loads(data)
    _close_conn(conn)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''SELECT id, full_ret FROM salt_returns WHERE jid = %s'''

    cur.execute(sql, (jid,))
    data = cur.fetchall()
    ret = {}
    if data:
        for minion, full_ret in data:
            ret[minion] = json.loads(full_ret)
    _close_conn(conn)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    conn = _get_conn()
    cur = conn.cursor()
    sql = '''SELECT s.id,s.jid, s.full_ret
            FROM salt_returns s
            JOIN ( SELECT MAX(jid) AS jid FROM salt_returns GROUP BY fun, id) max
            ON s.jid = max.jid
            WHERE s.fun = %s
            '''

    cur.execute(sql, (fun,))
    data = cur.fetchall()

    ret = {}
    if data:
        for minion, _, full_ret in data:
            ret[minion] = json.loads(full_ret)
    _close_conn(conn)
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
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


def prep_jid(nocache, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.gen_jid()
