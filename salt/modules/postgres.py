'''
Module to provide MySQL compatibility to salt.

In order to connect to MySQL, certain configuration is required
in /etc/salt/minion on the relevant minions. Some sample configs
might look like::

    postgres.host: 'localhost'
    postgres.port: 3306
    postgres.user: 'root'
    postgres.pass: ''
    postgres.db: 'mysql'

You can also use a defaults file::

    mysql.default_file: '/etc/mysql/debian.cnf'

Required python modules: MySQLdb
'''

import logging

log = logging.getLogger(__name__)
__opts__ = {}


def version():
    '''
    Return the version of a MySQL server using the output
    from the ``SELECT VERSION()`` query.

    CLI Example::

        salt '*' postgres.version
    '''
    version_line =  __salt__['cmd.run']('psql --version').split("\n")[0]
    name = version_line.split(" ")[1]
    ver = version_line.split(" ")[2]
    print "{0} {1}".format(name, ver)
    return "{0} {1}".format(name, ver)

'''
Database related actions
'''


def db_list(user, host):
    '''
    Return a list of databases of a MySQL server using the output
    from the ``SHOW DATABASES`` query.

    CLI Example::

        salt '*' postgres.db_list
    '''
    cmd = "psql -l -U {user} -h {host}".format(
        user=user, host=host)

    __salt__['cmd.run'](cmd)


def db_exists(user, host, name):
    '''
    Checks if a database exists on the MySQL server.

    CLI Example::

        salt '*' mysql.db_exists 'dbname'
    '''
    databases = __salt__['postgres.db_list'](user, host)
    return name in databases


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


