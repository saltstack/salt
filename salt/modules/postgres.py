'''
Module to provide Postgres compatibility to salt.

:configuration: In order to connect to Postgres, certain configuration is
    required in /etc/salt/minion on the relevant minions. Some sample configs
    might look like::

        postgres.host: 'localhost'
        postgres.port: '5432'
        postgres.user: 'postgres'
        postgres.pass: ''
        postgres.maintenance_db: 'postgres'

    The default for the maintenance_db is 'postgres' and in most cases it can
    be left at the default setting.
    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar
'''

# Import python libs
import datetime
import pipes
import logging
import csv
import StringIO
import os
import tempfile

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the psql bin exists
    '''
    if salt.utils.which('psql'):
        return 'postgres'
    return False


def _run_psql(cmd, runas=None, password=None, host=None,
              run_cmd="cmd.run_all"):
    '''
    Helper function to call psql, because the password requirement
    makes this too much code to be repeated in each function below
    '''
    kwargs = {}
    if runas is None:
        if not host:
            host = __salt__['config.option']('postgres.host')
        if not host or host.startswith('/'):
            if 'FreeBSD' in __grains__['os_family']:
                runas = 'pgsql'
            else:
                runas = 'postgres'

    if runas:
        kwargs['runas'] = runas

    if password is None:
        password = __salt__['config.option']('postgres.pass')
    if password is not None:
        pgpassfile = salt.utils.mkstemp(text=True)
        with salt.utils.fopen(pgpassfile, 'w') as fp_:
            fp_.write('{0}:*:*:{1}:{2}'.format(
                'localhost' if not host or host.startswith('/') else host,
                runas if runas else '*',
                password
            ))
            __salt__['file.chown'](pgpassfile, runas, '')
            kwargs['env'] = {'PGPASSFILE': pgpassfile}

    ret = __salt__[run_cmd](cmd, **kwargs)

    if password is not None and not __salt__['file.remove'](pgpassfile):
        log.warning('Remove PGPASSFILE failed')

    return ret


def version(user=None, host=None, port=None, maintenance_db=None,
            password=None, runas=None):
    '''
    Return the version of a Postgres server.

    CLI Example::

        salt '*' postgres.version
    '''
    query = 'SELECT setting FROM pg_catalog.pg_settings ' \
            'WHERE name = \'server_version\''
    cmd = _psql_cmd('-c', query, '-t', host=host, user=user,
                    port=port, maintenance_db=maintenance_db,
                    password=password)
    ret = _run_psql(cmd, runas=runas, password=password, host=host)

    for line in ret['stdout'].splitlines():
        return line


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
           '--no-readline']
    if password is None:
        cmd += ['--no-password']
    if user:
        cmd += ['--username', user]
    if host:
        cmd += ['--host', host]
    if port:
        cmd += ['--port', port]
    if not maintenance_db:
        maintenance_db = 'postgres'
    cmd += ['--dbname', maintenance_db]
    cmd += args
    cmdstr = ' '.join(map(pipes.quote, cmd))
    return cmdstr


def psql_query(query, user=None, host=None, port=None, maintenance_db=None,
               password=None, runas=None):
    '''
    Run an SQL-Query and return the results as a list. This command
    only supports SELECT statements.

    CLI Example::

        salt '*' postgres.psql_query 'select * from pg_stat_activity'
    '''
    ret = []

    csv_query = 'COPY ({0}) TO STDOUT WITH CSV HEADER'.format(
        query.strip().rstrip(';'))

    cmd = _psql_cmd(
        # always use the same datestyle settings to allow parsing dates
        # regardless what server settings are configured
        '-v', 'datestyle=ISO,MDY',
        '-c', csv_query,
        host=host, user=user, port=port, maintenance_db=maintenance_db,
        password=password)

    cmdret = _run_psql(cmd, runas=runas, password=password)

    if cmdret['retcode'] > 0:
        return ret

    csv_file = StringIO.StringIO(cmdret['stdout'])
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

    CLI Example::

        salt '*' postgres.db_list
    '''

    ret = {}

    query = 'SELECT datname as "Name", pga.rolname as "Owner", ' \
            'pg_encoding_to_char(encoding) as "Encoding", ' \
            'datcollate as "Collate", datctype as "Ctype", ' \
            'datacl as "Access privileges", spcname as "Tablespace" ' \
            'FROM pg_database pgd, pg_roles pga, pg_tablespace pgts ' \
            'WHERE pga.oid = pgd.datdba AND pgts.oid = pgd.dattablespace'

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

    CLI Example::

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

    CLI Example::

        salt '*' postgres.db_create 'dbname'

        salt '*' postgres.db_create 'dbname' template=template_postgis

    '''

    # Base query to create a database
    query = 'CREATE DATABASE "{0}"'.format(name)

    # "With"-options to create a database
    with_args = {
        # owner needs to be enclosed in double quotes so postgres
        # doesn't get thrown by dashes in the name
        'OWNER': owner and '"{0}"'.format(owner),
        'TEMPLATE': template,
        'ENCODING': encoding and '\'{0}\''.format(encoding),
        'LC_COLLATE': lc_collate and '\'{0}\''.format(lc_collate),
        'LC_CTYPE': lc_ctype and '\'{0}\''.format(lc_ctype),
        'TABLESPACE': tablespace,
    }
    with_chunks = []
    for key, value in with_args.iteritems():
        if value is not None:
            with_chunks += [key, '=', value]
    # Build a final query
    if with_chunks:
        with_chunks.insert(0, ' WITH')
        query += ' '.join(with_chunks)

    # Execute the command
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port,
                    maintenance_db=maintenance_db,
                    password=password)
    ret = _run_psql(cmd, runas=runas, password=password, host=host)

    return ret['retcode'] == 0


def db_alter(name, user=None, host=None, port=None, maintenance_db=None,
             password=None, tablespace=None, owner=None, runas=None):
    '''
    Change tablesbase or/and owner of databse.

    CLI Example::

        salt '*' postgres.db_alter dbname owner=otheruser
    '''
    if not any((tablespace, owner)):
        return True  # Nothing todo?

    queries = []
    if owner:
        queries.append('ALTER DATABASE "{0}" OWNER TO "{1}"'.format(
            name, owner
        ))
    if tablespace:
        queries.append('ALTER DATABASE "{0}" SET TABLESPACE "{1}"'.format(
            name, tablespace
        ))
    for Q in queries:
        cmd = _psql_cmd('-c', Q, user=user, host=host, port=port,
                        maintenance_db=maintenance_db, password=password)
        ret = _run_psql(cmd, runas=runas, password=password, host=host)
        if ret['retcode'] != 0:
            return False

    return True


def db_remove(name, user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None):
    '''
    Removes a databases from the Postgres server.

    CLI Example::

        salt '*' postgres.db_remove 'dbname'
    '''

    # db doesn't exist, proceed
    query = 'DROP DATABASE {0}'.format(name)
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port,
                    maintenance_db=maintenance_db, password=password)
    ret = _run_psql(cmd, runas=runas, password=password, host=host)
    return ret['retcode'] == 0


# User related actions

def user_list(user=None, host=None, port=None, maintenance_db=None,
              password=None, runas=None):
    '''
    Return a dict with information about users of a Postgres server.

    CLI Example::

        salt '*' postgres.user_list
    '''

    ret = {}

    ver = version(user=user,
                  host=host,
                  port=port,
                  maintenance_db=maintenance_db,
                  password=password,
                  runas=runas).split('.')
    if len(ver) >= 2 and int(ver[0]) >= 9 and int(ver[1]) >= 1:
        query = (
            'SELECT rolname as "name", rolsuper as "superuser", '
            'rolinherit as "inherits privileges", '
            'rolcreaterole as "can create roles", '
            'rolcreatedb as "can create databases", '
            'rolcatupdate as "can update system catalogs", '
            'rolcanlogin as "can login", rolreplication as "replication", '
            'rolconnlimit as "connections", '
            'rolvaliduntil::timestamp(0) as "expiry time", '
            'rolconfig  as "defaults variables" '
            'FROM pg_roles'
        )
    else:
        query = (
            'SELECT rolname as "name", rolsuper as "superuser", '
            'rolinherit as "inherits privileges", '
            'rolcreaterole as "can create roles", '
            'rolcreatedb as "can create databases", '
            'rolcatupdate as "can update system catalogs", '
            'rolcanlogin as "can login", NULL as "replication", '
            'rolconnlimit as "connections", '
            'rolvaliduntil::timestamp(0) as "expiry time", '
            'rolconfig  as "defaults variables" '
            'FROM pg_roles'
        )

    rows = psql_query(query, runas=runas, host=host, user=user,
                      port=port, maintenance_db=maintenance_db,
                      password=password)

    def get_bool(rowdict, key):
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
        ret[row['name']] = retrow

    return ret


def user_exists(name, user=None, host=None, port=None, maintenance_db=None,
                password=None, runas=None):
    '''
    Checks if a user exists on the Postgres server.

    CLI Example::

        salt '*' postgres.user_exists 'username'
    '''

    return name in user_list(user=user,
                             host=host,
                             port=port,
                             maintenance_db=maintenance_db,
                             password=password,
                             runas=runas)


def _role_create(name,
                 login,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 superuser=False,
                 replication=False,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Creates a Postgres role. Users and Groups are both roles in postgres.
    However, users can login, groups cannot.
    '''

    if login:
        create_type = 'USER'
    else:
        create_type = 'ROLE'

    # check if role exists
    if user_exists(name, user, host, port, maintenance_db,
                   password=password, runas=runas):
        log.info('{0} \'{1}\' already exists'.format(create_type, name,))
        return False

    sub_cmd = 'CREATE {0} "{1}" WITH'.format(create_type, name, )
    if rolepassword is not None:
        if encrypted:
            sub_cmd = '{0} ENCRYPTED'.format(sub_cmd, )
        escaped_password = rolepassword.replace('\'', '\'\'')
        sub_cmd = '{0} PASSWORD \'{1}\''.format(sub_cmd, escaped_password)
    if createdb:
        sub_cmd = '{0} CREATEDB'.format(sub_cmd, )
    if createuser:
        sub_cmd = '{0} CREATEUSER'.format(sub_cmd, )
    if superuser:
        sub_cmd = '{0} SUPERUSER'.format(sub_cmd, )
    if replication:
        sub_cmd = '{0} REPLICATION'.format(sub_cmd, )
    if groups:
        sub_cmd = '{0} IN GROUP {1}'.format(sub_cmd, groups, )

    if sub_cmd.endswith('WITH'):
        sub_cmd = sub_cmd.replace(' WITH', '')

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port,
                    maintenance_db=maintenance_db, password=password)
    return _run_psql(cmd, runas=runas, password=password, host=host,
                     run_cmd="cmd.run")


def user_create(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                superuser=False,
                replication=False,
                rolepassword=None,
                groups=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password' rolepassword='rolepassword'
    '''
    return _role_create(username,
                        True,
                        user,
                        host,
                        port,
                        maintenance_db,
                        password,
                        createdb,
                        createuser,
                        encrypted,
                        superuser,
                        replication,
                        rolepassword,
                        groups,
                        runas)


def _role_update(name,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 replication=False,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Updates a postgres role.
    '''

    # check if user exists
    if not user_exists(name, user, host, port, maintenance_db, password,
                       runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    sub_cmd = 'ALTER ROLE {0} WITH'.format(name, )
    if rolepassword is not None:
        sub_cmd = '{0} PASSWORD \'{1}\''.format(sub_cmd, rolepassword)
    if createdb:
        sub_cmd = '{0} CREATEDB'.format(sub_cmd, )
    if createuser:
        sub_cmd = '{0} CREATEUSER'.format(sub_cmd, )
    if encrypted:
        sub_cmd = '{0} ENCRYPTED'.format(sub_cmd, )
    if replication:
        sub_cmd = '{0} REPLICATION'.format(sub_cmd, )

    if sub_cmd.endswith('WITH'):
        sub_cmd = sub_cmd.replace(' WITH', '')

    if groups:
        for group in groups.split(','):
            sub_cmd = '{0}; GRANT {1} TO {2}'.format(sub_cmd, group, name)

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port,
                    maintenance_db=maintenance_db, password=password)
    return _run_psql(cmd, runas=runas, password=password, host=host,
                     run_cmd="cmd.run")


def user_update(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                replication=False,
                rolepassword=None,
                groups=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password' rolepassword='rolepassword'
    '''
    return _role_update(username,
                        user,
                        host,
                        port,
                        maintenance_db,
                        password,
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        rolepassword,
                        groups,
                        runas)


def _role_remove(name, user=None, host=None, port=None, maintenance_db=None,
                 password=None, runas=None):
    '''
    Removes a role from the Postgres Server
    '''

    # check if user exists
    if not user_exists(name, user, host, port, maintenance_db,
                       password=password, runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE {0}'.format(name)
    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port,
                    maintenance_db=maintenance_db, password=password)
    _run_psql(cmd, runas=runas, password=password, host=host,
              run_cmd="cmd.run")
    if not user_exists(name, user, host, port, maintenance_db,
                       password=password, runas=runas):
        return True
    else:
        log.info('Failed to delete user \'{0}\'.'.format(name, ))
        return False


def user_remove(username,
                user=None,
                host=None,
                port=None,
                maintenance_db=None,
                password=None,
                runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example::

        salt '*' postgres.user_remove 'username'
    '''
    return _role_remove(username, user, host, port, maintenance_db,
                        password, runas)


# Group related actions

def group_create(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 superuser=False,
                 replication=False,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Creates a Postgres group. A group is postgres is similar to a user, but
    cannot login.

    CLI Example::

        salt '*' postgres.group_create 'groupname' user='user' host='hostname' port='port' password='password' rolepassword='rolepassword'
    '''
    return _role_create(groupname,
                        False,
                        user,
                        host,
                        port,
                        maintenance_db,
                        password,
                        createdb,
                        createuser,
                        encrypted,
                        superuser,
                        replication,
                        rolepassword,
                        groups,
                        runas)


def group_update(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 replication=False,
                 rolepassword=None,
                 groups=None,
                 runas=None):
    '''
    Updated a postgres group

    CLI Examples::

        salt '*' postgres.group_update 'username' user='user' host='hostname' port='port' password='password' rolepassword='rolepassword'
    '''
    return _role_update(groupname,
                        user,
                        host,
                        port,
                        maintenance_db,
                        password,
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        rolepassword,
                        groups,
                        runas)


def group_remove(groupname,
                 user=None,
                 host=None,
                 port=None,
                 maintenance_db=None,
                 password=None,
                 runas=None):
    '''
    Removes a group from the Postgres server.

    CLI Example::

        salt '*' postgres.group_remove 'groupname'
    '''
    return _role_remove(groupname, user, host, port, maintenance_db,
                        password, runas)

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

    CLI Example::

        salt '*' postgres.owner_to 'dbname' 'username'
    '''

    sqlfile = tempfile.NamedTemporaryFile()
    sqlfile.write('begin;\n')
    sqlfile.write('alter database {0} owner to {1};\n'.format(dbname, ownername))

    queries = (
        # schemas
        (
         'alter schema %(n)s owner to %(owner)s;',
         'select quote_ident(schema_name) as n from information_schema.schemata;'
         ),
        # tables and views
        (
         'alter table %(n)s owner to %(owner)s;',
         "select quote_ident(table_schema)||'.'||quote_ident(table_name) as n " +
            "from information_schema.tables where table_schema not in ('pg_catalog', 'information_schema');"
         ),
        # functions
        (
         'alter function %(n)s owner to %(owner)s;',
         "select p.oid::regprocedure::text as n from pg_catalog.pg_proc p " +
            "join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where ns.nspname not in ('pg_catalog', 'information_schema') " +
            " and not p.proisagg;"
         ),
        # aggregate functions
        (
         'alter aggregate %(n)s owner to %(owner)s;',
         "select p.oid::regprocedure::text as n from pg_catalog.pg_proc p " +
            "join pg_catalog.pg_namespace ns on p.pronamespace=ns.oid where ns.nspname not in ('pg_catalog', 'information_schema') " +
            " and p.proisagg;"
         ),
        # sequences
        (
         'alter sequence %(n)s owner to %(owner)s;',
         "select quote_ident(sequence_schema)||'.'||quote_ident(sequence_name) as n from information_schema.sequences;"
        )
    )

    for fmt, query in queries:
        ret = psql_query(query, user=user, host=host, port=port, maintenance_db=dbname,
                   password=password, runas=runas)
        for row in ret:
            line = fmt % {'owner': ownername, 'n': row['n']}
            sqlfile.write(line + "\n")

    sqlfile.write('commit;\n')
    sqlfile.flush()
    os.chmod(sqlfile.name, 0644) # ensure psql can read the file

    # run the generated sqlfile in the db
    cmd = _psql_cmd('-f', sqlfile.name, user=user, host=host, port=port,
                password=password, maintenance_db=dbname)
    cmdret = _run_psql(cmd, runas=runas, password=password)
    return cmdret
