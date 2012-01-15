'''
Module to provide MySQL compatibility to salt.

In order to connect to MySQL, certain configuration is required
in /etc/salt/minion on the relevant minions. Some sample configs
might look like::

    mysql.host: 'localhost'
    mysql.port: 3306
    mysql.user: 'root'
    mysql.pass: ''
    mysql.db: 'mysql'
'''

import logging
import MySQLdb
import MySQLdb.cursors

log = logging.getLogger(__name__)
__opts__ = {}

def __check_table(name, table):
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    query = "CHECK TABLE `%s`.`%s`" % (name,table,)
    log.debug("Doing query: {0}".format(query,))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results   
    
def __repair_table(name, table):
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    query = "REPAIR TABLE `%s`.`%s`" % (name,table,)
    log.debug("Doing query: {0}".format(query,))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results
    
def __optimize_table(name, table):
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    query = "OPTIMIZE TABLE `%s`.`%s`" % (name,table,)
    log.debug("Doing query: {0}".format(query,))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results

def connect(**kwargs):
    '''
    wrap authentication credentials here
    '''
    hostname = kwargs.get('host', __opts__['mysql.host'])
    username = kwargs.get('user', __opts__['mysql.user'])
    password = kwargs.get('pass', __opts__['mysql.pass'])
    dbport = kwargs.get('port', __opts__['mysql.port'])
    dbname = kwargs.get('db', __opts__['mysql.db'])

    db = MySQLdb.connect(
        hostname,
        username,
        password,
        dbname,
        dbport,
    )

    db.autocommit(True)
    return db


def status():
    '''
    Return the status of a MySQL server using the output
    from the ``SHOW STATUS`` query.

    CLI Example::

        salt '*' mysql.status
    '''
    ret = {}
    db = connect()
    cur = db.cursor()
    cur.execute('SHOW STATUS')
    for i in xrange(cur.rowcount):
        row = cur.fetchone()
        ret[row[0]] = row[1]
    return ret


def version():
    '''
    Return the version of a MySQL server using the output
    from the ``SELECT VERSION()`` query.

    CLI Example::

        salt '*' mysql.version
    '''
    db = connect()
    cur = db.cursor()
    cur.execute('SELECT VERSION()')
    row = cur.fetchone()
    return row

def slave_lag():
    '''
    Return the number of seconds that a slave SQL server is lagging behind the
    master, if the host is not a slave it will return -1.  If the server is
    configured to be a slave but replication but slave IO is not running then
    -2 will be returned.

    CLI Example::

        salt '*' mysql.slave_lag
    '''
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("show slave status")
    results = cur.fetchone()
    if cur.rowcount == 0:
        # Server is not a slave if master is not defined.  Return empty tuple
        # in this case.  Could probably check to see if Slave_IO_Running and
        # Slave_SQL_Running are both set to 'Yes' as well to be really really
        # sure that it is a slave.
        return -1
    else:
        if results['Slave_IO_Running'] == 'Yes':
            return results['Seconds_Behind_Master']
        else:
            # Replication is broken if you get here.
            return -2


def free_slave():
    '''
    Frees a slave from its master.  This is a WIP, do not use.
    '''
    slave_db = connect()
    slave_cur = slave_db.cursor(MySQLdb.cursors.DictCursor)
    slave_cur.execute("show slave status")
    slave_status = slave_cur.fetchone()
    master = {'host': slave_status['Master_Host']}

    try:
        # Try to connect to the master and flush logs before promoting to
        # master.  This may fail if the master is no longer available.
        # I am also assuming that the admin password is the same on both
        # servers here, and only overriding the host option in the connect
        # function.
        master_db = connect(**master)
        master_cur = master_db.cursor()
        master_cur.execute("flush logs")
        master_db.close()
    except MySQLdb.OperationalError:
        pass

    slave_cur.execute("stop slave")
    slave_cur.execute("reset master")
    slave_cur.execute("change master to MASTER_HOST=''")
    slave_cur.execute("show slave status")
    results = slave_cur.fetchone()

    if results is None:
        return 'promoted'
    else:
        return 'failed'
        
'''
Database related actions
'''
def db_list():
    '''
    Return a list of databases of a MySQL server using the output
    from the ``SHOW DATABASES`` query.

    CLI Example::

        salt '*' mysqldb.db_list
    '''
    ret = []
    db = connect()
    cur = db.cursor()
    cur.execute('SHOW DATABASES')
    results = cur.fetchall()
    for dbs in results:
       ret.append(dbs[0])

    log.debug(ret)
    return ret
    
def db_tables(name):
    '''
    Shows the tables in the given MySQL database (if exists)

    CLI Example::

        salt '*' mysqldb.db_tables 'database'
    '''
    if not db_exists(name):
       log.info("Database '{0}' does not exist".format(name,))
       return False

    ret = []
    db = connect()
    cur = db.cursor()
    query = "SHOW TABLES IN %s" % name
    log.debug("Doing query: {0}".format(query,))

    cur.execute(query)
    results = cur.fetchall()
    for table in results:
       ret.append(table[0])
    log.debug(ret)
    return ret
   
def db_exists(name):
    '''
    Checks if a database exists on the MySQL server.

    CLI Example::

        salt '*' mysqldb.db_exists 'dbname'
    '''
    db = connect()
    cur = db.cursor()
    query = "SHOW DATABASES LIKE '%s'" % name
    log.debug("Doing query: {0}".format(query,))
    cur.execute( query )
    result_set = cur.fetchall()
    if cur.rowcount == 1:
       return True
    return False

    
def db_create(name):
    '''
    Adds a databases to the MySQL server.

    CLI Example::

        salt '*' mysqldb.db_create 'dbname'
    '''
    # check if db exists
    if db_exists(name):
        log.info("DB '{0}' already exists".format(name,))
        return False

    # db doesnt exist, proceed
    db = connect()
    cur = db.cursor()
    query = "CREATE DATABASE %s;" % name
    log.debug("Query: {0}".format(query,))
    if cur.execute( query ):
       log.info("DB '{0}' created".format(name,))
       return True
    return False

def db_remove(name):
    '''
    Removes a databases from the MySQL server.

    CLI Example::

        salt '*' mysqldb.db_remove 'dbname'
    '''
    # check if db exists
    if not db_exists(name):
        log.info("DB '{0}' does not exist".format(name,))
        return False

    if name in ('mysql','information_scheme'):
        log.info("DB '{0}' may not be removed".format(name,))
        return False

    # db doesnt exist, proceed
    db = connect()
    cur = db.cursor()
    query = "DROP DATABASE %s;" % name
    log.debug("Doing query: {0}".format(query,))
    cur.execute( query )

    if not db_exists(name):
       log.info("Database '{0}' has been removed".format(name,))
       return True

    log.info("Database '{0}' has not been removed".format(name,))
    return False

'''
User related actions
'''
def user_list():
    '''
    Return a list of users on a MySQL server

    CLI Example::

        salt '*' mysqldb.user_list
    '''
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT User,Host FROM mysql.user')
    results = cur.fetchall()
    log.debug(results)
    return results

def user_exists(user,
                host='localhost'):
    '''
    Checks if a user exists on the  MySQL server.

    CLI Example::

        salt '*' mysqldb.user_exists 'username' 'hostname'
    '''
    db = connect()
    cur = db.cursor()
    query = "SELECT User,Host FROM mysql.user WHERE User = '%s' AND Host = '%s'" % (user, host,)
    log.debug("Doing query: {0}".format(query,))
    cur.execute( query )
    if cur.rowcount == 1:
       return True
    return False
    
def user_info(user,
              host='localhost'):
    '''
    Get full info on a MySQL user

    CLI Example::

        salt '*' mysqldb.user_info root localhost
    '''
    db = connect()
    cur = db.cursor (MySQLdb.cursors.DictCursor)
    query = "SELECT * FROM mysql.user WHERE User = '%s' AND Host = '%s'" % (user, host,)
    log.debug("Query: {0}".format(query,))
    cur.execute(query)
    result = cur.fetchone()
    log.debug( result )
    return result

def user_create(user,
                host='localhost',
                password=None):
    '''
    Creates a MySQL user.

    CLI Example::

        salt '*' mysqldb.user_create 'username' 'hostname' 'password'
    '''
    if user_exists(user,host):
       log.info("User '{0}'@'{1}' already exists".format(user,host,))
       return False

    db = connect()
    cur = db.cursor ()
    query = "CREATE USER '%s'@'%s'" % (user, host,)
    if password is not None:
       query = query + " IDENTIFIED BY '%s'" % password

    log.debug("Query: {0}".format(query,))
    cur.execute( query )
    
    if user_exists(user,host):
       log.info("User '{0}'@'{1}' has been created".format(user,host,))
       return True

    log.info("User '{0}'@'{1}' is not created".format(user,host,))
    return False

def user_chpass(user,
                host='localhost',
                password=None):
    '''
    Change password for MySQL user

    CLI Example::

        salt '*' mysqldb.user_chpass frank localhost newpassword
    '''
    if password is None:
       log.error('No password provided')
       return False

    db = connect()
    cur = db.cursor ()
    query = "UPDATE mysql.user SET password=PASSWORD(\"%s\") WHERE User='%s' AND Host = '%s';" % (password,user,host,)
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

        salt '*' mysqldb.user_remove frank localhost
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

        salt '*' mysqldb.db_check dbname
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

        salt '*' mysqldb.db_repair dbname
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

        salt '*' mysqldb.db_optimize dbname
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