# -*- coding: utf-8 -*-
'''
InfluxDB - A distributed time series database

Module to provide InfluxDB compatibility to Salt (compatible with InfluxDB
version 0.5-0.8)

.. versionadded:: 2014.7.0

:depends:    - influxdb Python module (>= 1.0.0)

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions::

        influxdb08.host: 'localhost'
        influxdb08.port: 8086
        influxdb08.user: 'root'
        influxdb08.password: 'root'

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    import influxdb.influxdb08
    HAS_INFLUXDB_08 = True
except ImportError:
    HAS_INFLUXDB_08 = False

import logging

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'influxdb08'


def __virtual__():
    '''
    Only load if influxdb lib is present
    '''
    if HAS_INFLUXDB_08:
        return __virtualname__
    return (False, 'The influx execution module cannot be loaded: influxdb library not available.')


def _client(user=None, password=None, host=None, port=None):
    if not user:
        user = __salt__['config.option']('influxdb08.user', 'root')
    if not password:
        password = __salt__['config.option']('influxdb08.password', 'root')
    if not host:
        host = __salt__['config.option']('influxdb08.host', 'localhost')
    if not port:
        port = __salt__['config.option']('influxdb08.port', 8086)
    return influxdb.influxdb08.InfluxDBClient(
        host=host, port=port, username=user, password=password)


def db_list(user=None, password=None, host=None, port=None):
    '''
    List all InfluxDB databases

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.db_list
        salt '*' influxdb08.db_list <user> <password> <host> <port>

    '''
    client = _client(user=user, password=password, host=host, port=port)
    return client.get_list_database()


def db_exists(name, user=None, password=None, host=None, port=None):
    '''
    Checks if a database exists in Influxdb

    name
        Database name to create

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.db_exists <name>
        salt '*' influxdb08.db_exists <name> <user> <password> <host> <port>
    '''
    dbs = db_list(user, password, host, port)
    if not isinstance(dbs, list):
        return False
    return name in [db['name'] for db in dbs]


def db_create(name, user=None, password=None, host=None, port=None):
    '''
    Create a database

    name
        Database name to create

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.db_create <name>
        salt '*' influxdb08.db_create <name> <user> <password> <host> <port>
    '''
    if db_exists(name, user, password, host, port):
        log.info('DB \'%s\' already exists', name)
        return False
    client = _client(user=user, password=password, host=host, port=port)
    client.create_database(name)
    return True


def db_remove(name, user=None, password=None, host=None, port=None):
    '''
    Remove a database

    name
        Database name to remove

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.db_remove <name>
        salt '*' influxdb08.db_remove <name> <user> <password> <host> <port>
    '''
    if not db_exists(name, user, password, host, port):
        log.info('DB \'%s\' does not exist', name)
        return False
    client = _client(user=user, password=password, host=host, port=port)
    return client.delete_database(name)


def user_list(database=None, user=None, password=None, host=None, port=None):
    '''
    List cluster admins or database users.

    If a database is specified: it will return database users list.
    If a database is not specified: it will return cluster admins list.

    database
        The database to list the users from

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.user_list
        salt '*' influxdb08.user_list <database>
        salt '*' influxdb08.user_list <database> <user> <password> <host> <port>
    '''
    client = _client(user=user, password=password, host=host, port=port)

    if not database:
        return client.get_list_cluster_admins()

    client.switch_database(database)
    return client.get_list_users()


def user_exists(name, database=None, user=None, password=None, host=None, port=None):
    '''
    Checks if a cluster admin or database user exists.

    If a database is specified: it will check for database user existence.
    If a database is not specified: it will check for cluster admin existence.

    name
        User name

    database
        The database to check for the user to exist

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.user_exists <name>
        salt '*' influxdb08.user_exists <name> <database>
        salt '*' influxdb08.user_exists <name> <database> <user> <password> <host> <port>
    '''
    users = user_list(database, user, password, host, port)
    if not isinstance(users, list):
        return False

    for user in users:
        # the dict key could be different depending on influxdb version
        username = user.get('user', user.get('name'))
        if username:
            if username == name:
                return True
        else:
            log.warning('Could not find username in user: %s', user)

    return False


def user_create(name,
                passwd,
                database=None,
                user=None,
                password=None,
                host=None,
                port=None):
    '''
    Create a cluster admin or a database user.

    If a database is specified: it will create database user.
    If a database is not specified: it will create a cluster admin.

    name
        User name for the new user to create

    passwd
        Password for the new user to create

    database
        The database to create the user in

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.user_create <name> <passwd>
        salt '*' influxdb08.user_create <name> <passwd> <database>
        salt '*' influxdb08.user_create <name> <passwd> <database> <user> <password> <host> <port>
    '''
    if user_exists(name, database, user, password, host, port):
        if database:
            log.info('User \'%s\' already exists for DB \'%s\'', name, database)
        else:
            log.info('Cluster admin \'%s\' already exists', name)
        return False

    client = _client(user=user, password=password, host=host, port=port)

    if not database:
        return client.add_cluster_admin(name, passwd)

    client.switch_database(database)
    return client.add_database_user(name, passwd)


def user_chpass(name,
                passwd,
                database=None,
                user=None,
                password=None,
                host=None,
                port=None):
    '''
    Change password for a cluster admin or a database user.

    If a database is specified: it will update database user password.
    If a database is not specified: it will update cluster admin password.

    name
        User name for whom to change the password

    passwd
        New password

    database
        The database on which to operate

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.user_chpass <name> <passwd>
        salt '*' influxdb08.user_chpass <name> <passwd> <database>
        salt '*' influxdb08.user_chpass <name> <passwd> <database> <user> <password> <host> <port>
    '''
    if not user_exists(name, database, user, password, host, port):
        if database:
            log.info('User \'%s\' does not exist for DB \'%s\'', name, database)
        else:
            log.info('Cluster admin \'%s\' does not exist', name)
        return False

    client = _client(user=user, password=password, host=host, port=port)

    if not database:
        return client.update_cluster_admin_password(name, passwd)

    client.switch_database(database)
    return client.update_database_user_password(name, passwd)


def user_remove(name,
                database=None,
                user=None,
                password=None,
                host=None,
                port=None):
    '''
    Remove a cluster admin or a database user.

    If a database is specified: it will remove the database user.
    If a database is not specified: it will remove the cluster admin.

    name
        User name to remove

    database
        The database to remove the user from

    user
        User name for the new user to delete

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.user_remove <name>
        salt '*' influxdb08.user_remove <name> <database>
        salt '*' influxdb08.user_remove <name> <database> <user> <password> <host> <port>
    '''
    if not user_exists(name, database, user, password, host, port):
        if database:
            log.info('User \'%s\' does not exist for DB \'%s\'', name, database)
        else:
            log.info('Cluster admin \'%s\' does not exist', name)
        return False

    client = _client(user=user, password=password, host=host, port=port)

    if not database:
        return client.delete_cluster_admin(name)

    client.switch_database(database)
    return client.delete_database_user(name)


def retention_policy_get(database,
                         name,
                         user=None,
                         password=None,
                         host=None,
                         port=None):
    '''
    Get an existing retention policy.

    database
        The database to operate on.

    name
        Name of the policy to modify.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.retention_policy_get metrics default
    '''
    client = _client(user=user, password=password, host=host, port=port)

    for policy in client.get_list_retention_policies(database):
        if policy['name'] == name:
            return policy

    return None


def retention_policy_exists(database,
                            name,
                            user=None,
                            password=None,
                            host=None,
                            port=None):
    '''
    Check if a retention policy exists.

    database
        The database to operate on.

    name
        Name of the policy to modify.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.retention_policy_exists metrics default
    '''
    policy = retention_policy_get(database, name, user, password, host, port)
    return policy is not None


def retention_policy_add(database,
                         name,
                         duration,
                         replication,
                         default=False,
                         user=None,
                         password=None,
                         host=None,
                         port=None):
    '''
    Add a retention policy.

    database
        The database to operate on.

    name
        Name of the policy to modify.

    duration
        How long InfluxDB keeps the data.

    replication
        How many copies of the data are stored in the cluster.

    default
        Whether this policy should be the default or not. Default is False.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.retention_policy_add metrics default 1d 1
    '''
    client = _client(user=user, password=password, host=host, port=port)
    client.create_retention_policy(name, duration, replication, database, default)
    return True


def retention_policy_alter(database,
                           name,
                           duration,
                           replication,
                           default=False,
                           user=None,
                           password=None,
                           host=None,
                           port=None):
    '''
    Modify an existing retention policy.

    database
        The database to operate on.

    name
        Name of the policy to modify.

    duration
        How long InfluxDB keeps the data.

    replication
        How many copies of the data are stored in the cluster.

    default
        Whether this policy should be the default or not. Default is False.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.retention_policy_modify metrics default 1d 1
    '''
    client = _client(user=user, password=password, host=host, port=port)
    client.alter_retention_policy(name, database, duration, replication, default)
    return True


def query(database,
          query,
          time_precision='s',
          chunked=False,
          user=None,
          password=None,
          host=None,
          port=None):
    '''
    Querying data

    database
        The database to query

    query
        Query to be executed

    time_precision
        Time precision to use ('s', 'm', or 'u')

    chunked
        Whether is chunked or not

    user
        The user to connect as

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.query <database> <query>
        salt '*' influxdb08.query <database> <query> <time_precision> <chunked> <user> <password> <host> <port>
    '''
    client = _client(user=user, password=password, host=host, port=port)
    client.switch_database(database)
    return client.query(query, time_precision=time_precision, chunked=chunked)


def login_test(name, password, database=None, host=None, port=None):
    '''
    Checks if a credential pair can log in at all.

    If a database is specified: it will check for database user existence.
    If a database is not specified: it will check for cluster admin existence.

    name
        The user to connect as

    password
        The password of the user

    database
        The database to try to log in to

    host
        The host to connect to

    port
        The port to connect to

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb08.login_test <name>
        salt '*' influxdb08.login_test <name> <database>
        salt '*' influxdb08.login_test <name> <database> <user> <password> <host> <port>
    '''
    try:
        client = _client(user=name, password=password, host=host, port=port)
        client.get_list_database()
        return True
    except influxdb.influxdb08.client.InfluxDBClientError as e:
        if e.code == 401:
            return False
        else:
            raise
