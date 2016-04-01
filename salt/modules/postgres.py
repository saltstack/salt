# -*- coding: utf-8 -*-
'''
Module to provide Postgres compatibility to salt.

:configuration: In order to connect to Postgres, certain configuration is
    required in /etc/salt/minion on the relevant minions. Some sample configs
    might look like::

        postgres.host: 'localhost'
        postgres.port: '5432'
        postgres.user: 'postgres' -> db user
        postgres.pass: ''
        postgres.maintenance_db: 'postgres'

    The default for the maintenance_db is 'postgres' and in most cases it can
    be left at the default setting.
    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar

:note: This module uses MD5 hashing which may not be compliant with certain
    security audits.
'''

# This pylint error is popping up where there are no colons?
# pylint: disable=E8203

# Import python libs
from __future__ import absolute_import
import datetime
import distutils.version  # pylint: disable=import-error,no-name-in-module
import logging
import hashlib
import os
import tempfile
try:
    import pipes
    import csv
    HAS_ALL_IMPORTS = True
except ImportError:
    HAS_ALL_IMPORTS = False

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves import StringIO


log = logging.getLogger(__name__)


_DEFAULT_PASSWORDS_ENCRYPTION = True
_EXTENSION_NOT_INSTALLED = 'EXTENSION NOT INSTALLED'
_EXTENSION_INSTALLED = 'EXTENSION INSTALLED'
_EXTENSION_TO_UPGRADE = 'EXTENSION TO UPGRADE'
_EXTENSION_TO_MOVE = 'EXTENSION TO MOVE'
_EXTENSION_FLAGS = (
    _EXTENSION_NOT_INSTALLED,
    _EXTENSION_INSTALLED,
    _EXTENSION_TO_UPGRADE,
    _EXTENSION_TO_MOVE,
)


def __virtual__():
    '''
    Only load this module if the psql bin exists
    '''
    if all((salt.utils.which('psql'), HAS_ALL_IMPORTS)):
        return True
    return False


def _run_psql(cmd, runas=None, password=None, host=None, port=None, user=None):
    '''
    Helper function to call psql, because the password requirement
    makes this too much code to be repeated in each function below
    '''
    kwargs = {
        'reset_system_locale': False,
        'clean_env': True,
    }
    if runas is None:
        if not host:
            host = __salt__['config.option']('postgres.host')
        if not host or host.startswith('/'):
            if 'FreeBSD' in __grains__['os_family']:
                runas = 'pgsql'
            if 'OpenBSD' in __grains__['os_family']:
                runas = '_postgresql'
            else:
                runas = 'postgres'

    if user is None:
        user = runas

    if runas:
        kwargs['runas'] = runas

    if password is None:
        password = __salt__['config.option']('postgres.pass')
    if password is not None:
        pgpassfile = salt.utils.mkstemp(text=True)
        with salt.utils.fopen(pgpassfile, 'w') as fp_:
            fp_.write('{0}:{1}:*:{2}:{3}'.format(
                'localhost' if not host or host.startswith('/') else host,
                port if port else '*',
                user if user else '*',
                password,
            ))
            __salt__['file.chown'](pgpassfile, runas, '')
            kwargs['env'] = {'PGPASSFILE': pgpassfile}

    ret = __salt__['cmd.run_all'](cmd, python_shell=False, **kwargs)

    if ret.get('retcode', 0) != 0:
        log.error('Error connecting to Postgresql server')
    if password is not None and not __salt__['file.remove'](pgpassfile):
        log.warning('Remove PGPASSFILE failed')

    return ret


def version(user=None, host=None, port=None, maintenance_db=None,
            password=None, runas=None):
    '''
    Return the version of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.version
    '''
    query = 'SELECT setting FROM pg_catalog.pg_settings ' \
            'WHERE name = \'server_version\''
    cmd = _psql_cmd('-c', query,
                    '-t',
                    host=host,
                    user=user,
                    port=port,
                    maintenance_db=maintenance_db,
                    password=password)
    ret = _run_psql(
        cmd, runas=runas, password=password, host=host, port=port, user=user)

    for line in ret['stdout'].splitlines():
        return line


def _parsed_version(user=None, host=None, port=None, maintenance_db=None,
                    password=None, runas=None):
    '''
    Returns the server version properly parsed and int casted for internal use.

    If the Postgres server does not respond, None will be returned.
    '''

    psql_version = version(
        user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas,
    )

    if psql_version:
        return distutils.version.LooseVersion(psql_version)
    else:
        log.warning('Attempt to parse version of Postgres server failed. '
                    'Is the server responding?')
        return None


def _connection_defaults(user=None, host=None, port=None, maintenance_db=None,
                         password=None):
    '''
    Returns a tuple of (user, host, port, db) with config, pillar, or default
    values assigned to missing values.
    '''
    if not user:
        user = __salt__['config.option']('postgres.user')
    if not host:
        host = __salt__['config.option']('postgres.host')
    if not port:
        port = __salt__['config.option']('postgres.port')
    if not maintenance_db:
        maintenance_db = __salt__['config.option']('postgres.maintenance_db')
    if password is None:
        password = __salt__['config.option']('postgres.pass')

    return (user, host, port, maintenance_db, password)


def _psql_cmd(*args, **kwargs):
    '''
    Return string with fully composed psql command.

    Accept optional keyword arguments: user, host and port as well as any
    number or positional arguments to be added to the end of command.
    '''
    (user, host, port, maintenance_db, password) = _connection_defaults(
        kwargs.get('user'),
        kwargs.get('host'),
        kwargs.get('port'),
        kwargs.get('maintenance_db'),
        kwargs.get('password'))

    cmd = [salt.utils.which('psql'),
           '--no-align',
           '--no-readline',
           '--no-password']         # It is never acceptable to issue a password prompt.
    if user:
        cmd += ['--username', user]
    if host:
        cmd += ['--host', host]
    if port:
        cmd += ['--port', str(port)]
    if not maintenance_db:
        maintenance_db = 'postgres'
    cmd += ['--dbname', maintenance_db]
    cmd += args
    cmdstr = ' '.join([pipes.quote(c) for c in cmd])
    return cmdstr


def _psql_prepare_and_run(cmd,
                          host=None,
                          port=None,
                          maintenance_db=None,
                          password=None,
                          runas=None,
                          user=None):
    rcmd = _psql_cmd(
        host=host, user=user, port=port,
        maintenance_db=maintenance_db, password=password,
        *cmd)
    cmdret = _run_psql(
        rcmd, runas=runas, password=password, host=host, port=port, user=user)
    return cmdret


def psql_query(query, user=None, host=None, port=None, maintenance_db=None,
               password=None, runas=None):
    '''
    Run an SQL-Query and return the results as a list. This command
    only supports SELECT statements.  This limitation can be worked around
    with a query like this:

    WITH updated AS (UPDATE pg_authid SET rolconnlimit = 2000 WHERE
    rolname = 'rolename' RETURNING rolconnlimit) SELECT * FROM updated;

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.psql_query 'select * from pg_stat_activity'
    '''
    ret = []

    csv_query = 'COPY ({0}) TO STDOUT WITH CSV HEADER'.format(
        query.strip().rstrip(';'))

    # always use the same datestyle settings to allow parsing dates
    # regardless what server settings are configured
    cmdret = _psql_prepare_and_run(['-v', 'datestyle=ISO,MDY',
                                    '-c', csv_query],
                                   runas=runas,
                                   host=host, user=user, port=port,
                                   maintenance_db=maintenance_db,
                                   password=password)
    if cmdret['retcode'] > 0:
        return ret

    csv_file = StringIO(cmdret['stdout'])
    header = {}
    for row in csv.reader(csv_file, delimiter=',', quotechar='"'):
        if not row:
            continue
        if not header:
            header = row
            continue
        ret.append(dict(zip(header, row)))

    return ret


# Database related actions

def db_list(user=None, host=None, port=None, maintenance_db=None,
            password=None, runas=None):
    '''
    Return dictionary with information about databases of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_list
    '''

    ret = {}

    query = (
        'SELECT datname as "Name", pga.rolname as "Owner", '
        'pg_encoding_to_char(encoding) as "Encoding", '
        'datcollate as "Collate", datctype as "Ctype", '
        'datacl as "Access privileges", spcname as "Tablespace" '
        'FROM pg_database pgd, pg_roles pga, pg_tablespace pgts '
        'WHERE pga.oid = pgd.datdba AND pgts.oid = pgd.dattablespace'
    )

    rows = psql_query(query, runas=runas, host=host, user=user,
                      port=port, maintenance_db=maintenance_db,
                      password=password)

    for row in rows:
        ret[row['Name']] = row
        ret[row['Name']].pop('Name')

    return ret


def db_exists(name, user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None):
    '''
    Checks if a database exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_exists 'dbname'
    '''

    databases = db_list(user=user, host=host, port=port,
                        maintenance_db=maintenance_db,
                        password=password, runas=runas)
    return name in databases


def db_create(name,
              user=None,
              host=None,
              port=None,
              maintenance_db=None,
              password=None,
              tablespace=None,
              encoding=None,
              lc_collate=None,
              lc_ctype=None,
              owner=None,
              template=None,
              runas=None):
    '''
    Adds a databases to the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_create 'dbname'

        salt '*' postgres.db_create 'dbname' template=template_postgis

    '''

    # Base query to create a database
    query = 'CREATE DATABASE "{0}"'.format(name)

    # "With"-options to create a database
    with_args = salt.utils.odict.OrderedDict({
        # owner needs to be enclosed in double quotes so postgres
        # doesn't get thrown by dashes in the name
        'OWNER': owner and '"{0}"'.format(owner),
        'TEMPLATE': template,
        'ENCODING': encoding and '{0!r}'.format(encoding),
        'LC_COLLATE': lc_collate and '{0!r}'.format(lc_collate),
        'LC_CTYPE': lc_ctype and '{0!r}'.format(lc_ctype),
        'TABLESPACE': tablespace,
    })
    with_chunks = []
    for key, value in with_args.items():
        if value is not None:
            with_chunks += [key, '=', value]
    # Build a final query
    if with_chunks:
        with_chunks.insert(0, ' WITH')
        query += ' '.join(with_chunks)

    # Execute the command
    ret = _psql_prepare_and_run(['-c', query],
                                user=user, host=host, port=port,
                                maintenance_db=maintenance_db,
                                password=password, runas=runas)
    return ret['retcode'] == 0


def db_alter(name, user=None, host=None, port=None, maintenance_db=None,
             password=None, tablespace=None, owner=None, owner_recurse=False,
             runas=None):
    '''
    Change tablespace or/and owner of database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_alter dbname owner=otheruser
    '''
    if not any((tablespace, owner)):
        return True  # Nothing todo?

    if owner and owner_recurse:
        ret = owner_to(name, owner,
                       user=user,
                       host=host,
                       port=port,
                       password=password,
                       runas=runas)
    else:
        queries = []
        if owner:
            queries.append('ALTER DATABASE "{0}" OWNER TO "{1}"'.format(
                name, owner
            ))
        if tablespace:
            queries.append('ALTER DATABASE "{0}" SET TABLESPACE "{1}"'.format(
                name, tablespace
            ))
        for query in queries:
            ret = _psql_prepare_and_run(['-c', query],
                                        user=user, host=host, port=port,
                                        maintenance_db=maintenance_db,
                                        password=password, runas=runas)

    if ret['retcode'] != 0:
        return False

    return True


def db_remove(name, user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None):
    '''
    Removes a databases from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.db_remove 'dbname'
    '''

    # db doesn't exist, proceed
    query = 'DROP DATABASE {0}'.format(name)
    ret = _psql_prepare_and_run(['-c', query],
                                user=user,
                                host=host,
                                port=port,
                                runas=runas,
                                maintenance_db=maintenance_db,
                                password=password)
    return ret['retcode'] == 0


# Tablespace related actions

def tablespace_list(user=None, host=None, port=None, maintenance_db=None,
                    password=None, runas=None):
    '''
    Return dictionary with information about tablespaces of a Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_list

    .. versionadded:: 2015.8.0
    '''

    ret = {}

    query = (
        'SELECT spcname as "Name", pga.rolname as "Owner", spcacl as "ACL", '
        'spcoptions as "Opts", pg_tablespace_location(pgts.oid) as "Location" '
        'FROM pg_tablespace pgts, pg_roles pga WHERE pga.oid = pgts.spcowner'
    )

    rows = __salt__['postgres.psql_query'](query, runas=runas, host=host,
                                           user=user, port=port,
                                           maintenance_db=maintenance_db,
                                           password=password)

    for row in rows:
        ret[row['Name']] = row
        ret[row['Name']].pop('Name')

    return ret


def tablespace_exists(name, user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None):
    '''
    Checks if a tablespace exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_exists 'dbname'

    .. versionadded:: 2015.8.0
    '''

    tablespaces = tablespace_list(user=user, host=host, port=port,
                        maintenance_db=maintenance_db,
                        password=password, runas=runas)
    return name in tablespaces


def tablespace_create(name, location, options=None, owner=None, user=None,
                      host=None, port=None, maintenance_db=None, password=None,
                      runas=None):
    '''
    Adds a tablespace to the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_create tablespacename '/path/datadir'

    .. versionadded:: 2015.8.0
    '''
    owner_query = ''
    options_query = ''
    if owner:
        owner_query = 'OWNER {0}'.format(owner)
        # should come out looking like: 'OWNER postgres'
    if options:
        optionstext = ['{0} = {1}'.format(k, v) for k, v in options.items()]
        options_query = 'WITH ( {0} )'.format(', '.join(optionstext))
        # should come out looking like: 'WITH ( opt1 = 1.0, opt2 = 4.0 )'
    query = 'CREATE TABLESPACE {0} {1} LOCATION \'{2}\' {3}'.format(name,
                                                                owner_query,
                                                                location,
                                                                options_query)

    # Execute the command
    ret = _psql_prepare_and_run(['-c', query],
                                user=user, host=host, port=port,
                                maintenance_db=maintenance_db,
                                password=password, runas=runas)
    return ret['retcode'] == 0


def tablespace_alter(name, user=None, host=None, port=None, maintenance_db=None,
                     password=None, new_name=None, new_owner=None,
                     set_option=None, reset_option=None, runas=None):
    '''
    Change tablespace name, owner, or options.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_alter tsname new_owner=otheruser
        salt '*' postgres.tablespace_alter index_space new_name=fast_raid
        salt '*' postgres.tablespace_alter test set_option="{'seq_page_cost': '1.1'}"
        salt '*' postgres.tablespace_alter tsname reset_option=seq_page_cost

    .. versionadded:: 2015.8.0
    '''
    if not any([new_name, new_owner, set_option, reset_option]):
        return True  # Nothing todo?

    queries = []

    if new_name:
        queries.append('ALTER TABLESPACE {0} RENAME TO {1}'.format(
                       name, new_name))
    if new_owner:
        queries.append('ALTER TABLESPACE {0} OWNER TO {1}'.format(
                       name, new_owner))
    if set_option:
        queries.append('ALTER TABLESPACE {0} SET ({1} = {2})'.format(
                       name, set_option.keys()[0], set_option.values()[0]))
    if reset_option:
        queries.append('ALTER TABLESPACE {0} RESET ({1})'.format(
                       name, reset_option))

    for query in queries:
        ret = _psql_prepare_and_run(['-c', query],
                                    user=user, host=host, port=port,
                                    maintenance_db=maintenance_db,
                                    password=password, runas=runas)
        if ret['retcode'] != 0:
            return False

    return True


def tablespace_remove(name, user=None, host=None, port=None,
                      maintenance_db=None, password=None, runas=None):
    '''
    Removes a tablespace from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.tablespace_remove tsname

    .. versionadded:: 2015.8.0
    '''
    query = 'DROP TABLESPACE {0}'.format(name)
    ret = _psql_prepare_and_run(['-c', query],
                                user=user,
                                host=host,
                                port=port,
                                runas=runas,
                                maintenance_db=maintenance_db,
                                password=password)
    return ret['retcode'] == 0


# User related actions

def user_list(user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None, return_password=False):
    '''
    Return a dict with information about users of a Postgres server.

    Set return_password to True to get password hash in the result.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_list
    '''

    ret = {}

    ver = _parsed_version(user=user,
                          host=host,
                          port=port,
                          maintenance_db=maintenance_db,
                          password=password,
                          runas=runas)
    if ver:
        if ver >= distutils.version.LooseVersion('9.1'):
            replication_column = 'pg_roles.rolreplication'
        else:
            replication_column = 'NULL'
        if ver >= distutils.version.LooseVersion('9.5'):
            rolcatupdate_column = 'NULL'
        else:
            rolcatupdate_column = 'pg_roles.rolcatupdate'
    else:
        log.error('Could not retrieve Postgres version. Is Postgresql server running?')
        return False

    # will return empty string if return_password = False
    _x = lambda s: s if return_password else ''

    query = (''.join([
        'SELECT '
        'pg_roles.rolname as "name",'
        'pg_roles.rolsuper as "superuser", '
        'pg_roles.rolinherit as "inherits privileges", '
        'pg_roles.rolcreaterole as "can create roles", '
        'pg_roles.rolcreatedb as "can create databases", '
        '{0} as "can update system catalogs", '
        'pg_roles.rolcanlogin as "can login", '
        '{1} as "replication", '
        'pg_roles.rolconnlimit as "connections", '
        'pg_roles.rolvaliduntil::timestamp(0) as "expiry time", '
        'pg_roles.rolconfig  as "defaults variables" '
        , _x(', COALESCE(pg_shadow.passwd, pg_authid.rolpassword) as "password" '),
        'FROM pg_roles '
        , _x('LEFT JOIN pg_authid ON pg_roles.oid = pg_authid.oid ')
        , _x('LEFT JOIN pg_shadow ON pg_roles.oid = pg_shadow.usesysid')
    ]).format(rolcatupdate_column, replication_column))

    rows = psql_query(query,
                      runas=runas,
                      host=host,
                      user=user,
                      port=port,
                      maintenance_db=maintenance_db,
                      password=password)

    def get_bool(rowdict, key):
        '''
        Returns the boolean value of the key, instead of 't' and 'f' strings.
        '''
        if rowdict[key] == 't':
            return True
        elif rowdict[key] == 'f':
            return False
        else:
            return None

    for row in rows:
        retrow = {}
        for key in ('superuser', 'inherits privileges', 'can create roles',
                    'can create databases', 'can update system catalogs',
                    'can login', 'replication', 'connections'):
            retrow[key] = get_bool(row, key)
        for date_key in ('expiry time',):
            try:
                retrow[date_key] = datetime.datetime.strptime(
                    row['date_key'], '%Y-%m-%d %H:%M:%S')
            except (ValueError, KeyError):
                retrow[date_key] = None
        retrow['defaults variables'] = row['defaults variables']
        if return_password:
            retrow['password'] = row['password']
        ret[row['name']] = retrow

    # for each role, determine the inherited roles
    for role in six.iterkeys(ret):
        rdata = ret[role]
        groups = rdata.setdefault('groups', [])
        query = (
            'select rolname'
            ' from pg_user'
            ' join pg_auth_members'
            '      on (pg_user.usesysid=pg_auth_members.member)'
            ' join pg_roles '
            '      on (pg_roles.oid=pg_auth_members.roleid)'
            ' where pg_user.usename=\'{0}\''
        ).format(role)
        try:
            rows = psql_query(query,
                              runas=runas,
                              host=host,
                              user=user,
                              port=port,
                              maintenance_db=maintenance_db,
                              password=password)
            for row in rows:
                if row['rolname'] not in groups:
                    groups.append(row['rolname'])
        except Exception:
            # do not fail here, it is just a bonus
            # to try to determine groups, but the query
            # is not portable amongst all pg versions
            continue
    return ret


def role_get(name, user=None, host=None, port=None, maintenance_db=None,
             password=None, runas=None, return_password=False):
    '''
    Return a dict with information about users of a Postgres server.

    Set return_password to True to get password hash in the result.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.role_get postgres
    '''
    all_users = user_list(user=user,
                          host=host,
                          port=port,
                          maintenance_db=maintenance_db,
                          password=password,
                          runas=runas,
                          return_password=return_password)
    try:
        return all_users.get(name, None)
    except AttributeError:
        log.error('Could not retrieve Postgres role. Is Postgres running?')
        return None


def user_exists(name,
                user=None, host=None, port=None, maintenance_db=None,
                password=None,
                runas=None):
    '''
    Checks if a user exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_exists 'username'
    '''
    return bool(
        role_get(name,
                 user=user,
                 host=host,
                 port=port,
                 maintenance_db=maintenance_db,
                 password=password,
                 runas=runas,
                 return_password=False))


def _add_role_flag(string,
                   test,
                   flag,
                   cond=None,
                   prefix='NO',
                   addtxt='',
                   skip=False):
    if not skip:
        if cond is None:
            cond = test
        if test is not None:
            if cond:
                string = '{0} {1}'.format(string, flag)
            else:
                string = '{0} {2}{1}'.format(string, flag, prefix)
        if addtxt:
            string = '{0} {1}'.format(string, addtxt)
    return string


def _maybe_encrypt_password(role,
                            password,
                            encrypted=_DEFAULT_PASSWORDS_ENCRYPTION):
    '''
    pgsql passwords are md5 hashes of the string: 'md5{password}{rolename}'
    '''
    if encrypted and password and not password.startswith('md5'):
        password = "md5{0}".format(
            hashlib.md5(salt.utils.to_bytes('{0}{1}'.format(password, role))).hexdigest())
    return password


def _role_cmd_args(name,
                   sub_cmd='',
                   typ_='role',
                   encrypted=None,
                   login=None,
                   connlimit=None,
                   inherit=None,
                   createdb=None,
                   createuser=None,
                   createroles=None,
                   superuser=None,
                   groups=None,
                   replication=None,
                   rolepassword=None,
                   db_role=None):
    if createuser is not None and superuser is None:
        superuser = createuser
    if inherit is None:
        if typ_ in ['user', 'group']:
            inherit = True
    if login is None:
        if typ_ == 'user':
            login = True
        if typ_ == 'group':
            login = False
    # defaults to encrypted passwords (md5{password}{rolename})
    if encrypted is None:
        encrypted = _DEFAULT_PASSWORDS_ENCRYPTION
    skip_passwd = False
    escaped_password = ''
    if not (
        rolepassword is not None
        # first is passwd set
        # second is for handling NOPASSWD
        and (
            isinstance(rolepassword, six.string_types) and bool(rolepassword)
        )
        or (
            isinstance(rolepassword, bool)
        )
    ):
        skip_passwd = True
    if isinstance(rolepassword, six.string_types) and bool(rolepassword):
        escaped_password = '{0!r}'.format(
            _maybe_encrypt_password(name,
                                    rolepassword.replace('\'', '\'\''),
                                    encrypted=encrypted))
    skip_superuser = False
    if bool(db_role) and bool(superuser) == bool(db_role['superuser']):
        skip_superuser = True
    flags = (
        {'flag': 'INHERIT', 'test': inherit},
        {'flag': 'CREATEDB', 'test': createdb},
        {'flag': 'CREATEROLE', 'test': createroles},
        {'flag': 'SUPERUSER', 'test': superuser,
         'skip': skip_superuser},
        {'flag': 'REPLICATION', 'test': replication},
        {'flag': 'LOGIN', 'test': login},
        {'flag': 'CONNECTION LIMIT',
         'test': bool(connlimit),
         'addtxt': str(connlimit),
         'skip': connlimit is None},
        {'flag': 'ENCRYPTED',
         'test': (encrypted is not None and bool(rolepassword)),
         'skip': skip_passwd or isinstance(rolepassword, bool),
         'cond': encrypted,
         'prefix': 'UN'},
        {'flag': 'PASSWORD', 'test': bool(rolepassword),
         'skip': skip_passwd,
         'addtxt': escaped_password},
    )
    for data in flags:
        sub_cmd = _add_role_flag(sub_cmd, **data)
    if sub_cmd.endswith('WITH'):
        sub_cmd = sub_cmd.replace(' WITH', '')
    if groups:
        if isinstance(groups, list):
            groups = ','.join(groups)
        for group in groups.split(','):
            sub_cmd = '{0}; GRANT "{1}" TO "{2}"'.format(sub_cmd, group, name)
    return sub_cmd


def _role_create(name,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=None,
                 createroles=None,
                 createuser=None,
                 encrypted=None,
                 superuser=None,
                 login=None,
                 connlimit=None,
                 inherit=None,
                 replication=None,
                 rolepassword=None,
                 typ_='role',
                 groups=None,
                 runas=None):
    '''
    Creates a Postgres role. Users and Groups are both roles in postgres.
    However, users can login, groups cannot.
    '''

    # check if role exists
    if user_exists(name, user, host, port, maintenance_db,
                   password=password, runas=runas):
        log.info('{0} {1!r} already exists'.format(typ_.capitalize(), name))
        return False

    sub_cmd = 'CREATE ROLE "{0}" WITH'.format(name)
    sub_cmd = '{0} {1}'.format(sub_cmd, _role_cmd_args(
        name,
        typ_=typ_,
        encrypted=encrypted,
        login=login,
        connlimit=connlimit,
        inherit=inherit,
        createdb=createdb,
        createroles=createroles,
        createuser=createuser,
        superuser=superuser,
        groups=groups,
        replication=replication,
        rolepassword=rolepassword
    ))
    ret = _psql_prepare_and_run(['-c', sub_cmd],
                                runas=runas, host=host, user=user, port=port,
                                maintenance_db=maintenance_db,
                                password=password)

    return ret['retcode'] == 0


def user_create(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                createdb=None,
                createuser=None,
                createroles=None,
                inherit=None,
                login=None,
                connlimit=None,
                encrypted=None,
                superuser=None,
                replication=None,
                rolepassword=None,
                groups=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.user_create 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    '''
    return _role_create(username,
                        typ_='user',
                        user=user,
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        createdb=createdb,
                        createuser=createuser,
                        createroles=createroles,
                        inherit=inherit,
                        login=login,
                        connlimit=connlimit,
                        encrypted=encrypted,
                        superuser=superuser,
                        replication=replication,
                        rolepassword=rolepassword,
                        groups=groups,
                        runas=runas)


def _role_update(name,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=None,
                 createuser=None,
                 typ_='role',
                 createroles=None,
                 inherit=None,
                 login=None,
                 connlimit=None,
                 encrypted=None,
                 superuser=None,
                 replication=None,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Updates a postgres role.
    '''
    role = role_get(name,
                    user=user,
                    host=host,
                    port=port,
                    maintenance_db=maintenance_db,
                    password=password,
                    runas=runas,
                    return_password=False)

    # check if user exists
    if not bool(role):
        log.info('{0} {1!r} could not be found'.format(typ_.capitalize(), name))
        return False

    sub_cmd = 'ALTER ROLE "{0}" WITH'.format(name)
    sub_cmd = '{0} {1}'.format(sub_cmd, _role_cmd_args(
        name,
        encrypted=encrypted,
        login=login,
        connlimit=connlimit,
        inherit=inherit,
        createdb=createdb,
        createuser=createuser,
        createroles=createroles,
        superuser=superuser,
        groups=groups,
        replication=replication,
        rolepassword=rolepassword,
        db_role=role
    ))
    ret = _psql_prepare_and_run(['-c', sub_cmd],
                                runas=runas, host=host, user=user, port=port,
                                maintenance_db=maintenance_db,
                                password=password)

    return ret['retcode'] == 0


def user_update(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                createdb=None,
                createuser=None,
                createroles=None,
                encrypted=None,
                superuser=None,
                inherit=None,
                login=None,
                connlimit=None,
                replication=None,
                rolepassword=None,
                groups=None,
                runas=None):
    '''
    Updates a Postgres user.

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.user_update 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    '''
    return _role_update(username,
                        user=user,
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        typ_='user',
                        inherit=inherit,
                        login=login,
                        connlimit=connlimit,
                        createdb=createdb,
                        createuser=createuser,
                        createroles=createroles,
                        encrypted=encrypted,
                        superuser=superuser,
                        replication=replication,
                        rolepassword=rolepassword,
                        groups=groups,
                        runas=runas)


def _role_remove(name, user=None, host=None, port=None, maintenance_db=None,
                 password=None, runas=None):
    '''
    Removes a role from the Postgres Server
    '''

    # check if user exists
    if not user_exists(name, user, host, port, maintenance_db,
                       password=password, runas=runas):
        log.info('User {0!r} does not exist'.format(name))
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE {0}'.format(name)
    _psql_prepare_and_run(
        ['-c', sub_cmd],
        runas=runas, host=host, user=user, port=port,
        maintenance_db=maintenance_db, password=password)

    if not user_exists(name, user, host, port, maintenance_db,
                       password=password, runas=runas):
        return True
    else:
        log.info('Failed to delete user {0!r}.'.format(name))
        return False


def available_extensions(user=None,
                         host=None,
                         port=None,
                         maintenance_db=None,
                         password=None,
                         runas=None):
    '''
    List available postgresql extensions

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.available_extensions

    '''
    exts = []
    query = (
        'select * '
        'from pg_available_extensions();'
    )
    ret = psql_query(query, user=user, host=host, port=port,
                     maintenance_db=maintenance_db,
                     password=password, runas=runas)
    exts = {}
    for row in ret:
        if 'default_version' in row and 'name' in row:
            exts[row['name']] = row
    return exts


def installed_extensions(user=None,
                         host=None,
                         port=None,
                         maintenance_db=None,
                         password=None,
                         runas=None):
    '''
    List installed postgresql extensions

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.installed_extensions

    '''
    exts = []
    query = (
        'select a.*, b.nspname as schema_name '
        'from pg_extension a,  pg_namespace b where a.extnamespace = b.oid;'
    )
    ret = psql_query(query, user=user, host=host, port=port,
                     maintenance_db=maintenance_db,
                     password=password, runas=runas)
    exts = {}
    for row in ret:
        if 'extversion' in row and 'extname' in row:
            exts[row['extname']] = row
    return exts


def get_available_extension(name,
                            user=None,
                            host=None,
                            port=None,
                            maintenance_db=None,
                            password=None,
                            runas=None):
    '''
    Get info about an available postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.get_available_extension plpgsql

    '''
    return available_extensions(user=user,
                                host=host,
                                port=port,
                                maintenance_db=maintenance_db,
                                password=password,
                                runas=runas).get(name, None)


def get_installed_extension(name,
                            user=None,
                            host=None,
                            port=None,
                            maintenance_db=None,
                            password=None,
                            runas=None):
    '''
    Get info about an installed postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.get_installed_extension plpgsql

    '''
    return installed_extensions(user=user,
                                host=host,
                                port=port,
                                maintenance_db=maintenance_db,
                                password=password,
                                runas=runas).get(name, None)


def is_available_extension(name,
                           user=None,
                           host=None,
                           port=None,
                           maintenance_db=None,
                           password=None,
                           runas=None):
    '''
    Test if a specific extension is available

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.is_available_extension

    '''
    exts = available_extensions(user=user,
                                host=host,
                                port=port,
                                maintenance_db=maintenance_db,
                                password=password,
                                runas=runas)
    if name.lower() in [
        a.lower()
        for a in exts
    ]:
        return True
    return False


def _pg_is_older_ext_ver(a, b):
    '''Return true if version a is lesser than b
    TODO: be more intelligent to test versions

    '''
    return a < b


def is_installed_extension(name,
                           user=None,
                           host=None,
                           port=None,
                           maintenance_db=None,
                           password=None,
                           runas=None):
    '''
    Test if a specific extension is installed

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.is_installed_extension

    '''
    installed_ext = get_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas)
    return bool(installed_ext)


def create_metadata(name,
                    ext_version=None,
                    schema=None,
                    user=None,
                    host=None,
                    port=None,
                    maintenance_db=None,
                    password=None,
                    runas=None):
    '''
    Get lifecycle information about an extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.create_metadata adminpack

    '''
    installed_ext = get_installed_extension(
        name,
        user=user,
        host=host,
        port=port,
        maintenance_db=maintenance_db,
        password=password,
        runas=runas)
    ret = [_EXTENSION_NOT_INSTALLED]
    if installed_ext:
        ret = [_EXTENSION_INSTALLED]
        if (
            ext_version is not None
            and _pg_is_older_ext_ver(
                installed_ext.get('extversion', ext_version),
                ext_version
            )
        ):
            ret.append(_EXTENSION_TO_UPGRADE)
        if (
            schema is not None
            and installed_ext.get('extrelocatable', 'f') == 't'
            and installed_ext.get('schema_name', schema) != schema
        ):
            ret.append(_EXTENSION_TO_MOVE)
    return ret


def drop_extension(name,
                   if_exists=None,
                   restrict=None,
                   cascade=None,
                   user=None,
                   host=None,
                   port=None,
                   maintenance_db=None,
                   password=None,
                   runas=None):
    '''
    Drop an installed postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.drop_extension 'adminpack'

    '''
    if cascade is None:
        cascade = True
    if if_exists is None:
        if_exists = False
    if restrict is None:
        restrict = False
    args = ['DROP EXTENSION']
    if if_exists:
        args.append('IF EXISTS')
    args.append(name)
    if cascade:
        args.append('CASCADE')
    if restrict:
        args.append('RESTRICT')
    args.append(';')
    cmd = ' '.join(args)
    if is_installed_extension(name,
                              user=user,
                              host=host,
                              port=port,
                              maintenance_db=maintenance_db,
                              password=password,
                              runas=runas):
        _psql_prepare_and_run(
            ['-c', cmd],
            runas=runas, host=host, user=user, port=port,
            maintenance_db=maintenance_db, password=password)
    ret = not is_installed_extension(name,
                                     user=user,
                                     host=host,
                                     port=port,
                                     maintenance_db=maintenance_db,
                                     password=password,
                                     runas=runas)
    if not ret:
        log.info('Failed to drop ext: {0}'.format(name))
    return ret


def create_extension(name,
                     if_not_exists=None,
                     schema=None,
                     ext_version=None,
                     from_version=None,
                     user=None,
                     host=None,
                     port=None,
                     maintenance_db=None,
                     password=None,
                     runas=None):
    '''
    Install a postgresql extension

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.create_extension 'adminpack'

    '''
    if if_not_exists is None:
        if_not_exists = True
    mtdata = create_metadata(name,
                             ext_version=ext_version,
                             schema=schema,
                             user=user,
                             host=host,
                             port=port,
                             maintenance_db=maintenance_db,
                             password=password,
                             runas=runas)
    installed = _EXTENSION_NOT_INSTALLED not in mtdata
    installable = is_available_extension(name,
                                         user=user,
                                         host=host,
                                         port=port,
                                         maintenance_db=maintenance_db,
                                         password=password,
                                         runas=runas)
    if installable:
        if not installed:
            args = ['CREATE EXTENSION']
            if if_not_exists:
                args.append('IF NOT EXISTS')
            args.append('"{0}"'.format(name))
            sargs = []
            if schema:
                sargs.append('SCHEMA {0}'.format(schema))
            if ext_version:
                sargs.append('VERSION {0}'.format(ext_version))
            if from_version:
                sargs.append('FROM {0}'.format(from_version))
            if sargs:
                args.append('WITH')
                args.extend(sargs)
            args.append(';')
            cmd = ' '.join(args).strip()
        else:
            args = []
            if schema and _EXTENSION_TO_MOVE in mtdata:
                args.append('ALTER EXTENSION "{0}" SET SCHEMA {1};'.format(
                    name, schema))
            if ext_version and _EXTENSION_TO_UPGRADE in mtdata:
                args.append('ALTER EXTENSION "{0}" UPDATE TO {1};'.format(
                    name, ext_version))
            cmd = ' '.join(args).strip()
        if cmd:
            _psql_prepare_and_run(
                ['-c', cmd],
                runas=runas, host=host, user=user, port=port,
                maintenance_db=maintenance_db, password=password)
    mtdata = create_metadata(name,
                             ext_version=ext_version,
                             schema=schema,
                             user=user,
                             host=host,
                             port=port,
                             maintenance_db=maintenance_db,
                             password=password,
                             runas=runas)
    ret = True
    for i in _EXTENSION_FLAGS:
        if (i in mtdata) and (i != _EXTENSION_INSTALLED):
            ret = False
    if not ret:
        log.info('Failed to create ext: {0}'.format(name))
    return ret


def user_remove(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.user_remove 'username'
    '''
    return _role_remove(username,
                        user=user,
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        runas=runas)


# Group related actions

def group_create(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=None,
                 createuser=None,
                 createroles=None,
                 encrypted=None,
                 login=None,
                 inherit=None,
                 superuser=None,
                 replication=None,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Creates a Postgres group. A group is postgres is similar to a user, but
    cannot login.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.group_create 'groupname' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    '''
    return _role_create(groupname,
                        user=user,
                        typ_='group',
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        createdb=createdb,
                        createroles=createroles,
                        createuser=createuser,
                        encrypted=encrypted,
                        login=login,
                        inherit=inherit,
                        superuser=superuser,
                        replication=replication,
                        rolepassword=rolepassword,
                        groups=groups,
                        runas=runas)


def group_update(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=None,
                 createroles=None,
                 createuser=None,
                 encrypted=None,
                 inherit=None,
                 login=None,
                 superuser=None,
                 replication=None,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Updates a postgres group

    CLI Examples:

    .. code-block:: bash

        salt '*' postgres.group_update 'username' user='user' \\
                host='hostname' port='port' password='password' \\
                rolepassword='rolepassword'
    '''
    return _role_update(groupname,
                        user=user,
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        createdb=createdb,
                        typ_='group',
                        createroles=createroles,
                        createuser=createuser,
                        encrypted=encrypted,
                        login=login,
                        inherit=inherit,
                        superuser=superuser,
                        replication=replication,
                        rolepassword=rolepassword,
                        groups=groups,
                        runas=runas)


def group_remove(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 runas=None):
    '''
    Removes a group from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.group_remove 'groupname'
    '''
    return _role_remove(groupname,
                        user=user,
                        host=host,
                        port=port,
                        maintenance_db=maintenance_db,
                        password=password,
                        runas=runas)


def owner_to(dbname,
             ownername,
             user=None,
             host=None,
             port=None,
             password=None,
             runas=None):
    '''
    Set the owner of all schemas, functions, tables, views and sequences to
    the given username.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.owner_to 'dbname' 'username'
    '''

    sqlfile = tempfile.NamedTemporaryFile()
    sqlfile.write('begin;\n')
    sqlfile.write(
        'alter database {0} owner to {1};\n'.format(
            dbname, ownername
        )
    )

    queries = (
        # schemas
        ('alter schema {n} owner to {owner};',
         'select quote_ident(schema_name) as n from '
         'information_schema.schemata;'),
        # tables and views
        ('alter table {n} owner to {owner};',
         'select quote_ident(table_schema)||\'.\'||quote_ident(table_name) as '
         'n from information_schema.tables where table_schema not in '
         '(\'pg_catalog\', \'information_schema\');'),
        # functions
        ('alter function {n} owner to {owner};',
         'select p.oid::regprocedure::text as n from pg_catalog.pg_proc p '
         'join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where '
         'ns.nspname not in (\'pg_catalog\', \'information_schema\') '
         ' and not p.proisagg;'),
        # aggregate functions
        ('alter aggregate {n} owner to {owner};',
         'select p.oid::regprocedure::text as n from pg_catalog.pg_proc p '
         'join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where '
         'ns.nspname not in (\'pg_catalog\', \'information_schema\') '
         'and p.proisagg;'),
        # sequences
        ('alter sequence {n} owner to {owner};',
         'select quote_ident(sequence_schema)||\'.\'||'
         'quote_ident(sequence_name) as n from information_schema.sequences;')
    )

    for fmt, query in queries:
        ret = psql_query(query, user=user, host=host, port=port,
                         maintenance_db=dbname, password=password, runas=runas)
        for row in ret:
            sqlfile.write(fmt.format(owner=ownername, n=row['n']) + '\n')

    sqlfile.write('commit;\n')
    sqlfile.flush()
    os.chmod(sqlfile.name, 0o644)  # ensure psql can read the file

    # run the generated sqlfile in the db
    cmdret = _psql_prepare_and_run(['-f', sqlfile.name],
                                   user=user,
                                   runas=runas,
                                   host=host,
                                   port=port,
                                   password=password,
                                   maintenance_db=dbname)
    return cmdret

# Schema related actions


def schema_create(dbname, name, owner=None,
                  user=None,
                  db_user=None, db_password=None,
                  db_host=None, db_port=None):
    '''
    Creates a Postgres schema.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_create dbname name owner='owner' \\
                user='user' \\
                db_user='user' db_password='password'
                db_host='hostname' db_port='port'
    '''

    # check if schema exists
    if schema_exists(dbname, name,
                     db_user=db_user, db_password=db_password,
                     db_host=db_host, db_port=db_port):
        log.info('{0!r} already exists in {1!r}'.format(name, dbname))
        return False

    sub_cmd = 'CREATE SCHEMA {0}'.format(name)
    if owner is not None:
        sub_cmd = '{0} AUTHORIZATION {1}'.format(sub_cmd, owner)

    ret = _psql_prepare_and_run(['-c', sub_cmd],
                                user=db_user, password=db_password,
                                port=db_port, host=db_host,
                                maintenance_db=dbname, runas=user)

    return ret['retcode'] == 0


def schema_remove(dbname, name,
                  user=None,
                  db_user=None, db_password=None,
                  db_host=None, db_port=None):
    '''
    Removes a schema from the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_remove dbname schemaname

    dbname
        Database name we work on

    schemaname
        The schema's name we'll remove

    user
        System user all operations should be performed on behalf of

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default

    '''

    # check if schema exists
    if not schema_exists(dbname, name,
                         db_user=db_user, db_password=db_password,
                         db_host=db_host, db_port=db_port):
        log.info('Schema {0!r} does not exist in {1!r}'.format(name, dbname))
        return False

    # schema exists, proceed
    sub_cmd = 'DROP SCHEMA {0}'.format(name)
    _psql_prepare_and_run(
        ['-c', sub_cmd],
        runas=user,
        maintenance_db=dbname,
        host=db_host, user=db_user, port=db_port, password=db_password)

    if not schema_exists(dbname, name,
                         db_user=db_user, db_password=db_password,
                         db_host=db_host, db_port=db_port):
        return True
    else:
        log.info('Failed to delete schema {0!r}.'.format(name))
        return False


def schema_exists(dbname, name,
                  db_user=None, db_password=None,
                  db_host=None, db_port=None):
    '''
    Checks if a schema exists on the Postgres server.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_exists dbname schemaname

    dbname
        Database name we query on

    name
       Schema name we look for

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default

    '''
    return bool(
        schema_get(dbname, name,
                   db_user=db_user,
                   db_host=db_host,
                   db_port=db_port,
                   db_password=db_password))


def schema_get(dbname, name,
               db_user=None, db_password=None,
               db_host=None, db_port=None):
    '''
    Return a dict with information about schemas in a database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_get dbname name

    dbname
        Database name we query on

    name
       Schema name we look for

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''
    all_schemas = schema_list(dbname,
                              db_user=db_user,
                              db_host=db_host,
                              db_port=db_port,
                              db_password=db_password)
    try:
        return all_schemas.get(name, None)
    except AttributeError:
        log.error('Could not retrieve Postgres schema. Is Postgres running?')
        return False


def schema_list(dbname,
                db_user=None, db_password=None,
                db_host=None, db_port=None):
    '''
    Return a dict with information about schemas in a Postgres database.

    CLI Example:

    .. code-block:: bash

        salt '*' postgres.schema_list dbname

    dbname
        Database name we query on

    db_user
        database username if different from config or default

    db_password
        user password if any password for a specified user

    db_host
        Database host if different from config or default

    db_port
        Database port if different from config or default
    '''

    ret = {}

    query = (''.join([
        'SELECT '
        'pg_namespace.nspname as "name",'
        'pg_namespace.nspacl as "acl", '
        'pg_roles.rolname as "owner" '
        'FROM pg_namespace '
        'LEFT JOIN pg_roles ON pg_roles.oid = pg_namespace.nspowner '
    ]))

    rows = psql_query(query,
                      host=db_host,
                      user=db_user,
                      port=db_port,
                      maintenance_db=dbname,
                      password=db_password)

    for row in rows:
        retrow = {}
        for key in ('owner', 'acl'):
            retrow[key] = row[key]
        ret[row['name']] = retrow

    return ret
