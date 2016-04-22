# -*- coding: utf-8 -*-
'''
Return data to an ODBC compliant server.  This driver was
developed with Microsoft SQL Server in mind, but theoretically
could be used to return data to any compliant ODBC database
as long as there is a working ODBC driver for it on your
minion platform.

:maintainer:    C. R. Oldham (cr@saltstack.com)
:maturity:      New
:depends:       unixodbc, pyodbc, freetds (for SQL Server)
:platform:      all

To enable this returner the minion will need

On Linux:

    unixodbc (http://www.unixodbc.org)
    pyodbc (`pip install pyodbc`)
    The FreeTDS ODBC driver for SQL Server (http://www.freetds.org)
    or another compatible ODBC driver

On Windows:

    TBD

unixODBC and FreeTDS need to be configured via /etc/odbcinst.ini and
/etc/odbc.ini.

/etc/odbcinst.ini::

    [TDS]
    Description=TDS
    Driver=/usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so

(Note the above Driver line needs to point to the location of the FreeTDS
shared library.  This example is for Ubuntu 14.04.)

/etc/odbc.ini::

    [TS]
    Description = "Salt Returner"
    Driver=TDS
    Server = <your server ip or fqdn>
    Port = 1433
    Database = salt
    Trace = No

Also you need the following values configured in the minion or master config.
Configure as you see fit::

    returner.odbc.dsn: 'TS'
    returner.odbc.user: 'salt'
    returner.odbc.passwd: 'salt'

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.returner.odbc.dsn: 'TS'
    alternative.returner.odbc.user: 'salt'
    alternative.returner.odbc.passwd: 'salt'

Running the following commands against Microsoft SQL Server in the desired
database as the appropriate user should create the database tables
correctly.  Replace with equivalent SQL for other ODBC-compliant servers

.. code-block:: sql

    --
    -- Table structure for table 'jids'
    --

    if OBJECT_ID('dbo.jids', 'U') is not null
        DROP TABLE dbo.jids

    CREATE TABLE dbo.jids (
       jid   varchar(255) PRIMARY KEY,
       load  varchar(MAX) NOT NULL
     );

    --
    -- Table structure for table 'salt_returns'
    --
    IF OBJECT_ID('dbo.salt_returns', 'U') IS NOT NULL
        DROP TABLE dbo.salt_returns;

    CREATE TABLE dbo.salt_returns (
       added     datetime not null default (getdate()),
       fun       varchar(100) NOT NULL,
       jid       varchar(255) NOT NULL,
       retval    varchar(MAX) NOT NULL,
       id        varchar(255) NOT NULL,
       success   bit default(0) NOT NULL,
       full_ret  varchar(MAX)
     );

    CREATE INDEX salt_returns_added on dbo.salt_returns(added);
    CREATE INDEX salt_returns_id on dbo.salt_returns(id);
    CREATE INDEX salt_returns_jid on dbo.salt_returns(jid);
    CREATE INDEX salt_returns_fun on dbo.salt_returns(fun);

  To use this returner, append '--return odbc' to the salt command.

  .. code-block:: bash

    salt '*' status.diskusage --return odbc

  To use the alternative configuration, append '--return_config alternative' to the salt command.

  .. versionadded:: 2015.5.0

  .. code-block:: bash

    salt '*' test.ping --return odbc --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return odbc --return_kwargs '{"dsn": "dsn-name"}'

'''
from __future__ import absolute_import
# Let's not allow PyLint complain about string substitution
# pylint: disable=W1321,E1321

# Import python libs
import json

# Import Salt libs
import salt.utils.jid
import salt.returners

# FIXME We'll need to handle this differently for Windows.
# Import third party libs
try:
    import pyodbc
    #import psycopg2.extras
    HAS_ODBC = True
except ImportError:
    HAS_ODBC = False

# Define the module's virtual name
__virtualname__ = 'odbc'


def __virtual__():
    if not HAS_ODBC:
        return False
    return True


def _get_options(ret=None):
    '''
    Get the odbc options from salt.
    '''
    attrs = {'dsn': 'dsn',
             'user': 'user',
             'passwd': 'passwd'}

    _options = salt.returners.get_returner_options('returner.{0}'.format(__virtualname__),
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_conn(ret=None):
    '''
    Return a MSSQL connection.
    '''
    _options = _get_options(ret)
    dsn = _options.get('dsn')
    user = _options.get('user')
    passwd = _options.get('passwd')

    return pyodbc.connect('DSN={0};UID={1};PWD={2}'.format(
            dsn,
            user,
            passwd))


def _close_conn(conn):
    '''
    Close the MySQL connection
    '''
    conn.commit()
    conn.close()


def returner(ret):
    '''
    Return data to an odbc server
    '''
    conn = _get_conn(ret)
    cur = conn.cursor()
    sql = '''INSERT INTO salt_returns
            (fun, jid, retval, id, success, full_ret)
            VALUES (?, ?, ?, ?, ?, ?)'''
    cur.execute(
        sql, (
            ret['fun'],
            ret['jid'],
            json.dumps(ret['return']),
            ret['id'],
            ret['success'],
            json.dumps(ret)
        )
    )
    _close_conn(conn)


def save_load(jid, load):
    '''
    Save the load to the specified jid id
    '''
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''INSERT INTO jids (jid, load) VALUES (?, ?)'''

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
    sql = '''SELECT load FROM jids WHERE jid = ?;'''

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
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT id, full_ret FROM salt_returns WHERE jid = ?'''

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
            WHERE s.fun = ?
            '''

    cur.execute(sql, (fun,))
    data = cur.fetchall()

    ret = {}
    if data:
        for minion, _, retval in data:
            ret[minion] = json.loads(retval)
    _close_conn(conn)
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    conn = _get_conn(ret=None)
    cur = conn.cursor()
    sql = '''SELECT distinct jid, load FROM jids'''

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
