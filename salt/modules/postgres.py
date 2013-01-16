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
from salt.utils import check_or_die
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
    from the ``psql --version`` cmd.

    CLI Example::

        salt '*' postgres.version
    '''
    version_line =  __salt__['cmd.run']('psql --version').split("\n")[0]
    name = version_line.split(" ")[1]
    ver = version_line.split(" ")[2]
    return '{0} {1}'.format(name, ver)

def _connection_defaults(user=None, host=None, port=None):
    '''
    Returns a tuple of (user, host, port) with config, pillar, or default
    values assigned to missing values.
    '''
    if not user:
        user = __salt__['config.option']('postgres.user')
    if not host:
        host = __salt__['config.option']('postgres.host')
    if not port:
        port = __salt__['config.option']('postgres.port')

    return (user, host, port)

def _psql_cmd(*args, **kwargs):
    '''
    Return string with fully composed psql command.

    Accept optional keyword arguments: user, host and port as well as any
    number or positional arguments to be added to the end of command.
    '''
    (user, host, port) = _connection_defaults(kwargs.get('user'),
                                              kwargs.get('host'),
                                              kwargs.get('port'))
    cmd = ['psql', '--no-align', '--no-readline', '--no-password']
    if user:
        cmd += ['--username', user]
    if host:
        cmd += ['--host', host]
    if port:
        cmd += ['--port', port]
    cmd += args
    cmdstr = ' '.join(map(pipes.quote, cmd))
    return cmdstr


# Database related actions

def db_list(user=None, host=None, port=None, runas=None):
    '''
    Return a list of databases of a Postgres server using the output
    from the ``psql -l`` query.

    CLI Example::

        salt '*' postgres.db_list
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    ret = []
    query = """SELECT datname as "Name", pga.rolname as "Owner", """ \
    """pg_encoding_to_char(encoding) as "Encoding", datcollate as "Collate", datctype as "Ctype", """ \
    """datacl as "Access privileges" FROM pg_database pgd, pg_authid pga WHERE pga.oid = pgd.datdba"""

    cmd = _psql_cmd('-c', query,
            host=host, user=user, port=port)

    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    lines = [x for x in cmdret.splitlines() if len(x.split("|")) == 6]
    if not lines:
        log.error("no results from postgres.db_list")
    else:
        log.debug(lines)
        header = [x.strip() for x in lines[0].split("|")]
        for line in lines[1:]:
            line = [x.strip() for x in line.split("|")]
            if not line[0] == "":
                ret.append(list(zip(header[:-1], line[:-1])))

    return ret


def db_exists(name, user=None, host=None, port=None, runas=None):
    '''
    Checks if a database exists on the Postgres server.

    CLI Example::

        salt '*' postgres.db_exists 'dbname'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    databases = db_list(user=user, host=host, port=port, runas=runas)
    for database in databases:
        if name == dict(database).get('Name'):
            return True

    return False


def db_create(name,
              user=None,
              host=None,
              port=None,
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
    (user, host, port) = _connection_defaults(user, host, port)

    # check if db exists
    if db_exists(name, user, host, port, runas=runas):
        log.info("DB '{0}' already exists".format(name,))
        return False

    # check if template exists
    if template:
        if not db_exists(template, user, host, port, runas=runas):
            log.info("template '{0}' does not exist.".format(template, ))
            return False

    # Base query to create a database
    query = 'CREATE DATABASE "{0}"'.format(name)

    # "With"-options to create a database
    with_args = {
        # owner needs to be enclosed in double quotes so postgres
        # doesn't get thrown by dashes in the name
        'OWNER': owner and '"{0}"'.format(owner),
        'TEMPLATE': template,
        'ENCODING': encoding and "'{0}'".format(encoding),
        'LC_COLLATE': lc_collate and "'{0}'".format(lc_collate),
        'LC_CTYPE': lc_ctype and "'{0}'".format(lc_ctype),
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
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port)
    __salt__['cmd.run'](cmd, runas=runas)

    # Check the result
    if db_exists(name, user, host, port, runas=runas):
        return True
    else:
        log.info("Failed to create DB '{0}'".format(name,))
        return False


def db_remove(name, user=None, host=None, port=None, runas=None):
    '''
    Removes a databases from the Postgres server.

    CLI Example::

        salt '*' postgres.db_remove 'dbname'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    # check if db exists
    if not db_exists(name, user, host, port, runas=runas):
        log.info("DB '{0}' does not exist".format(name,))
        return False

    # db doesnt exist, proceed
    query = 'DROP DATABASE {0}'.format(name)
    cmd = _psql_cmd('-c', query, user=user, host=host, port=port)
    __salt__['cmd.run'](cmd, runas=runas)
    if not db_exists(name, user, host, port, runas=runas):
        return True
    else:
        log.info("Failed to delete DB '{0}'.".format(name, ))
        return False

# User related actions

def user_list(user=None, host=None, port=None, runas=None):
    '''
    Return a list of users of a Postgres server.

    CLI Example::

        salt '*' postgres.user_list
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    ret = []
    query = (
        '''SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb,
        rolcatupdate, rolcanlogin, rolreplication, rolconnlimit, rolvaliduntil, rolconfig, oid
        FROM pg_roles'''
    )
    cmd = _psql_cmd('-c', query,
            host=host, user=user, port=port)

    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    lines = [x for x in cmdret.splitlines() if len(x.split("|")) == 12]
    log.debug(lines)
    header = [x.strip() for x in lines[0].split("|")]
    for line in lines[1:]:
        line = [x.strip() for x in line.split("|")]
        if not line[0] == "":
            ret.append(list(zip(header[:-1], line[:-1])))

    return ret

def user_exists(name, user=None, host=None, port=None, runas=None):
    '''
    Checks if a user exists on the Postgres server.

    CLI Example::

        salt '*' postgres.user_exists 'username'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    query = (
        "SELECT true "
        "FROM pg_roles "
        "WHERE EXISTS "
        "(SELECT rolname WHERE rolname='{role}')".format(role=name)
    )
    cmd = _psql_cmd('-c', query, host=host, user=user, port=port)
    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    log.debug(cmdret.splitlines())
    try:
        val = cmdret.splitlines()[1]
    except IndexError:
        log.error("Invalid PostgreSQL result: '%s'", cmdret)
        return False
    return True if val.strip() == 't' else False

def _role_create(name,
                 login,
                 user=None,
                 host=None,
                 port=None,
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
    (user, host, port) = _connection_defaults(user, host, port)

    if login:
        create_type = 'USER'
    else:
        create_type = 'ROLE'

    # check if role exists
    if user_exists(name, user, host, port, runas=runas):
        log.info("{0} '{1}' already exists".format(create_type, name,))
        return False

    sub_cmd = 'CREATE {0} "{1}" WITH'.format(create_type, name, )
    if password:
        if encrypted:
            sub_cmd = "{0} ENCRYPTED".format(sub_cmd, )
        escaped_password = password.replace("'", "''")
        sub_cmd = "{0} PASSWORD '{1}'".format(sub_cmd, escaped_password)
    if createdb:
        sub_cmd = "{0} CREATEDB".format(sub_cmd, )
    if createuser:
        sub_cmd = "{0} CREATEUSER".format(sub_cmd, )
    if superuser:
        sub_cmd = "{0} SUPERUSER".format(sub_cmd, )
    if replication:
        sub_cmd = "{0} REPLICATION".format(sub_cmd, )
    if groups:
        sub_cmd = "{0} IN GROUP {1}".format(sub_cmd, groups, )

    if sub_cmd.endswith("WITH"):
        sub_cmd = sub_cmd.replace(" WITH", "")

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    return __salt__['cmd.run'](cmd, runas=runas)

def user_create(username,
                user=None,
                host=None,
                port=None,
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
    (user, host, port) = _connection_defaults(user, host, port)

    # check if user exists
    if not user_exists(name, user, host, port, runas=runas):
        log.info("User '{0}' does not exist".format(name,))
        return False

    sub_cmd = "ALTER ROLE {0} WITH".format(name, )
    if password:
        sub_cmd = "{0} PASSWORD '{1}'".format(sub_cmd, password)
    if createdb:
        sub_cmd = "{0} CREATEDB".format(sub_cmd, )
    if createuser:
        sub_cmd = "{0} CREATEUSER".format(sub_cmd, )
    if encrypted:
        sub_cmd = "{0} ENCRYPTED".format(sub_cmd, )
    if encrypted:
        sub_cmd = "{0} REPLICATION".format(sub_cmd, )

    if sub_cmd.endswith("WITH"):
        sub_cmd = sub_cmd.replace(" WITH", "")

    if groups:
        for group in groups.split(','):
            sub_cmd = "{0}; GRANT {1} TO {2}".format(sub_cmd, group, name)

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    return __salt__['cmd.run'](cmd, runas=runas)

def user_update(username,
                user=None,
                host=None,
                port=None,
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
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        password,
                        groups,
                        runas)

def _role_remove(name, user=None, host=None, port=None, runas=None):
    '''
    Removes a role from the Postgres Server
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    # check if user exists
    if not user_exists(name, user, host, port, runas=runas):
        log.info("User '{0}' does not exist".format(name,))
        return False

    # user exists, proceed
    sub_cmd = 'DROP ROLE {0}'.format(name)
    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    __salt__['cmd.run'](cmd, runas=runas)
    if not user_exists(name, user, host, port, runas=runas):
        return True
    else:
        log.info("Failed to delete user '{0}'.".format(name, ))

def user_remove(username, user=None, host=None, port=None, runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example::

        salt '*' postgres.user_remove 'username'
    '''
    return _role_remove(username, user, host, port, runas)

# Group related actions

def group_create(groupname,
                 user=None,
                 host=None,
                 port=None,
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
                        createdb,
                        createuser,
                        encrypted,
                        replication,
                        password,
                        groups,
                        runas)

def group_remove(groupname, user=None, host=None, port=None, runas=None):
    '''
    Removes a group from the Postgres server.

    CLI Example::

        salt '*' postgres.group_remove 'groupname'
    '''
    return _role_remove(groupname, user, host, port, runas)
