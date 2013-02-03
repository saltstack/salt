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
import pipes
import logging

# Import salt libs
from salt.utils import check_or_die, which
from salt.exceptions import CommandNotFoundError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the psql bin exists
    '''
    try:
        check_or_die('psql')
        return 'postgres'
    except CommandNotFoundError:
        return False


def version():
    '''
    Return the version of a Postgres server using the output
    from the ``postgres --version`` cmd.

    CLI Example::

        salt '*' postgres.version
    '''
    cmd = '{0} --version'.format(which('postgres'))
    for line in __salt__['cmd.run'](cmd).splitlines():
        return line.split()[-1]


def _connection_defaults(user=None, host=None, port=None, db=None):
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

    return (user, host, port, db)


def _psql_cmd(*args, **kwargs):
    '''
    Return string with fully composed psql command.

    Accept optional keyword arguments: user, host and port as well as any
    number or positional arguments to be added to the end of command.
    '''
    (user, host, port, db) = _connection_defaults(kwargs.get('user'),
                                                  kwargs.get('host'),
                                                  kwargs.get('port'),
                                                  kwargs.get('db'))
    cmd = [which('psql'), '--no-align', '--no-readline', '--no-password']
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

def db_list(user=None, host=None, port=None, db=None, runas=None):
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
            'pg_authid pga WHERE pga.oid = pgd.datdba'

    cmd = _psql_cmd('-c', query, '-t',
                    host=host, user=user, port=port, db=db)

    cmdret = __salt__['cmd.run_all'](cmd, runas=runas)

    if cmdret['retcode'] > 0:
        return ret

    for line in cmdret['stdout'].splitlines():
        if line.count('|') != 5:
            log.warning('Unexpected string: {0}'.format(line))
            continue
        comps = line.split('|')
        ret[comps[0]] = dict(zip(header[1:], comps[1:]))

    return ret


def db_exists(name, user=None, host=None, port=None, db=None, runas=None):
    '''
    Checks if a database exists on the Postgres server.

    CLI Example::

        salt '*' postgres.db_exists 'dbname'
    '''

    databases = db_list(user=user, host=host, port=port, db=db, runas=runas)
    return name in databases


def db_create(name,
              user=None,
              host=None,
              port=None,
              db=None,
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
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port, db=db)
    ret = __salt__['cmd.run_all'](cmd, runas=runas)

    return ret['retcode'] == 0


def db_remove(name, user=None, host=None, port=None, db=None, runas=None):
    '''
    Removes a databases from the Postgres server.

    CLI Example::

        salt '*' postgres.db_remove 'dbname'
    '''

    # check if db exists
    if not db_exists(name, user, host, port, db, runas=runas):
        log.info('DB \'{0}\' does not exist'.format(name,))
        return False

    # db doesnt exist, proceed
    query = 'DROP DATABASE {0}'.format(name)
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port, db=db)
    __salt__['cmd.run'](cmd, runas=runas)
    if not db_exists(name, user, host, port, db, runas=runas):
        return True
    else:
        log.info('Failed to delete DB \'{0}\'.'.format(name, ))
        return False


# User related actions

def user_list(user=None, host=None, port=None, db=None, runas=None):
    '''
    Return a list of users of a Postgres server.

    CLI Example::

        salt '*' postgres.user_list
    '''

    ret = []
    query = (
        '''SELECT rolname, rolsuper, rolinherit, rolcreaterole,
        rolcreatedb, rolcatupdate, rolcanlogin, rolreplication,
        rolconnlimit, rolvaliduntil, rolconfig, oid
        FROM pg_roles'''
    )
    cmd = _psql_cmd('-c', query,
                    host=host, user=user, port=port, db=db)

    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    lines = [x for x in cmdret.splitlines() if len(x.split('|')) == 12]
    log.debug(lines)
    header = [x.strip() for x in lines[0].split('|')]
    for line in lines[1:]:
        line = [x.strip() for x in line.split('|')]
        if not line[0] == '':
            ret.append(list(zip(header[:-1], line[:-1])))

    return ret


def user_exists(name, user=None, host=None, port=None, db=None, runas=None):
    '''
    Checks if a user exists on the Postgres server.

    CLI Example::

        salt '*' postgres.user_exists 'username'
    '''

    query = (
        'SELECT true '
        'FROM pg_roles '
        'WHERE EXISTS '
        '(SELECT rolname WHERE rolname=\'{role}\')'.format(role=name)
    )
    cmd = _psql_cmd('-c', query, host=host, user=user, port=port, db=db)
    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    log.debug(cmdret.splitlines())
    try:
        val = cmdret.splitlines()[1]
    except IndexError:
        log.error('Invalid PostgreSQL result: \'%s\'', cmdret)
        return False
    return True if val.strip() == 't' else False


def _role_create(name,
                 login,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 superuser=False,
                 replication=False,
                 password=None,
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
    if user_exists(name, user, host, port, db, runas=runas):
        log.info('{0} \'{1}\' already exists'.format(create_type, name,))
        return False

    sub_cmd = 'CREATE {0} "{1}" WITH'.format(create_type, name, )
    if password:
        if encrypted:
            sub_cmd = '{0} ENCRYPTED'.format(sub_cmd, )
        escaped_password = password.replace('\'', '\'\'')
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

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db)
    return __salt__['cmd.run'](cmd, runas=runas)


def user_create(username,
                user=None,
                host=None,
                port=None,
                db=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                superuser=False,
                replication=False,
                password=None,
                groups=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password'
    '''
    return _role_create(username,
                        True,
                        user,
                        host,
                        port,
                        db,
                        createdb,
                        createuser,
                        encrypted,
                        superuser,
                        replication,
                        password,
                        groups,
                        runas)


def _role_update(name,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 replication=False,
                 password=None,
                 groups=None,
                 runas=None):
    '''
    Updates a postgres role.
    '''

    # check if user exists
    if not user_exists(name, user, host, port, db, runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    sub_cmd = 'ALTER ROLE {0} WITH'.format(name, )
    if password:
        sub_cmd = '{0} PASSWORD \'{1}\''.format(sub_cmd, password)
    if createdb:
        sub_cmd = '{0} CREATEDB'.format(sub_cmd, )
    if createuser:
        sub_cmd = '{0} CREATEUSER'.format(sub_cmd, )
    if encrypted:
        sub_cmd = '{0} ENCRYPTED'.format(sub_cmd, )
    if encrypted:
        sub_cmd = '{0} REPLICATION'.format(sub_cmd, )

    if sub_cmd.endswith('WITH'):
        sub_cmd = sub_cmd.replace(' WITH', '')

    if groups:
        for group in groups.split(','):
            sub_cmd = '{0}; GRANT {1} TO {2}'.format(sub_cmd, group, name)

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db)
    return __salt__['cmd.run'](cmd, runas=runas)


def user_update(username,
                user=None,
                host=None,
                port=None,
                db=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                replication=False,
                password=None,
                groups=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password'
    '''
    return _role_update(username,
                        user,
                        host,
                        port,
                        db,
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        password,
                        groups,
                        runas)


def _role_remove(name, user=None, host=None, port=None, db=None, runas=None):
    '''
    Removes a role from the Postgres Server
    '''

    # check if user exists
    if not user_exists(name, user, host, port, db, runas=runas):
        log.info('User \'{0}\' does not exist'.format(name,))
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE {0}'.format(name)
    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port, db=db)
    __salt__['cmd.run'](cmd, runas=runas)
    if not user_exists(name, user, host, port, db, runas=runas):
        return True
    else:
        log.info('Failed to delete user \'{0}\'.'.format(name, ))


def user_remove(username,
                user=None,
                host=None,
                port=None,
                db=None,
                runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example::

        salt '*' postgres.user_remove 'username'
    '''
    return _role_remove(username, user, host, port, db, runas)


# Group related actions

def group_create(groupname,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 superuser=False,
                 replication=False,
                 password=None,
                 groups=None,
                 runas=None):
    '''
    Creates a Postgres group. A group is postgres is similar to a user, but
    cannot login.

    CLI Example::

        salt '*' postgres.group_create 'groupname' user='user' host='hostname' port='port' password='password'
    '''
    return _role_create(groupname,
                        False,
                        user,
                        host,
                        port,
                        db,
                        createdb,
                        createuser,
                        encrypted,
                        superuser,
                        replication,
                        password,
                        groups,
                        runas)


def group_update(groupname,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
                 createdb=False,
                 createuser=False,
                 encrypted=False,
                 replication=False,
                 password=None,
                 groups=None,
                 runas=None):
    '''
    Updated a postgres group

    CLI Examples::

        salt '*' postgres.group_update 'username' user='user' host='hostname' port='port' password='password'
    '''
    return _role_update(groupname,
                        user,
                        host,
                        port,
                        db,
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        password,
                        groups,
                        runas)


def group_remove(groupname,
                 user=None,
                 host=None,
                 port=None,
                 db=None,
                 runas=None):
    '''
    Removes a group from the Postgres server.

    CLI Example::

        salt '*' postgres.group_remove 'groupname'
    '''
    return _role_remove(groupname, user, host, port, db, runas)
