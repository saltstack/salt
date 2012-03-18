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

'''

import logging

log = logging.getLogger(__name__)
__opts__ = {}


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
    return "%s %s" % (name, ver)


'''
Database related actions
'''


def db_list(user=None, host=None):
    '''
    Return a list of databases of a MySQL server using the output
    from the ``psql -l`` query.

    CLI Example::

        salt '*' postgres.db_list
    '''
    if not user:
        user = __opts__['postgres.user']
    if not host:
        host = __opts__['postgres.host']

    ret = []
    cmd = "psql -l -U {user} -h {host}".format(
        user=user, host=host)
    lines = [x for x in __salt__['cmd.run'](cmd).split("\n") if len(x.split("|")) == 6]
    header = [x.strip() for x in lines[0].split("|")]
    for line in lines[1:]:
        line = [x.strip() for x in line.split("|")]
        if not line[0] == "":        
            ret.append(zip(header[:-1], line[:-1]))

    return ret

def db_exists(name, user=None, host=None):
    '''
    Checks if a database exists on the MySQL server.

    CLI Example::

        salt '*' mysql.db_exists 'dbname'
    '''
    databases = __salt__['postgres.db_list'](user, host)
    for db in databases:
        if name == dict(db).get('Name'):
            return True

    return False


def db_create(user, host, name, **kwargs):
    '''
    Adds a databases to the MySQL server.

    CLI Example::

        salt '*' mysql.db_create 'dbname'
    '''
    # check if db exists
    if db_exists(name):
        log.info("DB '{0}' already exists".format(name,))
        return False

    cmd = 'create_db {name} '.format(name)
    for param, value in kwargs.iteritems():
        cmd = '{cmd} {param} {value} '.format(
            cmd=cmd, param=param, value=value)

    __salt__['cmd.run'](cmd)


def db_remove(name):
    '''
    Removes a databases from the MySQL server.

    CLI Example::

        salt '*' mysql.db_remove 'dbname'
    '''
    # check if db exists
    if not db_exists(name):
        log.info("DB '{0}' does not exist".format(name,))
        return False

    # db doesnt exist, proceed
    cmd = 'dropdb {name} '.format(name)
    __salt__['cmd.run'](cmd)


'''
User related actions
'''
def user_create(user,
                host='localhost',
                password=None,
                password_hash=None):
    '''
    Creates a MySQL user.

    CLI Examples::

        salt '*' mysql.user_create 'username' 'hostname' 'password

        salt '*' mysql.user_create 'username' 'hostname' password_hash='hash'
    '''
    pass


