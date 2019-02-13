# -*- coding: utf-8 -*-
'''
Oracle DataBase connection module

:maintainer: Vladimir Bormotov <bormotov@gmail.com>

:maturity: new

:depends: cx_Oracle

:platform: all

:configuration: module provide connections for multiple Oracle DB instances.

    **OS Environment**

    .. code-block:: yaml

        ORACLE_HOME: path to oracle product
        PATH: path to Oracle Client libs need to be in PATH

    **pillar**

    .. code-block:: yaml

        oracle:
          dbs:
            <db>:
              uri: connection credentials in format:
            user/password@host[:port]/sid[ servicename as {sysdba|sysoper}]
              or
            sid[ as {sysdba|sysoper}]
             (ORACLE_HOME is parsed from oratab)
            optional keyword servicename will determine whether it is a sid or service_name
            <db>:
              uri: .....
'''
from __future__ import absolute_import, print_function, unicode_literals

import os
import logging
from salt.utils.decorators import depends
from salt.utils.files import fopen
from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)

try:
    import cx_Oracle
    MODE = {
        'sysdba': cx_Oracle.SYSDBA,
        'sysoper': cx_Oracle.SYSOPER
    }
    HAS_CX_ORACLE = True
except ImportError:
    MODE = {'sysdba': 2, 'sysoper': 4}
    HAS_CX_ORACLE = False

__virtualname__ = 'oracle'


def __virtual__():
    '''
    Load module only if cx_Oracle installed
    '''
    if HAS_CX_ORACLE:
        return __virtualname__
    return (False, 'The oracle execution module not loaded: '
            'python oracle library not found.')


def _cx_oracle_req():
    '''
    Fallback function stub
    '''
    return 'Need "cx_Oracle" and Oracle Client installed for this function exist'


def _unicode_output(cursor, name, default_type, size, precision, scale):
    '''
    Return strings values as python unicode string

    http://www.oracle.com/technetwork/articles/dsl/tuininga-cx-oracle-084866.html
    '''
    if default_type in (cx_Oracle.STRING, cx_Oracle.LONG_STRING,
                        cx_Oracle.FIXED_CHAR, cx_Oracle.CLOB):
        return cursor.var(six.text_type, size, cursor.arraysize)


def _connect(uri):
    '''
    uri = user/password@host[:port]/sid[servicename as {sysdba|sysoper}]
     or
    uri = sid[ as {sysdba|sysoper}]
     (this syntax only makes sense on non-Windows minions, ORAHOME is taken from oratab)

    Return cx_Oracle.Connection instance
    '''
    # cx_Oracle.Connection() does not support 'as sysdba' syntax
    uri_l = uri.rsplit(' as ', 1)
    if len(uri_l) == 2:
        credentials, mode = uri_l
        mode = MODE[mode]
    else:
        credentials = uri_l[0]
        mode = 0
    # force UTF-8 client encoding
    os.environ['NLS_LANG'] = '.AL32UTF8'
    if '@' in uri:
        serv_name = False
        userpass, hostportsid = credentials.split('@')
        user, password = userpass.split('/')
        hostport, sid = hostportsid.split('/')
        if 'servicename' in sid:
            serv_name = True
            sid = sid.split('servicename')[0].strip()
        hostport_l = hostport.split(':')
        if len(hostport_l) == 2:
            host, port = hostport_l
        else:
            host = hostport_l[0]
            port = 1521
        log.debug('connect: %s', (user, password, host, port, sid, mode))
        if serv_name:
            conn = cx_Oracle.connect(user, password, cx_Oracle.makedsn(host, port, service_name=sid), mode)
        else:
            conn = cx_Oracle.connect(user, password, cx_Oracle.makedsn(host, port, sid), mode)
    else:
        sid = uri.rsplit(' as ', 1)[0]
        orahome = _parse_oratab(sid)
        if orahome:
            os.environ['ORACLE_HOME'] = orahome
        else:
            raise CommandExecutionError('No uri defined and SID {0} not found in oratab'.format(sid))
        os.environ['ORACLE_SID'] = sid
        log.debug('connect: %s', (sid, mode))
        conn = cx_Oracle.connect(mode=MODE['sysdba'])
    conn.outputtypehandler = _unicode_output
    return conn


def _parse_oratab(sid):
    '''
    Return ORACLE_HOME for a given SID found in oratab

    Note: only works with Unix-like minions
    '''
    if __grains__.get('kernel') in ('Linux', 'AIX', 'FreeBSD', 'OpenBSD', 'NetBSD'):
        ORATAB = '/etc/oratab'
    elif __grains__.get('kernel') in 'SunOS':
        ORATAB = '/var/opt/oracle/oratab'
    else:
        # Windows has no oratab file
        raise CommandExecutionError(
            'No uri defined for {0} and oratab not available in this OS'.format(sid))
    with fopen(ORATAB, 'r') as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.startswith('#'):
                continue
            if sid in line.split(':')[0]:
                return line.split(':')[1]
    return None


@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def run_query(db, query):
    '''
    Run SQL query and return result

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.run_query my_db "select * from my_table"
    '''
    if db in [x.keys()[0] for x in show_dbs()]:
        conn = _connect(show_dbs(db)[db]['uri'])
    else:
        log.debug('No uri found in pillars - will try to use oratab')
        # if db does not have uri defined in pillars
        # or it's not defined in pillars at all parse oratab file
        conn = _connect(uri=db)
    return conn.cursor().execute(query).fetchall()


def show_dbs(*dbs):
    '''
    Show databases configuration from pillar. Filter by `*args`

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.show_dbs
        salt '*' oracle.show_dbs my_db
    '''
    if dbs:
        log.debug('get db versions for: %s', dbs)
        result = {}
        for db in dbs:
            result[db] = __salt__['pillar.get']('oracle:dbs:' + db)
        return result
    else:
        pillar_dbs = __salt__['pillar.get']('oracle:dbs')
        log.debug('get all (%s) dbs versions', len(pillar_dbs))
        return pillar_dbs


@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def version(*dbs):
    '''
    Server Version (select banner  from v$version)

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.version
        salt '*' oracle.version my_db
    '''
    pillar_dbs = __salt__['pillar.get']('oracle:dbs')
    get_version = lambda x: [
        r[0] for r in run_query(x, "select banner from v$version order by banner")
        ]
    result = {}
    if dbs:
        log.debug('get db versions for: %s', dbs)
        for db in dbs:
            if db in pillar_dbs:
                result[db] = get_version(db)
    else:
        log.debug('get all(%s) dbs versions', len(dbs))
        for db in dbs:
            result[db] = get_version(db)
    return result


@depends('cx_Oracle', fallback_function=_cx_oracle_req)
def client_version():
    '''
    Oracle Client Version

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.client_version
    '''
    return '.'.join((six.text_type(x) for x in cx_Oracle.clientversion()))


def show_pillar(item=None):
    '''
    Show Pillar segment oracle.* and subitem with notation "item:subitem"

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.show_pillar
        salt '*' oracle.show_pillar dbs:my_db
    '''
    if item:
        return __salt__['pillar.get']('oracle:' + item)
    else:
        return __salt__['pillar.get']('oracle')


def show_env():
    '''
    Show Environment used by Oracle Client

    CLI Example:

    .. code-block:: bash

        salt '*' oracle.show_env

    .. note::
        at first _connect() ``NLS_LANG`` will forced to '.AL32UTF8'
    '''
    envs = ['PATH', 'ORACLE_HOME', 'TNS_ADMIN', 'NLS_LANG']
    result = {}
    for env in envs:
        if env in os.environ:
            result[env] = os.environ[env]
    return result
