"""
Support for SQLite3
"""

try:
    import sqlite3

    HAS_SQLITE3 = True
except ImportError:
    HAS_SQLITE3 = False


# pylint: disable=C0103
def __virtual__():
    if not HAS_SQLITE3:
        return (
            False,
            "The sqlite3 execution module failed to load: the sqlite3 python library is"
            " not available.",
        )
    return True


def _connect(db=None):
    if db is None:
        return False

    con = sqlite3.connect(db, isolation_level=None)
    cur = con.cursor()
    return cur


def version():
    """
    Return version of pysqlite

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.version
    """
    return sqlite3.version


def sqlite_version():
    """
    Return version of sqlite

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.sqlite_version
    """
    return sqlite3.sqlite_version


def modify(db=None, sql=None):
    """
    Issue an SQL query to sqlite3 (with no return data), usually used
    to modify the database in some way (insert, delete, create, etc)

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.modify /root/test.db 'CREATE TABLE test(id INT, testdata TEXT);'
    """
    cur = _connect(db)

    if not cur:
        return False

    cur.execute(sql)
    return True


def fetch(db=None, sql=None):
    """
    Retrieve data from an sqlite3 db (returns all rows, be careful!)

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.fetch /root/test.db 'SELECT * FROM test;'
    """
    cur = _connect(db)

    if not cur:
        return False

    cur.execute(sql)
    rows = cur.fetchall()
    return rows


def tables(db=None):
    """
    Show all tables in the database

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.tables /root/test.db
    """
    cur = _connect(db)

    if not cur:
        return False

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    rows = cur.fetchall()
    return rows


def indices(db=None):
    """
    Show all indices in the database

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.indices /root/test.db
    """
    cur = _connect(db)

    if not cur:
        return False

    cur.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;")
    rows = cur.fetchall()
    return rows


def indexes(db=None):
    """
    Show all indices in the database, for people with poor spelling skills

    CLI Example:

    .. code-block:: bash

        salt '*' sqlite3.indexes /root/test.db
    """
    return indices(db)
