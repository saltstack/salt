'''
Support for SQLite3
'''

try:
    import sqlite3
    has_sqlite3 = True
except ImportError:
    has_sqlite3 = False

def __virtual__():
    if not has_sqlite3:
        return False
    return 'sqlite3'

def version():
    '''
    Return version of pysqlite

    CLI Example::

        salt '*' sqlite3.version
    '''
    return sqlite3.version

def sqlite_version():
    '''
    Return version of sqlite

    CLI Example::

        salt '*' sqlite3.sqlite_version
    '''
    return sqlite3.sqlite_version

def query(db=None, sql=None):
    '''
    Issue an SQL query to sqlite3 (with no return data)

    CLI Example::

        salt '*' sqlite3.query /root/test.db 'CREATE TABLE test(id INT, testdata TEXT);'
    '''
    if db == None:
        return False

    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute(sql)
    return True

def select(db=None, sql=None):
    '''
    SELECT data from an sqlite3 db (returns all rows, be careful!)

    CLI Example::

        salt '*' sqlite3.select /root/test.db 'SELECT * FROM test;'
    '''
    if db == None:
        return False

    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    return rows
