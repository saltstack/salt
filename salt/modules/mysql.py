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

import MySQLdb

__opts__ = {}


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
    master.

    CLI Example::

        salt '*' mysql.slave_lag
    '''
    db = connect()
    cur = db.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("show slave status")
    results = cur.fetchone()
    if results['Master_Host'] == '':
        # Server is not a slave if master is not defined.  Return empty tuple
        # in this case.  Could probably check to see if Slave_IO_Running and
        # Slave_SQL_Running are both set to 'Yes' as well to be really really
        # sure that it is a slave.
        return ()
    else:
        return results['Seconds_Behind_Master']
    
    
def promote_slave():
    '''
    Useful comments go here.
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
    
    






















