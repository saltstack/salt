# -*- coding: utf-8 -*-
'''
Module to provide redis functionality to Salt

:configuration: This module requires the redis python module and uses the
    following defaults which may be overridden in the minion configuration:

        redis.host: 'localhost'
        redis.port: 6379
        redis.db: 0
        redis.password: None
'''

# Import third party libs
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

__virtualname__ = 'redis'


def __virtual__():
    '''
    Only load this module if redis python module is installed
    '''
    if HAS_REDIS:
        return __virtualname__
    else:
        return False


def _connect(host=None, port=None, db=None, password=None):
    '''
    Returns an instance of the redis client
    '''
    if not host:
        host = __salt__['config.option']('redis.host')
    if not port:
        port = __salt__['config.option']('redis.port')
    if not db:
        db = __salt__['config.option']('redis.db')
    if not password:
        password = __salt__['config.option']('redis.password')

    return redis.StrictRedis(host, port, db, password)


def bgrewriteaof(host=None, port=None, db=None, password=None):
    '''
    Asynchronously rewrite the append-only file

    CLI Example:

    .. code-block:: bash

        salt '*' redis.bgrewriteaof
    '''
    server = _connect(host, port, db, password)
    return server.bgrewriteaof()


def bgsave(host=None, port=None, db=None, password=None):
    '''
    Asynchronously save the dataset to disk

    CLI Example:

    .. code-block:: bash

        salt '*' redis.bgsave
    '''
    server = _connect(host, port, db, password)
    return server.bgsave()


def config_get(pattern='*', host=None, port=None, db=None, password=None):
    '''
    Get redis server configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' redis.config_get
        salt '*' redis.config_get port
    '''
    server = _connect(host, port, db, password)
    return server.config_get(pattern)


def config_set(name, value, host=None, port=None, db=None, password=None):
    '''
    Set redis server configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' redis.config_set masterauth luv_kittens
    '''
    server = _connect(host, port, db, password)
    return server.config_set(name, value)


def dbsize(host=None, port=None, db=None, password=None):
    '''
    Return the number of keys in the selected database

    CLI Example:

    .. code-block:: bash

        salt '*' redis.dbsize
    '''
    server = _connect(host, port, db, password)
    return server.dbsize()


def flushall(host=None, port=None, db=None, password=None):
    '''
    Remove all keys from all databases

    CLI Example:

    .. code-block:: bash

        salt '*' redis.flushall
    '''
    server = _connect(host, port, db, password)
    return server.flushall()


def flushdb(host=None, port=None, db=None, password=None):
    '''
    Remove all keys from the selected database

    CLI Example:

    .. code-block:: bash

        salt '*' redis.flushdb
    '''
    server = _connect(host, port, db, password)
    return server.flushdb()


def get_key(key, host=None, port=None, db=None, password=None):
    '''
    Get redis key value

    CLI Example:

    .. code-block:: bash

        salt '*' redis.get_key foo
    '''
    server = _connect(host, port, db, password)
    return server.get(key)


def info(host=None, port=None, db=None, password=None):
    '''
    Get information and statistics about the server

    CLI Example:

    .. code-block:: bash

        salt '*' redis.info
    '''
    server = _connect(host, port, db, password)
    return server.info()


def lastsave(host=None, port=None, db=None, password=None):
    '''
    Get the UNIX time stamp of the last successful save to disk

    CLI Example:

    .. code-block:: bash

        salt '*' redis.lastsave
    '''
    server = _connect(host, port, db, password)
    return str(server.lastsave())


def ping(host=None, port=None, db=None, password=None):
    '''
    Ping the server, returns False on connection errors

    CLI Example:

    .. code-block:: bash

        salt '*' redis.ping
    '''
    server = _connect(host, port, db, password)
    try:
        return server.ping()
    except redis.ConnectionError:
        return False


def save(host=None, port=None, db=None, password=None):
    '''
    Synchronously save the dataset to disk

    CLI Example:

    .. code-block:: bash

        salt '*' redis.save
    '''
    server = _connect(host, port, db, password)
    return server.save()


def set_key(key, value, host=None, port=None, db=None, password=None):
    '''
    Set redis key value

    CLI Example:

    .. code-block:: bash

        salt '*' redis.set_key foo bar
    '''
    server = _connect(host, port, db, password)
    return server.set(key, value)


def shutdown(host=None, port=None, db=None, password=None):
    '''
    Synchronously save the dataset to disk and then shut down the server

    CLI Example:

    .. code-block:: bash

        salt '*' redis.shutdown
    '''
    server = _connect(host, port, db, password)
    try:
        # Return false if unable to ping server
        server.ping()
    except redis.ConnectionError:
        return False

    server.shutdown()
    try:
        # This should fail now if the server is shutdown, which we want
        server.ping()
    except redis.ConnectionError:
        return True
    return False


def slaveof(master_host=None, master_port=None, host=None, port=None, db=None, password=None):
    '''
    Make the server a slave of another instance, or promote it as master

    CLI Example:

    .. code-block:: bash
        # Become slave of redis-n01.example.com:6379
        salt '*' redis.slaveof redis-n01.example.com 6379
        salt '*' redis.slaveof redis-n01.example.com
        # Become master
        salt '*' redis.slaveof
    '''
    if master_host and not master_port:
        master_port = 6379
    server = _connect(host, port, db, password)
    return server.slaveof(master_host, master_port)


def time(host=None, port=None, db=None, password=None):
    '''
    Return the current server time

    CLI Example:

    .. code-block:: bash

        salt '*' redis.time
    '''
    server = _connect(host, port, db, password)
    return server.time()[0]
