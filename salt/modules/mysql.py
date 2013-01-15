'''
Module to provide MySQL compatibility to salt.

:depends:   - MySQLdb Python module
:configuration: In order to connect to MySQL, certain configuration is required
    in /etc/salt/minion on the relevant minions. Some sample configs might look
    like::

        mysql.host: 'localhost'
        mysql.port: 3306
        mysql.user: 'root'
        mysql.pass: ''
        mysql.db: 'mysql'
        mysql.unix_socket: '/tmp/mysql.sock'

    You can also use a defaults file::

        mysql.default_file: '/etc/mysql/debian.cnf'
'''

# Import python libs
import time
import logging
import re
import sys

# Import third party libs
try:
    import MySQLdb
    import MySQLdb.cursors
    HAS_MYSQLDB = True
except ImportError:
    HAS_MYSQLDB = False

log = logging.getLogger(__name__)

# TODO: this is not used anywhere in the code?
__opts__ = {}


def __virtual__():
    '''
    Only load this module if the mysql libraries exist
    '''
    if HAS_MYSQLDB:
        return 'mysql'
    return False


def __check_table(name, table):
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    query = 'CHECK TABLE `{0}`.`{1}`'.format(name, table)
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results


def __repair_table(name, table):
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    query = 'REPAIR TABLE `{0}`.`{1}`'.format(name, table)
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results


def __optimize_table(name, table):
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    query = 'OPTIMIZE TABLE `{0}`.`{1}`'.format(name, table)
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)
    results = cur.fetchall()
    log.debug(results)
    return results


def connect(**kwargs):
    '''
    wrap authentication credentials here
    '''
    connargs = dict()

    def _connarg(name, key=None):
        '''
        Add key to connargs, only if name exists in our
        kwargs or as mysql.<name> in __opts__ or __pillar__
        Evaluate in said order - kwargs, opts then pillar
        '''
        if key is None:
            key = name
        if name in kwargs:
            connargs[key] = kwargs[name]
        else:
            val = __salt__['config.option']('mysql.{0}'.format(name), None)
            if val is not None:
                connargs[key] = val

    _connarg('host')
    _connarg('user')
    _connarg('pass', 'passwd')
    _connarg('port')
    _connarg('db')
    _connarg('unix_socket')
    _connarg('default_file', 'read_default_file')

    dbc = MySQLdb.connect(**connargs)
    dbc.autocommit(True)
    return dbc


def query(database, query):
    '''
    Run an arbitrary SQL query and return the results or
    the number of affected rows.

    CLI Examples::

        salt '*' mysql.query mydb "UPDATE mytable set myfield=1 limit 1"
        returns: {'query time': {'human': '39.0ms', 'raw': '0.03899'},
        'rows affected': 1L}

        salt '*' mysql.query mydb "SELECT id,name,cash from users limit 3"
        returns: {'columns': ('id', 'name', 'cash'),
            'query time': {'human': '1.0ms', 'raw': '0.001'},
            'results': ((1L, 'User 1', Decimal('110.000000')),
                        (2L, 'User 2', Decimal('215.636756')),
                        (3L, 'User 3', Decimal('0.040000'))),
            'rows returned': 3L}

        salt '*' mysql.query mydb "INSERT into users values (null,'user 4', 5)"
        returns: {'query time': {'human': '25.6ms', 'raw': '0.02563'},
           'rows affected': 1L}

        salt '*' mysql.query mydb "DELETE from users where id = 4 limit 1"
        returns: {'query time': {'human': '39.0ms', 'raw': '0.03899'},
            'rows affected': 1L}

    Jinja Example::

        Run a query on "mydb" and use row 0, column 0's data.
        {{ salt['mysql.query']("mydb","SELECT info from mytable limit 1")['results'][0][0] }}

    '''
    # Doesn't do anything about sql warnings, e.g. empty values on an insert.
    # I don't think it handles multiple queries at once, so adding "commit"
    # might not work.
    ret = {}
    dbc = connect(**{'db': database})
    cur = dbc.cursor()
    start = time.time()
    affected = cur.execute(query)
    log.debug('Using db: ' + database + ' to run query: ' + query)
    results = cur.fetchall()
    elapsed = (time.time() - start)
    if elapsed < 0.200:
        elapsed_h = str(round(elapsed * 1000, 1)) + 'ms'
    else:
        elapsed_h = str(round(elapsed, 2)) + 's'
    ret['query time'] = {'human': elapsed_h, 'raw': str(round(elapsed, 5))}
    if len(results) == 0:
        ret['rows affected'] = affected
        return ret
    else:
        ret['rows returned'] = affected
        columns = ()
        for column in cur.description:
            columns += (column[0],)
        ret['columns'] = columns
        ret['results'] = results
        return ret


def status():
    '''
    Return the status of a MySQL server using the output
    from the ``SHOW STATUS`` query.

    CLI Example::

        salt '*' mysql.status
    '''
    ret = {}
    dbc = connect()
    cur = dbc.cursor()
    cur.execute('SHOW STATUS')
    for _ in range(cur.rowcount):
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
    dbc = connect()
    cur = dbc.cursor()
    cur.execute('SELECT VERSION()')
    row = cur.fetchone()
    return row


def slave_lag():
    '''
    Return the number of seconds that a slave SQL server is lagging behind the
    master, if the host is not a slave it will return -1.  If the server is
    configured to be a slave for replication but slave IO is not running then
    -2 will be returned.

    CLI Example::

        salt '*' mysql.slave_lag
    '''
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('show slave status')
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


#Database related actions
def db_list():
    '''
    Return a list of databases of a MySQL server using the output
    from the ``SHOW DATABASES`` query.

    CLI Example::

        salt '*' mysql.db_list
    '''
    ret = []
    dbc = connect()
    cur = dbc.cursor()
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

        salt '*' mysql.db_tables 'database'
    '''
    if not db_exists(name):
        log.info("Database '{0}' does not exist".format(name,))
        return False

    ret = []
    dbc = connect()
    cur = dbc.cursor()
    query = 'SHOW TABLES IN {0}'.format(name)
    log.debug('Doing query: {0}'.format(query))

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

        salt '*' mysql.db_exists 'dbname'
    '''
    dbc = connect()
    cur = dbc.cursor()
    query = 'SHOW DATABASES LIKE \'{0}\''.format(name)
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)
    cur.fetchall()
    return cur.rowcount == 1


def db_create(name):
    '''
    Adds a databases to the MySQL server.

    CLI Example::

        salt '*' mysql.db_create 'dbname'
    '''
    # check if db exists
    if db_exists(name):
        log.info('DB \'{0}\' already exists'.format(name))
        return False

    # db doesnt exist, proceed
    dbc = connect()
    cur = dbc.cursor()
    query = 'CREATE DATABASE `{0}`;'.format(name)
    log.debug('Query: {0}'.format(query))
    if cur.execute(query):
        log.info('DB \'{0}\' created'.format(name))
        return True
    return False


def db_remove(name):
    '''
    Removes a databases from the MySQL server.

    CLI Example::

        salt '*' mysql.db_remove 'dbname'
    '''
    # check if db exists
    if not db_exists(name):
        log.info('DB \'{0}\' does not exist'.format(name))
        return False

    if name in ('mysql', 'information_scheme'):
        log.info('DB \'{0}\' may not be removed'.format(name))
        return False

    # db doesnt exist, proceed
    dbc = connect()
    cur = dbc.cursor()
    query = 'DROP DATABASE `{0}`;'.format(name)
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)

    if not db_exists(name):
        log.info('Database \'{0}\' has been removed'.format(name))
        return True

    log.info('Database \'{0}\' has not been removed'.format(name))
    return False


# User related actions
def user_list():
    '''
    Return a list of users on a MySQL server

    CLI Example::

        salt '*' mysql.user_list
    '''
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT User,Host FROM mysql.user')
    results = cur.fetchall()
    log.debug(results)
    return results


def user_exists(user, host='localhost'):
    '''
    Checks if a user exists on the  MySQL server.

    CLI Example::

        salt '*' mysql.user_exists 'username' 'hostname'
    '''
    dbc = connect()
    cur = dbc.cursor()
    query = ('SELECT User,Host FROM mysql.user WHERE User = \'{0}\' AND '
             'Host = \'{1}\''.format(user, host))
    log.debug('Doing query: {0}'.format(query))
    cur.execute(query)
    return cur.rowcount == 1


def user_info(user, host='localhost'):
    '''
    Get full info on a MySQL user

    CLI Example::

        salt '*' mysql.user_info root localhost
    '''
    dbc = connect()
    cur = dbc.cursor(MySQLdb.cursors.DictCursor)
    query = ('SELECT * FROM mysql.user WHERE User = \'{0}\' AND '
             'Host = \'{1}\''.format(user, host))
    log.debug('Query: {0}'.format(query))
    cur.execute(query)
    result = cur.fetchone()
    log.debug(result)
    return result


def user_create(user,
                host='localhost',
                password=None,
                password_hash=None):
    '''
    Creates a MySQL user.

    CLI Examples::

        salt '*' mysql.user_create 'username' 'hostname' 'password'

        salt '*' mysql.user_create 'username' 'hostname' password_hash='hash'
    '''
    if user_exists(user, host):
        log.info('User \'{0}\'@\'{1}\' already exists'.format(user, host))
        return False

    dbc = connect()
    cur = dbc.cursor()
    query = 'CREATE USER \'{0}\'@\'{1}\''.format(user, host)
    if password is not None:
        query = query + ' IDENTIFIED BY \'{0}\''.format(password)
    elif password_hash is not None:
        query = query + ' IDENTIFIED BY PASSWORD \'{0}\''.format(password_hash)

    log.debug('Query: {0}'.format(query))
    cur.execute(query)

    if user_exists(user, host):
        log.info('User \'{0}\'@\'{1}\' has been created'.format(user, host))
        return True

    log.info('User \'{0}\'@\'{1}\' is not created'.format(user, host))
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
    if password is None and password_hash is None:
        log.error('No password provided')
        return False
    elif password is not None:
        password_sql = 'PASSWORD("{0}")'.format(password)
    elif password_hash is not None:
        password_sql = '"{0}"'.format(password_hash)

    dbc = connect()
    cur = dbc.cursor()
    query = ('UPDATE mysql.user SET password={0} WHERE User=\'{1}\' AND '
             'Host = \'{2}\';'.format(password_sql, user, host))
    log.debug('Query: {0}'.format(query))
    if cur.execute(query):
        cur.execute('FLUSH PRIVILEGES;')
        log.info(
            'Password for user \'{0}\'@\'{1}\' has been changed'.format(
                user, host
            )
        )
        return True

    log.info(
        'Password for user \'{0}\'@\'{1}\' is not changed'.format(user, host)
    )
    return False


def user_remove(user,
                host='localhost'):
    '''
    Delete MySQL user

    CLI Example::

        salt '*' mysql.user_remove frank localhost
    '''
    dbc = connect()
    cur = dbc.cursor()
    query = 'DROP USER \'{0}\'@\'{1}\''.format(user, host)
    log.debug('Query: {0}'.format(query))
    cur.execute(query)
    if not user_exists(user, host):
        log.info('User \'{0}\'@\'{1}\' has been removed'.format(user, host))
        return True

    log.info('User \'{0}\'@\'{1}\' has NOT been removed'.format(user, host))
    return False


# Maintenance
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
            log.info(
                'Checking table \'{0}\' in db \'{1}..\''.format(name, table)
            )
            ret.append(__check_table(name, table))
    else:
        log.info('Checking table \'{0}\' in db \'{1}\'..'.format(name, table))
        ret = __check_table(name, table)
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
            log.info(
                'Repairing table \'{0}\' in db \'{1}..\''.format(name, table)
            )
            ret.append(__repair_table(name, table))
    else:
        log.info('Repairing table \'{0}\' in db \'{1}\'..'.format(name, table))
        ret = __repair_table(name, table)
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
            log.info(
                'Optimizing table \'{0}\' in db \'{1}..\''.format(name, table)
            )
            ret.append(__optimize_table(name, table))
    else:
        log.info(
            'Optimizing table \'{0}\' in db \'{1}\'..'.format(name, table)
        )
        ret = __optimize_table(name, table)
    return ret


# Grants
def __grant_generate(grant,
                    database,
                    user,
                    host='localhost',
                    grant_option=False,
                    escape=True):
    # TODO: Re-order the grant so it is according to the
    #       SHOW GRANTS for xxx@yyy query (SELECT comes first, etc)
    grant = re.sub(r'\s*,\s*', ', ', grant).upper()

    # MySQL normalizes ALL to ALL PRIVILEGES, we do the same so that
    # grant_exists and grant_add ALL work correctly
    if grant == 'ALL':
        grant = 'ALL PRIVILEGES'

    db_part = database.rpartition('.')
    dbc = db_part[0]
    table = db_part[2]

    if escape:
        if dbc is not '*':
            dbc = '`{0}`'.format(dbc)
        if table is not '*':
            table = '`{0}`'.format(table)
    query = 'GRANT {0} ON {1}.{2} TO \'{3}\'@\'{4}\''.format(
        grant, dbc, table, user, host
    )
    if grant_option:
        query += ' WITH GRANT OPTION'
    log.debug('Query generated: {0}'.format(query))
    return query


def user_grants(user,
                host='localhost'):
    '''
    Shows the grants for the given MySQL user (if it exists)

    CLI Example::

        salt '*' mysql.user_grants 'frank' 'localhost'
    '''
    if not user_exists(user, host):
        log.info('User \'{0}\'@\'{1}\' does not exist'.format(user, host))
        return False

    ret = []
    dbc = connect()
    cur = dbc.cursor()
    query = 'SHOW GRANTS FOR \'{0}\'@\'{1}\''.format(user, host)
    log.debug('Doing query: {0}'.format(query))

    cur.execute(query)
    results = cur.fetchall()
    for grant in results:
        ret.append(grant[0].split(' IDENTIFIED BY')[0])
    log.debug(ret)
    return ret


def grant_exists(grant,
                database,
                user,
                host='localhost',
                grant_option=False,
                escape=True):
    # TODO: This function is a bit tricky, since it requires the ordering to
    #       be exactly the same. Perhaps should be replaced/reworked with a
    #       better/cleaner solution.
    target = __grant_generate(
        grant, database, user, host, grant_option, escape
    )

    grants = user_grants(user, host)
    if grants is not False and target in grants:
        log.debug('Grant exists.')
        return True

    log.debug('Grant does not exist, or is perhaps not ordered properly?')
    return False


def grant_add(grant,
              database,
              user,
              host='localhost',
              grant_option=False,
              escape=True):
    '''
    Adds a grant to the MySQL server.

    For database, make sure you specify database.table or database.*

    CLI Example::

        salt '*' mysql.grant_add 'SELECT,INSERT,UPDATE,...' 'database.*' 'frank' 'localhost'
    '''
    # todo: validate grant
    dbc = connect()
    cur = dbc.cursor()

    query = __grant_generate(grant, database, user, host, grant_option, escape)
    log.debug('Query: {0}'.format(query))
    cur.execute(query)
    if grant_exists(grant, database, user, host, grant_option, escape):
        log.info(
            'Grant \'{0}\' on \'{1}\' for user \'{2}\' has been added'.format(
                grant, database, user
            )
        )
        return True

    log.info(
        'Grant \'{0}\' on \'{1}\' for user \'{2}\' has NOT been added'.format(
            grant, database, user
        )
    )
    return False


def grant_revoke(grant,
                 database,
                 user,
                 host='localhost',
                 grant_option=False,
                 escape=True):
    '''
    Removes a grant from the MySQL server.

    CLI Example::

        salt '*' mysql.grant_revoke 'SELECT,INSERT,UPDATE' 'database.*' 'frank' 'localhost'
    '''
    # todo: validate grant
    dbc = connect()
    cur = dbc.cursor()

    if grant_option:
        grant += ', GRANT OPTION'
    query = 'REVOKE {0} ON {1} FROM \'{2}\'@\'{3}\';'.format(
        grant, database, user, host
    )
    log.debug('Query: {0}'.format(query))
    cur.execute(query)
    if not grant_exists(grant, database, user, host, grant_option, escape):
        log.info(
            'Grant \'{0}\' on \'{1}\' for user \'{2}\' has been '
            'revoked'.format(grant, database, user)
        )
        return True

    log.info(
        'Grant \'{0}\' on \'{1}\' for user \'{2}\' has NOT been '
        'revoked'.format(grant, database, user)
    )
    return False


def processlist():
    '''
    Retrieves the processlist from the MySQL server via
    "SHOW FULL PROCESSLIST".

    Returns: a list of dicts, with each dict representing a process:
        {'Command': 'Query',
                          'Host': 'localhost',
                          'Id': 39,
                          'Info': 'SHOW FULL PROCESSLIST',
                          'Rows_examined': 0,
                          'Rows_read': 1,
                          'Rows_sent': 0,
                          'State': None,
                          'Time': 0,
                          'User': 'root',
                          'db': 'mysql'}

    CLI Example:
        salt '*' mysql.processlist

    '''
    ret = []
    hdr = ('Id', 'User', 'Host', 'db', 'Command', 'Time', 'State',
           'Info', 'Rows_sent', 'Rows_examined', 'Rows_read')

    log.debug('MySQL Process List:\n{0}'.format(processlist()))
    dbc = connect()
    cur = dbc.cursor()
    cur.execute("SHOW FULL PROCESSLIST")
    for _ in range(cur.rowcount):
        row = cur.fetchone()
        idx_r = {}
        for idx_j in range(len(hdr)):
            try:
                idx_r[hdr[idx_j]] = row[idx_j]
            except KeyError:
                pass
        ret.append(idx_r)
    cur.close()
    return ret


def __do_query_into_hash(conn, sql_str):
    '''
    Perform the query that is passed to it (sql_str).

    Returns:
       results in a dict.

    '''
    mod = sys._getframe().f_code.co_name
    log.debug('{0}<--({1})'.format(mod, sql_str))

    rtn_results = []

    try:
        cursor = conn.cursor()
    except MySQLdb.MySQLError:
        log.error('{0}: Can\'t get cursor for SQL->{1}'.format(mod, sql_str))
        cursor.close()
        log.debug('{0}-->'.format(mod))
        return rtn_results

    try:
        cursor.execute(sql_str)
    except MySQLdb.MySQLError:
        log.error('{0}: try to execute : SQL->{1}'.format(mod, sql_str))
        cursor.close()
        log.debug('{0}-->'.format(mod))
        return rtn_results

    qrs = cursor.fetchall()

    for row_data in qrs:
        col_cnt = 0
        row = {}
        for col_data in cursor.description:
            col_name = col_data[0]
            row[col_name] = row_data[col_cnt]
            col_cnt += 1

        rtn_results.append(row)

    cursor.close()
    log.debug('{0}-->'.format(mod))
    return rtn_results


def get_master_status():
    '''
    Retrieves the master status from the mimion.

    Returns:
        {'host.domain.com': {'Binlog_Do_DB': '',
                         'Binlog_Ignore_DB': '',
                         'File': 'mysql-bin.000021',
                         'Position': 107}}

    CLI Example:
        salt '*' mysql.get_master_status

    '''
    mod = sys._getframe().f_code.co_name
    log.debug('{0}<--'.format(mod))
    conn = connect()
    rtnv = __do_query_into_hash(conn, "SHOW MASTER STATUS")
    conn.close()

    # check for if this minion is not a master
    if (len(rtnv) == 0):
        rtnv.append([])

    log.debug('{0}-->{1}'.format(mod, len(rtnv[0])))
    return rtnv[0]


def get_slave_status():
    '''
    Retrieves the slave status from the minion.

    Returns::

        {'host.domain.com': {'Connect_Retry': 60,
                       'Exec_Master_Log_Pos': 107,
                       'Last_Errno': 0,
                       'Last_Error': '',
                       'Last_IO_Errno': 0,
                       'Last_IO_Error': '',
                       'Last_SQL_Errno': 0,
                       'Last_SQL_Error': '',
                       'Master_Host': 'comet.scion-eng.com',
                       'Master_Log_File': 'mysql-bin.000021',
                       'Master_Port': 3306,
                       'Master_SSL_Allowed': 'No',
                       'Master_SSL_CA_File': '',
                       'Master_SSL_CA_Path': '',
                       'Master_SSL_Cert': '',
                       'Master_SSL_Cipher': '',
                       'Master_SSL_Key': '',
                       'Master_SSL_Verify_Server_Cert': 'No',
                       'Master_Server_Id': 1,
                       'Master_User': 'replu',
                       'Read_Master_Log_Pos': 107,
                       'Relay_Log_File': 'klo-relay-bin.000071',
                       'Relay_Log_Pos': 253,
                       'Relay_Log_Space': 553,
                       'Relay_Master_Log_File': 'mysql-bin.000021',
                       'Replicate_Do_DB': '',
                       'Replicate_Do_Table': '',
                       'Replicate_Ignore_DB': '',
                       'Replicate_Ignore_Server_Ids': '',
                       'Replicate_Ignore_Table': '',
                       'Replicate_Wild_Do_Table': '',
                       'Replicate_Wild_Ignore_Table': '',
                       'Seconds_Behind_Master': 0,
                       'Skip_Counter': 0,
                       'Slave_IO_Running': 'Yes',
                       'Slave_IO_State': 'Waiting for master to send event',
                       'Slave_SQL_Running': 'Yes',
                       'Until_Condition': 'None',
                       'Until_Log_File': '',
                       'Until_Log_Pos': 0}}

    CLI Example::

        salt '*' mysql.get_slave_status

    '''
    mod = sys._getframe().f_code.co_name
    log.debug('{0}<--'.format(mod))
    conn = connect()
    rtnv = __do_query_into_hash(conn, "SHOW SLAVE STATUS")
    conn.close()

    # check for if this minion is not a slave
    if (len(rtnv) == 0):
        rtnv.append([])

    log.debug('{0}-->{1}'.format(mod, len(rtnv[0])))
    return rtnv[0]
