# -*- coding: utf-8 -*-
'''
Module to provide redis functionality to Salt

.. versionadded:: 2014.7.0

:configuration: This module requires the redis python module and uses the
    following defaults which may be overridden in the minion configuration:

.. code-block:: yaml

    redis.host: 'localhost'
    redis.port: 6379
    redis.db: 0
    redis.password: None
'''

# Import Python libs
from __future__ import absolute_import
from salt.ext.six.moves import zip

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
        return (False, 'The redis execution module failed to load: the redis python library is not available.')


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


def _sconnect(host=None, port=None, password=None):
    '''
    Returns an instance of the redis client
    '''
    if host is None:
        host = __salt__['config.option']('redis_sentinel.host', 'localhost')
    if port is None:
        port = __salt__['config.option']('redis_sentinel.port', 26379)
    if password is None:
        password = __salt__['config.option']('redis_sentinel.password')

    return redis.StrictRedis(host, port, password=password)


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


def delete(*keys, **connection_args):
    '''
    Deletes the keys from redis, returns number of keys deleted

    CLI Example:

    .. code-block:: bash

        salt '*' redis.delete foo
    '''
    # Get connection args from keywords if set
    conn_args = {}
    for arg in ['host', 'port', 'db', 'password']:
        if arg in connection_args:
            conn_args[arg] = connection_args[arg]

    server = _connect(**conn_args)
    return server.delete(*keys)


def exists(key, host=None, port=None, db=None, password=None):
    '''
    Return true if the key exists in redis

    CLI Example:

    .. code-block:: bash

        salt '*' redis.exists foo
    '''
    server = _connect(host, port, db, password)
    return server.exists(key)


def expire(key, seconds, host=None, port=None, db=None, password=None):
    '''
    Set a keys time to live in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' redis.expire foo 300
    '''
    server = _connect(host, port, db, password)
    return server.expire(key, seconds)


def expireat(key, timestamp, host=None, port=None, db=None, password=None):
    '''
    Set a keys expire at given UNIX time

    CLI Example:

    .. code-block:: bash

        salt '*' redis.expireat foo 1400000000
    '''
    server = _connect(host, port, db, password)
    return server.expireat(key, timestamp)


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


def hget(key, field, host=None, port=None, db=None, password=None):
    '''
    Get specific field value from a redis hash, returns dict

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hget foo_hash bar_field
    '''
    server = _connect(host, port, db, password)
    return server.hget(key, field)


def hgetall(key, host=None, port=None, db=None, password=None):
    '''
    Get all fields and values from a redis hash, returns dict

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hgetall foo_hash
    '''
    server = _connect(host, port, db, password)
    return server.hgetall(key)


def info(host=None, port=None, db=None, password=None):
    '''
    Get information and statistics about the server

    CLI Example:

    .. code-block:: bash

        salt '*' redis.info
    '''
    server = _connect(host, port, db, password)
    return server.info()


def keys(pattern='*', host=None, port=None, db=None, password=None):
    '''
    Get redis keys, supports glob style patterns

    CLI Example:

    .. code-block:: bash

        salt '*' redis.keys
        salt '*' redis.keys test*
    '''
    server = _connect(host, port, db, password)
    return server.keys(pattern)


def key_type(key, host=None, port=None, db=None, password=None):
    '''
    Get redis key type

    CLI Example:

    .. code-block:: bash

        salt '*' redis.type foo
    '''
    server = _connect(host, port, db, password)
    return server.type(key)


def lastsave(host=None, port=None, db=None, password=None):
    '''
    Get the UNIX time in seconds of the last successful save to disk

    CLI Example:

    .. code-block:: bash

        salt '*' redis.lastsave
    '''
    server = _connect(host, port, db, password)
    return int(server.lastsave().strftime("%s"))


def llen(key, host=None, port=None, db=None, password=None):
    '''
    Get the length of a list in Redis

    CLI Example:

    .. code-block:: bash

        salt '*' redis.llen foo_list
    '''
    server = _connect(host, port, db, password)
    return server.llen(key)


def lrange(key, start, stop, host=None, port=None, db=None, password=None):
    '''
    Get a range of values from a list in Redis

    CLI Example:

    .. code-block:: bash

        salt '*' redis.lrange foo_list 0 10
    '''
    server = _connect(host, port, db, password)
    return server.lrange(key, start, stop)


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


def slaveof(master_host=None, master_port=None, host=None, port=None, db=None,
            password=None):
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


def smembers(key, host=None, port=None, db=None, password=None):
    '''
    Get members in a Redis set

    CLI Example:

    .. code-block:: bash

        salt '*' redis.smembers foo_set
    '''
    server = _connect(host, port, db, password)
    return list(server.smembers(key))


def time(host=None, port=None, db=None, password=None):
    '''
    Return the current server UNIX time in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' redis.time
    '''
    server = _connect(host, port, db, password)
    return server.time()[0]


def zcard(key, host=None, port=None, db=None, password=None):
    '''
    Get the length of a sorted set in Redis

    CLI Example:

    .. code-block:: bash

        salt '*' redis.zcard foo_sorted
    '''
    server = _connect(host, port, db, password)
    return server.zcard(key)


def zrange(key, start, stop, host=None, port=None, db=None, password=None):
    '''
    Get a range of values from a sorted set in Redis by index

    CLI Example:

    .. code-block:: bash

        salt '*' redis.zrange foo_sorted 0 10
    '''
    server = _connect(host, port, db, password)
    return server.zrange(key, start, stop)


def sentinel_get_master_ip(master, host=None, port=None, password=None):
    '''
    Get ip for sentinel master

    .. versionadded: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sentinel_get_master_ip 'mymaster'
    '''
    server = _sconnect(host, port, password)
    ret = server.sentinel_get_master_addr_by_name(master)
    return dict(list(zip(('master_host', 'master_port'), ret)))


def get_master_ip(host=None, port=None, password=None):
    '''
    Get host information about slave

    .. versionadded: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.get_master_ip
    '''
    server = _connect(host, port, password)
    info = server.info()
    ret = (info.get('master_host', ''), info.get('master_port', ''))
    return dict(list(zip(('master_host', 'master_port'), ret)))
