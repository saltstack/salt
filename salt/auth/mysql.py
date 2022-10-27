"""
Provide authentication using MySQL.

When using MySQL as an authentication backend, you will need to create or
use an existing table that has a username and a password column.

To get started, create a simple table that holds just a username and
a password. The password field will hold a SHA256 checksum.

.. code-block:: sql

    CREATE TABLE `users` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `username` varchar(25) DEFAULT NULL,
      `password` varchar(70) DEFAULT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=latin1;

To create a user within MySQL, execute the following statement.

.. code-block:: sql

    INSERT INTO users VALUES (NULL, 'diana', SHA2('secret', 256))

.. code-block:: yaml

    mysql_auth:
      hostname: localhost
      database: SaltStack
      username: root
      password: letmein
      auth_sql: 'SELECT username FROM users WHERE username = "{0}" AND password = SHA2("{1}", 256)'

The `auth_sql` contains the SQL that will validate a user to ensure they are
correctly authenticated. This is where you can specify other SQL queries to
authenticate users.

Enable MySQL authentication.

.. code-block:: yaml

    external_auth:
      mysql:
        damian:
          - test.*

:depends:   - MySQL-python Python module
"""


import logging

log = logging.getLogger(__name__)

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.converters
    import MySQLdb.cursors
    from MySQLdb.connections import OperationalError
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.converters
        import MySQLdb.cursors
        from MySQLdb.err import OperationalError
    except ImportError:
        MySQLdb = None


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


def __get_connection_info():
    """
    Grab MySQL Connection Details
    """
    conn_info = {}

    try:
        conn_info["hostname"] = __opts__["mysql_auth"]["hostname"]
        conn_info["username"] = __opts__["mysql_auth"]["username"]
        conn_info["password"] = __opts__["mysql_auth"]["password"]
        conn_info["database"] = __opts__["mysql_auth"]["database"]

        conn_info["auth_sql"] = __opts__["mysql_auth"]["auth_sql"]
    except KeyError as e:
        log.error("%s does not exist", e)
        return None

    return conn_info


def auth(username, password):
    """
    Authenticate using a MySQL user table
    """
    _info = __get_connection_info()

    if _info is None:
        return False

    try:
        conn = MySQLdb.connect(
            _info["hostname"], _info["username"], _info["password"], _info["database"]
        )
    except OperationalError as e:
        log.error(e)
        return False

    cur = conn.cursor()
    cur.execute(_info["auth_sql"].format(username, password))

    if cur.rowcount == 1:
        return True

    return False
