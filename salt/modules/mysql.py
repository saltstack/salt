'''
Module to provide MySQL compatibility to salt.

In order to connect to MySQL, certain configuration is required 
in /etc/salt/minion on the relevant minions. Some sample configs
might look like:

mysql.host: 'localhost'
mysql.port: 3306
mysql.user: 'root'
mysql.pass: ''
mysql.db: 'mysql'
'''

import MySQLdb

__opts__ = {}

def connect():
    '''
    wrap authentication credentials here
    '''

    hostname = __opts__['mysql.host']
    username = __opts__['mysql.user']
    password = __opts__['mysql.pass']
    dbport = __opts__['mysql.port']
    dbname = __opts__['mysql.db']

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
    from the SHOW STATUS query.

    CLI Example:
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
    from the SELECT VERSION() query.

    CLI Example:
    salt '*' mysql.version
    '''
    db = connect()
    cur = db.cursor()
    cur.execute('SELECT VERSION()')
    row = cur.fetchone()
    return row

