# -*- coding: utf-8 -*-

'''
Provide authentication using SQLite.

When using SQLite as an authentication backend, you will need to create or
use an existing table that has a username and a password column.

To get started, create a simple table that holds just a username and
a password. The password field will hold a SHA256 checksum (hex digest).

.. code-block:: sql

    CREATE TABLE `users` (
      `id` INTEGER PRIMARY KEY ASC,
      `username` VARCHAR(25),
      `password` VARCHAR(64)
    );

To create a user within SQLite, execute the following statement.

.. code-block:: sql

    INSERT INTO users(username, password) VALUES ('diana',
      '2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b');

Where username is `diana` and password is the SHA256 hex digest of `secret`.

.. code-block:: yaml

    sqlite_auth:
      database: salt_users.db
      username: root
      password: letmein
      auth_sql: 'SELECT username FROM users WHERE username = ? AND password = SHA256(?)'

The `auth_sql` contains the SQL that will validate a user to ensure they are
correctly authenticated. This is where you can specify other SQL queries to
authenticate users.

Enable SQLite authentication.

.. code-block:: yaml

    external_auth:
      sqlite:
        damian:
          - test.*
'''

from __future__ import absolute_import
import logging
import hashlib
import os.path

log = logging.getLogger(__name__)


def __get_connection_info():
    '''
    Grab SQLite Connection Details
    '''
    conn_info = {}
    try:
        conn_info['database'] = __opts__['sqlite_auth']['database']
        conn_info['username'] = __opts__['sqlite_auth']['username']
        conn_info['password'] = __opts__['sqlite_auth']['password']
        conn_info['auth_sql'] = __opts__['sqlite_auth']['auth_sql']
    except KeyError as e:
        log.error('{0} does not exist'.format(e))
        return None
    return conn_info


def sha256sum(text):
    '''
    Calculate SHA-256 hex digest of text
    '''
    return hashlib.sha256(text).hexdigest()


def auth(username, password):
    '''
    Authenticate using a SQLite user table
    '''
    _info = __get_connection_info()

    if _info is None:
        return False

    if not os.path.isfile(_info['database']):
        log.error('File {0} not found'.format(_info['database']))
        return False

    conn = sqlite3.connect(_info['database'])

    # In order to have SHA256() in SQL statements
    conn.create_function('sha256', 1, sha256sum)

    cur = conn.cursor()
    try:
        cur.execute(_info['auth_sql'], (username, password))
    except sqlite3.OperationalError as e:
        log.error(e)
        return False

    if cur.rowcount == 1:
        return True

    return False
