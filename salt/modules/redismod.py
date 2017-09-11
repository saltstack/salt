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


def _get_kwargs_opts(**options):
    '''
    Return the Redis connection details from kwargs.
    '''
    host = options.get('host', None)
    port = options.get('port', None)
    database = options.get('db', None)
    password = options.get('password', None)
    return (host, port, database, password)


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


def hdel(key, *fields, **options):
    '''
    Delete one of more hash fields.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hdel foo_hash bar_field1 bar_field2
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.hdel(key, *fields)


def hexists(key, field, host=None, port=None, db=None, password=None):
    '''
    Determine if a hash fields exists.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hexists foo_hash bar_field
    '''
    server = _connect(host, port, db, password)
    return server.hexists(key, field)


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


def hincrby(key, field, increment=1, host=None, port=None, db=None, password=None):
    '''
    Increment the integer value of a hash field by the given number.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hincrby foo_hash bar_field 5
    '''
    server = _connect(host, port, db, password)
    return server.hincrby(key, field, amount=increment)


def hincrbyfloat(key, field, increment=1.0, host=None, port=None, db=None, password=None):
    '''
    Increment the float value of a hash field by the given number.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hincrbyfloat foo_hash bar_field 5.17
    '''
    server = _connect(host, port, db, password)
    return server.hincrbyfloat(key, field, amount=increment)


def hlen(key, host=None, port=None, db=None, password=None):
    '''
    Returns number of fields of a hash.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hlen foo_hash
    '''
    server = _connect(host, port, db, password)
    return server.hlen(key)


def hmget(key, *fields, **options):
    '''
    Returns the values of all the given hash fields.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hmget foo_hash bar_field1 bar_field2
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.hmget(key, *fields)


def hmset(key, **fieldsvals):
    '''
    Sets multiple hash fields to multiple values.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hmset foo_hash bar_field1=bar_value1 bar_field2=bar_value2
    '''
    host = fieldsvals.pop('host', None)
    port = fieldsvals.pop('port', None)
    database = fieldsvals.pop('db', None)
    password = fieldsvals.pop('password', None)
    server = _connect(host, port, database, password)
    return server.hmset(key, **fieldsvals)


def hset(key, field, value, host=None, port=None, db=None, password=None):
    '''
    Set the value of a hash field.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hset foo_hash bar_field bar_value
    '''
    server = _connect(host, port, db, password)
    return server.hset(key, field, value)


def hsetnx(key, field, value, host=None, port=None, db=None, password=None):
    '''
    Set the value of a hash field only if the field does not exist.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hsetnx foo_hash bar_field bar_value
    '''
    server = _connect(host, port, db, password)
    return server.hsetnx(key, field, value)


def hvals(key, host=None, port=None, db=None, password=None):
    '''
    Return all the values in a hash.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hvals foo_hash bar_field1 bar_value1
    '''
    server = _connect(host, port, db, password)
    return server.hvals(key)


def hscan(key, cursor=0, match=None, count=None, host=None, port=None, db=None, password=None):
    '''
    Incrementally iterate hash fields and associated values.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' redis.hscan foo_hash match='field_prefix_*' count=1
    '''
    server = _connect(host, port, db, password)
    return server.hscan(key, cursor=cursor, match=match, count=count)


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


def sadd(key, *members, **options):
    '''
    Add the specified members to the set stored at key.
    Specified members that are already a member of this set are ignored.
    If key does not exist, a new set is created before adding the specified members.
    An error is returned when the value stored at key is not a set.

    Returns:
        The number of elements that were added to the set,
        not including all the elements already present into the set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sadd foo_set foo_member bar_member
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sadd(key, *members)


def scard(key, host=None, port=None, db=None, password=None):
    '''
    Returns the set cardinality (number of elements) of the set stored at key.
    Keys that do not exist are considered to be empty sets.

    Returns:
        The cardinality (number of elements) of the set,
        or 0 if key does not exist.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.scard foo_set
    '''
    server = _connect(host, port, db, password)
    return server.scard(key)


def sdiff(key, *keys, **options):
    '''
    Returns the members of the set resulting from the difference
    between the first set and all the successive sets.

    Returns:
        List with members of the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sdiff foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sdiff(key, *keys)


def sdiffstore(destination, key, *keys, **options):
    '''
    This command is equal to :mod:`redis.sdiff <salt.modules.redismod.sdiff>`,
    but instead of returning the resulting set, it is stored in ``destination``.
    If ``destination`` already exists, it is overwritten.

    Returns:
        The number of elements in the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sdiffstore destination_set foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sdiffstore(destination, key, *keys)


def sinter(key, *keys, **options):
    '''
    Returns the members of the set resulting
    from the intersection of all the given sets.
    Keys that do not exist are considered to be empty sets.
    With one of the keys being an empty set,
    the resulting set is also empty
    (since set intersection with an empty set always results in an empty set).

    Returns:
        List with members of the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sinter foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sinter(key, *keys)


def sinterstore(destination, key, *keys, **options):
    '''
    This command is equal to :mod:`redis.sinter <salt.modules.redismod.sinter>`,
    but instead of returning the resulting set, it is stored in ``destination``.
    If ``destination`` already exists, it is overwritten.

    Returns:
        The number of elements in the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sinterstore dest foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sinterstore(destination, key, *keys)


def sismember(key, member, host=None, port=None, db=None, password=None):
    '''
    Returns if ``member`` is a member of the set stored at key.

    Returns:
        - ``1`` if the element is a member of the set.
        - ``0`` if the element is not a member of the set, or if key does not exist.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sismember foo_set bar_member
    '''
    server = _connect(host, port, db, password)
    return server.sismember(key, member)


def smembers(key, host=None, port=None, db=None, password=None):
    '''
    Get members in a Redis set

    CLI Example:

    .. code-block:: bash

        salt '*' redis.smembers foo_set
    '''
    server = _connect(host, port, db, password)
    return list(server.smembers(key))


def smove(source, destination, member, host=None, port=None, db=None, password=None):
    '''
    Move member from the set at ``source`` to the set at ``destination``.
    This operation is atomic. In every given moment the element
    will appear to be a member of ``source`` or ``destination`` for other clients.
    If the ``source`` set does not exist or does not contain the specified element,
    no operation is performed and ``0`` is returned.
    Otherwise, the element is removed from the ``source`` set and added
    to the ``destination`` set. When the specified element already exists
    in the ``destination`` set, it is only removed from the source set.
    An error is returned if ``source`` or ``destination`` does not hold a set value.

    Returns:
        - ``1`` if the element is moved.
        - ``0`` if the element is not a member of source and no operation was performed.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.smove foo_source bar_destination baz_member
    '''
    server = _connect(host, port, db, password)
    return server.smove(source, destination, member)


def spop(key, host=None, port=None, db=None, password=None):
    '''
    Removes and returns one or more random elements
    from the set value store at ``key``.
    This operation is similar to :mod:`redis.srandmember <salt.modules.redismod.srandmember>`,
    that returns one or more random elements from a set but does not remove it.

    Returns:
        The removed element, or ``None`` when ``key`` does not exist.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.spop foo_set
    '''
    server = _connect(host, port, db, password)
    return server.spop(key)


def srandmember(key, count=None, host=None, port=None, db=None, password=None):
    '''
    When called with just the ``key`` argument,
    return a random element from the set value stored at ``key``.
    When called with the additional ``count`` argument,
    return an array of ``count`` distinct elements if ``count`` is positive.
    If called with a negative ``count`` the behavior changes
    and the command is allowed to return the same element multiple times.
    In this case the number of returned elements
    is the absolute value of the specified ``count``.
    When called with just the ``key`` argument,
    the operation is similar to :mod:`redis.spop <salt.modules.redismod.spop>`,
    however while :mod:`redis.spop <salt.modules.redismod.spop>` also removes
    the randomly selected element from the set, ``srandmember`` will just return
    a random element without altering the original set in any way.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.srandmember foo_set
    '''
    server = _connect(host, port, db, password)
    return server.srandmember(key, number=count)


def srem(key, *members, **options):
    '''
    Remove the specified members from the set stored at ``key``.
    Specified members that are not a member of this set are ignored.
    If ``key`` does not exist, it is treated as an empty set and this command returns ``0``.
    An error is returned when the value stored at ``key`` is not a set.

    Returns:
        The number of members that were removed from the set,
        not including non existing members.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.srem foo_set bar_member baz_member
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.srem(key, *members)


def sunion(key, *keys, **options):
    '''
    Returns the members of the set resulting from the union of all the given sets.
    Keys that do not exist are considered to be empty sets.

    Returns:
        List with members of the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sunion foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sunion(key, *keys)


def sunionstore(destination, key, *keys, **options):
    '''
    This command is equal to :mod:`redis.sunion <salt.modules.redismod.sunion>`,
    but instead of returning the resulting set, it is stored in ``destination``.
    If ``destination`` already exists, it is overwritten.

    Returns:
        The number of elements in the resulting set.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sunionstore destination_set foo_set bar_set baz_set
    '''
    (host, port, databse, password) = _get_kwargs_opts(**options)
    server = _connect(host, port, database, password)
    return server.sunionstore(destination, key, *keys)


def sscan(key, cursor=0, match=None, count=None, host=None, port=None, db=None, password=None):
    '''
    Incrementally return lists of elements in a set.
    Also return a cursor indicating the scan position.

    .. versionadded:: Nitrogen

    CLI Example:

    .. code-block:: bash

        salt '*' redis.sscan foo_set match='field_prefix_*' count=1
    '''
    server = _connect(host, port, db, password)
    return server.sscan(key, cursor=cursor, match=match, count=count)


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
    srv_info = server.info()
    ret = (srv_info.get('master_host', ''), srv_info.get('master_port', ''))
    return dict(list(zip(('master_host', 'master_port'), ret)))
