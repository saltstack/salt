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


def version(user, password):
    '''
    Return the version of a MySQL server using the output
    from the ``SELECT VERSION()`` query.

    CLI Example::

        salt '*' postgres.version
    '''
    __salt__['cmd.run']('psql --version')


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
    if user_exists(user,host):
       log.info("User '{0}'@'{1}' already exists".format(user,host,))
       return False

    db = connect()
    cur = db.cursor ()
    query = "CREATE USER '%s'@'%s'" % (user, host,)
    if password is not None:
        query = query + " IDENTIFIED BY '%s'" % password
    elif password_hash is not None:
        query = query + " IDENTIFIED BY PASSWORD '%s'" % password_hash

    log.debug("Query: {0}".format(query,))
    cur.execute( query )

    if user_exists(user,host):
        log.info("User '{0}'@'{1}' has been created".format(user,host,))
        return True

    log.info("User '{0}'@'{1}' is not created".format(user,host,))
    return False

def user_chpass(user,
                host='localhost',
                password=None,
                password_hash=None):
    '''
    Change password for MySQL user

    CLI Examples::

        salt '*' mysql.user_chpass frank localhost newpassword

        salt '*' mysql.user_chpass frank localhost password_hash='hash'
    '''
    if password is None or password_hash is None:
        log.error('No password provided')
        return False
    elif password is not None:
        password_sql = "PASSWORD(\"%s\")" % password
    elif password_hash is not None:
        password_sql = "\"%s\"" % password_hash

    db = connect()
    cur = db.cursor ()
    query = "UPDATE mysql.user SET password=%s WHERE User='%s' AND Host = '%s';" % (password_sql,user,host,)
    log.debug("Query: {0}".format(query,))
    if cur.execute( query ):
        log.info("Password for user '{0}'@'{1}' has been changed".format(user,host,))
        return True

    log.info("Password for user '{0}'@'{1}' is not changed".format(user,host,))
    return False

def user_remove(user,
                host='localhost'):
    '''
    Delete MySQL user

    CLI Example::

        salt '*' mysql.user_remove frank localhost
    '''
    db = connect()
    cur = db.cursor ()
    query = "DROP USER '%s'@'%s'" % (user, host,)
    log.debug("Query: {0}".format(query,))
    cur.execute(query)
    result = cur.fetchone()
    if not user_exists(user,host):
        log.info("User '{0}'@'{1}' has been removed".format(user,host,))
        return True

    log.info("User '{0}'@'{1}' has NOT been removed".format(user,host,))
    return False

'''
Maintenance
'''
def db_check(name,
              table=None):
    '''
    Repairs the full database or just a given table

    CLI Example::

        salt '*' mysql.db_check dbname
    '''
    ret = []
    if table is None:
        # we need to check all tables
        tables = db_tables(name)
        for table in tables:
            log.info("Checking table '%s' in db '%s..'".format(name,table,))
            ret.append( __check_table(name,table) )
    else:
        log.info("Checking table '%s' in db '%s'..".format(name,table,))
        ret = __check_table(name,table)
    return ret

def db_repair(name,
              table=None):
    '''
    Repairs the full database or just a given table

    CLI Example::

        salt '*' mysql.db_repair dbname
    '''
    ret = []
    if table is None:
        # we need to repair all tables
        tables = db_tables(name)
        for table in tables:
            log.info("Repairing table '%s' in db '%s..'".format(name,table,))
            ret.append( __repair_table(name,table) )
    else:
        log.info("Repairing table '%s' in db '%s'..".format(name,table,))
        ret = __repair_table(name,table)
    return ret

def db_optimize(name,
              table=None):
    '''
    Optimizes the full database or just a given table

    CLI Example::

        salt '*' mysql.db_optimize dbname
    '''
    ret = []
    if table is None:
        # we need to optimize all tables
        tables = db_tables(name)
        for table in tables:
            log.info("Optimizing table '%s' in db '%s..'".format(name,table,))
            ret.append( __optimize_table(name,table) )
    else:
        log.info("Optimizing table '%s' in db '%s'..".format(name,table,))
        ret = __optimize_table(name,table)
    return ret

'''
Grants
'''
def __grant_generate(grant,
                    database,
                    user,
                    host='localhost',
                    grant_option=False,
                    escape=True):
    # todo: Re-order the grant so it is according to the SHOW GRANTS for xxx@yyy query (SELECT comes first, etc)
    grant = grant.replace(',', ', ').upper()

    db_part = database.rpartition('.')
    db = db_part[0]
    table = db_part[2]

    if escape:
        db = "`%s`" % db
        table = "`%s`" % table
    query = "GRANT %s ON %s.%s TO '%s'@'%s'" % (grant, db, table, user, host,)
    if grant_option:
        query += " WITH GRANT OPTION"
    log.debug("Query generated: {0}".format(query,))
    return query

def user_grants(user,
                host='localhost'):
    '''
    Shows the grants for the given MySQL user (if it exists)

    CLI Example::

        salt '*' mysql.user_grants 'frank' 'localhost'
    '''
    if not user_exists(user):
       log.info("User '{0}' does not exist".format(user,))
       return False

    ret = []
    db = connect()
    cur = db.cursor()
    query = "SHOW GRANTS FOR '%s'@'%s'" % (user,host,)
    log.debug("Doing query: {0}".format(query,))

    cur.execute(query)
    results = cur.fetchall()
    for grant in results:
        ret.append(grant[0])
    log.debug(ret)
    return ret

def grant_exists(grant,
                database,
                user,
                host='localhost',
                grant_option=False,
                escape=True):
    # todo: This function is a bit tricky, since it requires the ordering to be exactly the same.
    # perhaps should be replaced/reworked with a better/cleaner solution.
    target = __grant_generate(grant, database, user, host, grant_option, escape)

    if target in user_grants(user, host):
        log.debug("Grant exists.")
        return True

    log.debug("Grant does not exist, or is perhaps not ordered properly?")
    return False

def grant_add(grant,
              database,
              user,
              host='localhost',
              grant_option=False,
              escape=True):
    '''
    Adds a grant to the MySQL server.

    CLI Example::

        salt '*' mysql.grant_add 'SELECT|INSERT|UPDATE|...' 'database.*' 'frank' 'localhost'
    '''
    # todo: validate grant
    db = connect()
    cur = db.cursor()

    query = __grant_generate(grant, database, user, host, grant_option, escape)
    log.debug("Query: {0}".format(query,))
    if cur.execute( query ):
        log.info("Grant '{0}' created")
        return True
    return False

def grant_revoke(grant,
                 database,
                 user,
                 host='localhost',
                 grant_option=False):
    '''
    Removes a grant from the MySQL server.

    CLI Example::

        salt '*' mysql.grant_revoke 'SELECT,INSERT,UPDATE' 'database.*' 'frank' 'localhost'
    '''
    # todo: validate grant
    db = connect()
    cur = db.cursor()

    if grant_option:
        grant += ", GRANT OPTION"
    query = "REVOKE %s ON %s FROM '%s'@'%s';" % (grant, database, user, host,)
    log.debug("Query: {0}".format(query,))
    if cur.execute( query ):
        log.info("Grant '{0}' revoked")
        return True
    return False

