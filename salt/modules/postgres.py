'''
Module to provide Postgres compatibility to salt.

In order to connect to Postgres, certain configuration is required
in /etc/salt/minion on the relevant minions. Some sample configs
might look like::

    postgres.host: 'localhost'
    postgres.port: '5432'
    postgres.user: 'postgres'
    postgres.pass: ''
    postgres.db: 'postgres'

This data can also be passed into pillar. Options passed into opts will
overwrite options passed into pillar
'''

# Import Python libs
import pipes
import logging

# Import Salt libs
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
    cmd = _psql_cmd('-l', user=user, host=host, port=port)
    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    lines = [x for x in cmdret.splitlines() if len(x.split("|")) == 6]
    try:
        header = [x.strip() for x in lines[0].split("|")]
    except IndexError:
        log.error("Invalid PostgreSQL output: '%s'", cmdret)
        return []
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
    for db in databases:
        if name == dict(db).get('Name'):
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
    for k, v in with_args.iteritems():
        if v is not None:
            with_chunks += [k, '=', v]
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
        rolcatupdate, rolcanlogin, rolconnlimit, rolvaliduntil, rolconfig, oid
        FROM pg_roles'''
    )
    cmd = _psql_cmd('-c', query,
            host=host, user=user, port=port)

    cmdret = __salt__['cmd.run'](cmd, runas=runas)
    lines = [x for x in cmdret.splitlines() if len(x.split("|")) == 11]
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


def user_create(username,
                user=None,
                host=None,
                port=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                superuser=False,
                password=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    # check if user exists
    if user_exists(username, user, host, port, runas=runas):
        log.info("User '{0}' already exists".format(username,))
        return False

    sub_cmd = 'CREATE USER "{0}" WITH'.format(username, )
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

    if sub_cmd.endswith("WITH"):
        sub_cmd = sub_cmd.replace(" WITH", "")

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    return __salt__['cmd.run'](cmd, runas=runas)

def user_update(username,
                user=None,
                host=None,
                port=None,
                createdb=False,
                createuser=False,
                encrypted=False,
                password=None,
                runas=None):
    '''
    Creates a Postgres user.

    CLI Examples::

        salt '*' postgres.user_create 'username' user='user' host='hostname' port='port' password='password'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    # check if user exists
    if not user_exists(username, user, host, port, runas=runas):
        log.info("User '{0}' does not exist".format(username,))
        return False

    sub_cmd = "ALTER USER {0} WITH".format(username, )
    if password:
        sub_cmd = "{0} PASSWORD '{1}'".format(sub_cmd, password)
    if createdb:
        sub_cmd = "{0} CREATEDB".format(sub_cmd, )
    if createuser:
        sub_cmd = "{0} CREATEUSER".format(sub_cmd, )
    if encrypted:
        sub_cmd = "{0} ENCRYPTED".format(sub_cmd, )

    if sub_cmd.endswith("WITH"):
        sub_cmd = sub_cmd.replace(" WITH", "")

    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    return __salt__['cmd.run'](cmd, runas=runas)

def user_remove(username, user=None, host=None, port=None, runas=None):
    '''
    Removes a user from the Postgres server.

    CLI Example::

        salt '*' postgres.user_remove 'username'
    '''
    (user, host, port) = _connection_defaults(user, host, port)

    # check if user exists
    if not user_exists(username, user, host, port, runas=runas):
        log.info("User '{0}' does not exist".format(username,))
        return False

    # user exists, proceed
    sub_cmd = 'DROP USER {0}'.format(username)
    cmd = _psql_cmd('-c', sub_cmd, host=host, user=user, port=port)
    __salt__['cmd.run'](cmd, runas=runas)
    if not user_exists(username, user, host, port, runas=runas):
        return True
    else:
        log.info("Failed to delete user '{0}'.".format(username, ))
        return False
