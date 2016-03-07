# -*- coding: utf-8 -*-
'''
Return data to a postgresql server

:maintainer:    None
:maturity:      New
:depends:       psycopg2
:platform:      all

To enable this returner the minion will need the psycopg2 installed and
the following values configured in the minion or master config:

.. code-block:: yaml

    returner.postgres.host: 'salt'
    returner.postgres.user: 'salt'
    returner.postgres.passwd: 'salt'
    returner.postgres.db: 'salt'
    returner.postgres.port: 5432

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.returner.postgres.host: 'salt'
    alternative.returner.postgres.user: 'salt'
    alternative.returner.postgres.passwd: 'salt'
    alternative.returner.postgres.db: 'salt'
    alternative.returner.postgres.port: 5432

Running the following commands as the postgres user should create the database
correctly:

.. code-block:: sql

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

To use the postgres returner, append '--return postgres' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return postgres

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return postgres --return_config alternative
'''
from __future__ import absolute_import
# Let's not allow PyLint complain about string substitution
# pylint: disable=W1321,E1321

# Import python libs
import json

# Import Salt libs
import salt.utils.jid
import salt.returners

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


def _get_options(ret=None):
    '''
    Get the postgres options from salt.
    '''
    attrs = {'host': 'host',
             'user': 'user',
             'passwd': 'passwd',
             'db': 'db',
             'port': 'port'}

    _options = salt.returners.get_returner_options('returner.{0}'.format(__virtualname__),
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_conn(ret=None):
    '''
    Return a postgres connection.
    '''
    _options = _get_options(ret)

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
    '''
    Close the Postgres connection
    '''
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
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''INSERT INTO jids (jid, load) VALUES (%s, %s)'''

    cur.execute(sql, (jid, json.dumps(load)))
    _close_conn(conn)


def save_minions(jid, minions):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT load FROM jids WHERE jid = %s;'''

    cur.execute(sql, (jid,))
    data = cur.fetchone()
    if data:
        return json.loads(data[0])
    _close_conn(conn)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    conn = _get_conn(ret=None)
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
    conn = _get_conn(ret=None)
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
    conn = _get_conn(ret=None)
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
