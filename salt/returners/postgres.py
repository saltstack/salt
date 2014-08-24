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

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.returner.postgres.host: 'salt'
    alternative.returner.postgres.user: 'salt'
    alternative.returner.postgres.passwd: 'salt'
    alternative.returner.postgres.db: 'salt'
    alternative.returner.postgres.port: 5432

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
      jid   bigint PRIMARY KEY,
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

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return postgres --return_config alternative
'''
# Let's not allow PyLint complain about string substitution
# pylint: disable=W1321,E1321

# Import python libs
import json

# Import third party libs
try:
    import psycopg2
    #import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

__virtualname__ = 'postgres'


def __virtual__():
    if not HAS_POSTGRES:
        return False
    return __virtualname__


def _get_options(ret):
    '''
    Get the odbc options from salt.
    '''
    ret_config = '{0}'.format(ret['ret_config']) if 'ret_config' in ret else ''

    attrs = {'host': 'host',
             'user': 'user',
             'passwd': 'passwd',
             'db': 'db',
             'port': 'port'}

    _options = {}
    for attr in attrs:
        if 'config.option' in __salt__:
            cfg = __salt__['config.option']
            c_cfg = cfg('returner.{0}'.format(__virtualname__), {})
            if ret_config:
                ret_cfg = cfg('{0}.returner.{1}'.format(ret_config, __virtualname__), {})
                if ret_cfg.get(attrs[attr], cfg('{0}.returner.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg('{0}.returner.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg('returner.{0}.{1}'.format(__virtualname__, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg('returner.{0}.{1}'.format(__virtualname__, attrs[attr])))
        else:
            cfg = __opts__
            c_cfg = cfg.get('returner.{0}'.format(__virtualname__), {})
            if ret_config:
                ret_cfg = cfg.get('{0}.returner.{1}'.format(ret_config, __virtualname__), {})
                if ret_cfg.get(attrs[attr], cfg.get('{0}.returner.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg.get('{0}.returner.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg.get('returner.{0}.{1}'.format(__virtualname__, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg.get('returner.{0}.{1}'.format(__virtualname__, attrs[attr])))
        if not _attr:
            _options[attr] = None
            continue
        _options[attr] = _attr
    return _options


def _get_conn(ret):
    '''
    Return a postgres connection.
    '''
    _options = _get_options()

    host = _options.get('host')
    user = _options.get('user')
    passwd = _options.get('passwd')
    db = _options.get('db')
    port = _options.get('port')

    return psycopg2.connect(
            host=host,
            user=user,
            password=passwd,
            database=db,
            port=port)


def _close_conn(conn):
    conn.commit()
    conn.close()


def returner(ret):
    '''
    Return data to a postgres server
    '''
    conn = _get_conn(ret)
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
        for minion, jid, full_ret in data:
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
