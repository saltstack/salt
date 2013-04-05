'''
Module to provide Postgres compatibility to salt.

:configuration: In order to connect to Postgres, certain configuration is
    required in /etc/salt/minion on the relevant minions. Some sample configs
    might look like::

        postgres.host: 'localhost'
        postgres.port: '5432'
        postgres.user: 'postgres'
        postgres.pass: ''
        postgres.db: 'postgres'

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar
'''

# Import python libs
import datetime
import pipes
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the psql bin exists
    '''
    if salt.utils.which('psql'):
        return 'postgres'
    return False


def _get_runas(runas=None):
    '''
    Returns the default runas user for this platform
    '''
    if runas is not None:
        return runas

    if 'FreeBSD' in __grains__['os_family']:
        return 'pgsql'
    else:
        return 'postgres'


def _run_psql(cmd, runas=None, password=None, run_cmd="cmd.run_all"):
    '''
    Helper function to call psql, because the password requirement
    makes this too much code to be repeated in each function below
    '''
    kwargs = {"runas": _get_runas(runas)}

    if not password:
        password = __salt__['config.option']('postgres.pass')
    if password:
        kwargs["env"] = {"PGPASSWORD": password}
        # PGPASSWORD has been deprecated, supposedly leading to
        # protests. Currently, this seems the simplest way to solve
        # this. If needed in the future, a tempfile could also be
        # written and the filename set to the PGPASSFILE variable. see
        # http://www.postgresql.org/docs/8.4/static/libpq-pgpass.html

    return __salt__[run_cmd](cmd, **kwargs)


def version(user=None, host=None, port=None, db=None, password=None,
            runas=None):
    '''
    Return the version of a Postgres server.

    CLI Example::

        salt '*' postgres.version
    '''
    query = 'SELECT setting FROM pg_catalog.pg_settings ' \
            'WHERE name = \'server_version\''
    cmd = _psql_cmd('-c', query, '-t',
                    host=host, user=user, port=port, db=db, password=password)
    ret = _run_psql(cmd, runas=runas, password=password)

    for line in ret['stdout'].splitlines():
        return line


def _connection_defaults(user=None, host=None, port=None, db=None,
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
    if not db:
        db = __salt__['config.option']('postgres.db')
    if not password:
        password = __salt__['config.option']('postgres.pass')

    return (user, host, port, db, password)


def _psql_cmd(*args, **kwargs):
    '''
    Return string with fully composed psql command.

    Accept optional keyword arguments: user, host and port as well as any
    number or positional arguments to be added to the end of command.
    '''
    (user, host, port, db, password) = _connection_defaults(
        kwargs.get('user'),
        kwargs.get('host'),
        kwargs.get('port'),
        kwargs.get('db'),
        kwargs.get('password'))

    cmd = [salt.utils.which('psql'),
           '--no-align',
           '--no-readline']
    if not password:
        cmd += ['--no-password']
    if user:
        cmd += ['--username', user]
    if host:
        cmd += ['--host', host]
    if port:
        cmd += ['--port', port]
    if db:
        cmd += ['--dbname', db]
    cmd += args
    cmdstr = ' '.join(map(pipes.quote, cmd))
    return cmdstr


# Database related actions

def db_list(user=None, host=None, port=None, db=None,
            password=None, runas=None):
    '''
    Return dictionary with information about databases of a Postgres server.

    CLI Example::

        salt '*' postgres.db_list
    '''

    ret = {}
    header = ['Name',
              'Owner',
              'Encoding',
              'Collate',
              'Ctype',
              'Access privileges']

    query = 'SELECT datname as "Name", pga.rolname as "Owner", ' \
            'pg_encoding_to_char(encoding) as "Encoding", ' \
            'datcollate as "Collate", datctype as "Ctype", ' \
            'datacl as "Access privileges" FROM pg_database pgd, ' \
            'pg_roles pga WHERE pga.oid = pgd.datdba'

    cmd = _psql_cmd('-c', query, '-t',
                    host=host, user=user, port=port, db=db, password=password)

    cmdret = _run_psql(cmd, runas=runas, password=password)

    if cmdret['retcode'] > 0:
        return ret

    for line in cmdret['stdout'].splitlines():
        if line.count('|') != 5:
            log.warning('Unexpected string: {0}'.format(line))
            continue
        comps = line.split('|')
        ret[comps[0]] = dict(zip(header[1:], comps[1:]))

    return ret


def db_exists(name, user=None, host=None, port=None, db=None, password=None,
              runas=None):
    '''
    Checks if a database exists on the Postgres server.

    CLI Example::

        salt '*' postgres.db_exists 'dbname'
    '''

    databases = db_list(user=user, host=host, port=port, db=db,
                        password=password, runas=runas)
    return name in databases


def db_create(name,
              user=None,
              host=None,
              port=None,
              db=None,
              password=None,
              tablespace=None,
              encoding=None,
              locale=None,
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
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port, db=db,
                    password=password)
    ret = _run_psql(cmd, runas=runas, password=password)

    return ret['retcode'] == 0


def db_remove(name, user=None, host=None, port=None, db=None,
              password=None, runas=None):
    '''
    Removes a databases from the Postgres server.

    CLI Example::

        salt '*' postgres.db_remove 'dbname'
    '''

    # db doesnt exist, proceed
    query = 'DROP DATABASE {0}'.format(name)
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port, db=db,
                    password=password)
    ret = _run_psql(cmd, runas=runas, password=password)
    return ret['retcode'] == 0


# User related actions

def user_list(user=None, host=None, port=None, db=None,
              password=None, runas=None):
    '''
    Return a dict with information about users of a Postgres server.

    CLI Example::

        salt '*' postgres.user_list
    '''

    ret = {}
    header = ['name',
              'superuser',
              'inherits privileges',
              'can create roles',
              'can create databases',
              'can update system catalogs',
              'can login',
              'replication',
              'connections',
              'expiry time',
              'defaults variables']

    ver = version(user=user,
                  host=host,
                  port=port,
                  db=db,
                  password=password,
                  runas=runas).split('.')
    if len(ver) >= 2 and int(ver[0]) >= 9 and int(ver[1]) >= 1:
        query = (
            'SELECT rolname, rolsuper, rolinherit, rolcreaterole, '
            'rolcreatedb, rolcatupdate, rolcanlogin, rolreplication, '
            'rolconnlimit, rolvaliduntil::timestamp(0), rolconfig '
            'FROM pg_roles'
        )
    else:
        query = (
            'SELECT rolname, rolsuper, rolinherit, rolcreaterole, '
            'rolcreatedb, rolcatupdate, rolcanlogin, NULL, '
            'rolconnlimit, rolvaliduntil::timestamp(0), rolconfig '
            'FROM pg_roles'
        )
    cmd = _psql_cmd('-c', query, '-t',
                    host=host, user=user, port=port, db=db, password=password)

    cmdret = _run_psql(cmd, runas=runas, password=password)

    if cmdret['retcode'] > 0:
        return ret

    for line in cmdret['stdout'].splitlines():
        comps = line.split('|')
        # type casting
        for i in range(1, 8):
            if comps[i] == 't':
                comps[i] = True
            elif comps[i] == 'f':
                comps[i] = False
            else:
                comps[i] = None
        comps[8] = int(comps[8])
        if comps[9]:
            comps[9] = datetime.datetime.strptime(
                comps[9], '%Y-%m-%d %H:%M:%S'
            )
        else:
            comps[9] = None
        if not comps[10]:
            comps[10] = None
        ret[comps[0]] = dict(zip(header[1:], comps[1:]))

    return ret


def user_exists(name, user=None, host=None, port=None, db=None,
                password=None, runas=None):
    '''
    Checks if a user exists on the Postgres server.

    CLI Example::

        salt '*' postgres.user_exists 'username'
    '''

    return name in user_list(user=user,
                             host=host,
                             port=port,
                             db=db,
                             password=password,
                             runas=runas)


def _role_create(name,
                 login,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
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
    if user_exists(name, user, host, port, db, password=password, runas=runas):
        log.info('{0} \'{1}\' already exists'.format(create_type, name,))
        return False

    sub_cmd = 'CREATE {0} "{1}" WITH'.format(create_type, name, )
    if rolepassword:
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

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db,
                    password=password)
    return _run_psql(cmd, runas=runas, password=password, run_cmd="cmd.run")


def user_create(username,
                user=None,
                host=None,
                port=None,
                db=None,
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
                        db,
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
                 db=None,
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
    if not user_exists(name, user, host, port, db, password, runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    sub_cmd = 'ALTER ROLE {0} WITH'.format(name, )
    if rolepassword:
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

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db,
                    password=password)
    return _run_psql(cmd, runas=runas, password=password, run_cmd="cmd.run")


def user_update(username,
                user=None,
                host=None,
                port=None,
                db=None,
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
                        db,
                        password,
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        rolepassword,
                        groups,
                        runas)


def _role_remove(name, user=None, host=None, port=None, db=None,
                 password=None, runas=None):
    '''
    Removes a role from the Postgres Server
    '''

    # check if user exists
    if not user_exists(name, user, host, port, db, password=password,
                       runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE {0}'.format(name)
    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db,
                    password=password)
    _run_psql(cmd, runas=runas, password=password, run_cmd="cmd.run")
    if not user_exists(name, user, host, port, db, password=password, runas=runas):
        return True
    else:
        log.info('Failed to delete user \'{0}\'.'.format(name, ))


def user_remove(username,
                user=None,
                host=None,
                port=None,
                db=None,
                password=None,
                runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example::

        salt '*' postgres.user_remove 'username'
    '''
    return _role_remove(username, user, host, port, db, password, runas)


# Group related actions

def group_create(groupname,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
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
                        db,
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
                 db=None,
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
                        db,
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
                 db=None,
                 password=None,
                 runas=None):
    '''
    Removes a group from the Postgres server.

    CLI Example::

        salt '*' postgres.group_remove 'groupname'
    '''
    return _role_remove(groupname, user, host, port, db, password, runas)
