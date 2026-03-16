r"""
Redis
=====

Redis plugin for the Salt caching subsystem.

.. versionadded:: 2017.7.0
.. versionchanged:: 3005

To enable this cache plugin, the master will need the python client for redis installed.
This can be easily installed with pip:

.. code-block:: bash

    salt \* pip.install redis

To use Redis Cluster the cluster package should be installed:

.. code-block:: bash

    salt \* pip.install redis-py-cluster

As Redis provides a simple mechanism for very fast key-value store, in order to
provide the necessary features for the Salt caching subsystem, the following
conventions are used:

- As the caching subsystem is organised as a tree, we need to store the caching
  path and identify the bank and its offspring.  At the same time, Redis is
  linear and we need to avoid doing ``keys <pattern>`` which is very
  inefficient as it goes through all the keys on the remote Redis server.
  Instead a SORTED SET of all banks is stored in a single value. This can act as
  an index for finding sub-banks. By default this key is prefixed with ``$BANKS_``.
- Each bank is stored as a hash. It is a simple mechanism and allows for fast access
  to the data and of the keys. By default this key is prefixed with ``$KEYS_``.
- An additional hash is used to store the last update time of each cache key. By
  default this key is prefixed with ``$TSTAMP_``.

For example, to store the key ``my-key`` with value ``my-value`` under the bank
``root-bank/sub-bank/leaf-bank``, the following datastructures will be created.

.. code-block:: text

    127.0.0.1:6379> ZSCAN $BANKS_ 0
    1) "0"
    2) 1) "$KEYS_root-bank/sub-bank/leaf-bank/"
       2) "0"
    127.0.0.1:6379> HGETALL $KEYS_root-bank/sub-bank/leaf-bank/
    1) "my-key"
    2) "my-value"
    127.0.0.1:6379> HGETALL $TSTAMP_root-bank/sub-bank/leaf-bank/
    1) "my-key"
    2) "1773671718"


There are four types of keys stored:

- ``$BANKS_*`` is a Redis SORTED SET containing the list of all banks
- ``$KEYS_*`` is a Redis SET containing key, value pairs of the current bank.
- ``$TSTAMP_*`` stores the last updated timestamp of the key.

These prefixes and the separator can be adjusted using the configuration options:

banks_prefix: ``$BANK``
    The prefix used for the name of the Redis key storing the sorted set of banks.

keys_prefix: ``$KEY``
    The prefix of the Redis keys having the value of the keys to be cached under
    a certain bank.

timestamp_prefix: ``$TSTAMP``
    The prefix for the last modified timestamp for keys.

    .. versionadded:: 3005

separator: ``_``
    The separator between the prefix and the key body.

The connection details can be specified using:

host: ``localhost``
    The hostname of the Redis server.

port: ``6379``
    The Redis server port.

cluster_mode: ``False``
    Whether cluster_mode is enabled or not

cluster.startup_nodes:
    A list of host, port dictionaries pointing to cluster members. At least one is required
    but multiple nodes are better

    .. code-block:: yaml

        cache.redis.cluster.startup_nodes
          - host: redis-member-1
            port: 6379
          - host: redis-member-2
            port: 6379

cluster.skip_full_coverage_check: ``False``
    Some cluster providers restrict certain redis commands such as CONFIG for enhanced security.
    Set this option to true to skip checks that required advanced privileges.

    .. note::

        Most cloud hosted redis clusters will require this to be set to ``True``

db: ``'0'``
    The database index.

    .. note::
        The database index must be specified as string not as integer value!

password:
    Redis connection password.

unix_socket_path:

    .. versionadded:: 2018.3.1

    Path to a UNIX socket for access. Overrides `host` / `port`.

Configuration Example:

.. code-block:: yaml

    cache.redis.host: localhost
    cache.redis.port: 6379
    cache.redis.db: '0'
    cache.redis.password: my pass
    cache.redis.banks_prefix: #BANKS
    cache.redis.keys_prefix: #KEYS
    cache.redis.timestamp_prefix: #TSTAMP
    cache.redis.separator: '_'

Cluster Configuration Example:

.. code-block:: yaml

    cache.redis.cluster_mode: true
    cache.redis.cluster.skip_full_coverage_check: true
    cache.redis.cluster.startup_nodes:
      - host: redis-member-1
        port: 6379
      - host: redis-member-2
        port: 6379
    cache.redis.db: '0'
    cache.redis.password: my pass
    cache.redis.banks_prefix: #BANKS
    cache.redis.keys_prefix: #KEYS
    cache.redis.timestamp_prefix: #TSTAMP
    cache.redis.separator: '_'
"""

import logging
import time

import salt.payload
import salt.utils.stringutils
from salt.exceptions import SaltCacheError

# Import salt

try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import ResponseError as RedisResponseError

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    from rediscluster import RedisCluster  # pylint: disable=no-name-in-module

    HAS_REDIS_CLUSTER = True
except ImportError:
    HAS_REDIS_CLUSTER = False


# -----------------------------------------------------------------------------
# module properties
# -----------------------------------------------------------------------------

__virtualname__ = "redis"
__func_alias__ = {"list_": "list"}

log = logging.getLogger(__file__)

_BANKS_PREFIX = "$BANKS"
_KEYS_PREFIX = "$KEYS"
_TIMESTAMP_PREFIX = "$TSTAMP"
_SEPARATOR = "_"

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    The redis library must be installed for this module to work.

    The redis redis cluster library must be installed if cluster_mode is True
    """
    if not HAS_REDIS:
        return (False, "Please install the redis package.")
    if not HAS_REDIS_CLUSTER and _get_redis_cache_opts()["cluster_mode"]:
        return (False, "Please install the redis-py-cluster package.")
    return __virtualname__


# -----------------------------------------------------------------------------
# helper functions -- will not be exported
# -----------------------------------------------------------------------------


def init_kwargs(kwargs):
    """
    Effectively a noop. Return an empty dictionary.
    """
    return {}


def _get_redis_cache_opts():
    """
    Return the Redis server connection details from the __opts__.
    """
    sep = __opts__.get("cache.redis.separator", _SEPARATOR)
    opts = {
        "host": __opts__.get("cache.redis.host", "localhost"),
        "port": __opts__.get("cache.redis.port", 6379),
        "unix_socket_path": __opts__.get("cache.redis.unix_socket_path", None),
        "db": __opts__.get("cache.redis.db", "0"),
        "password": __opts__.get("cache.redis.password", ""),
        "cluster_mode": __opts__.get("cache.redis.cluster_mode", False),
        "startup_nodes": __opts__.get("cache.redis.cluster.startup_nodes", {}),
        "skip_full_coverage_check": __opts__.get(
            "cache.redis.cluster.skip_full_coverage_check", False
        ),
        "banks_prefix": __opts__.get("cache.redis.banks_prefix", _BANKS_PREFIX) + sep,
        "keys_prefix": __opts__.get("cache.redis.keys_prefix", _KEYS_PREFIX) + sep,
        "timestamp_prefix": __opts__.get("cache.redis.timestamp_prefix", _TIMESTAMP_PREFIX) + sep,
    }
    prefix_confs = [opts["banks_prefix"], opts["keys_prefix"], opts["timestamp_prefix"]]
    if any("/" in conf for conf in prefix_confs):
        mesg = "Slash '/' cannot be used in redis cache prefix configuration."
        log.error(mesg)
        raise SaltCacheError(mesg)
    return opts


def _get_redis_server():
    """
    Return the Redis server instance.
    Caching the object instance.
    """
    redis_server = __context__.get("cache.redis", {}).get("client")
    if redis_server is not None:
        return redis_server
    opts = _get_redis_cache_opts()
    if opts["cluster_mode"]:
        redis_server = RedisCluster(
            startup_nodes=opts["startup_nodes"],
            skip_full_coverage_check=opts["skip_full_coverage_check"],
        )
    else:
        redis_server = redis.StrictRedis(
            opts["host"],
            opts["port"],
            unix_socket_path=opts["unix_socket_path"],
            db=opts["db"],
            password=opts["password"],
        )
    __context__["cache.redis"] = {
        "client": redis_server,
        "banks_prefix": opts["banks_prefix"],
        "keys_prefix": opts["keys_prefix"],
        "timestamp_prefix": opts["timestamp_prefix"],
    }
    return __context__["cache.redis"]["client"]


def _banks_set_key():
    """
    Return the Redis key that stores all banks.
    """
    return __context__["cache.redis"]["banks_prefix"]


def _normalize_bank(bank):
    """
    Return the normalized bank key and bank timestamp names.
    """
    bankname = "{0}/".format(bank.rstrip("/"))
    return (
        "{0}{1}".format(__context__["cache.redis"]["keys_prefix"], bankname),
        "{0}{1}".format(__context__["cache.redis"]["timestamp_prefix"], bankname),
    )


def _timestamp_from_bank_key(bank_key):
    """
    Convert a bank key into a timestamp key.
    """
    return '{0}{1}'.format(
        __context__['cache.redis']['timestamp_prefix'],
        bank_key.removeprefix(__context__['cache.redis']['keys_prefix']),
    )


def _flush_key(bank, key):
    """
    Remove the key from the cache.

    If this is the last key in the bank then also remove the bank from the list of banks.
    """
    redis_server = _get_redis_server()
    bank_key, timestamp_key = _normalize_bank(bank)
    redis_pipe = redis_server.pipeline()
    redis_pipe.hdel(bank_key, key)
    redis_pipe.hdel(timestamp_key, key)
    redis_pipe.exists(bank_key)
    batch_results = redis_pipe.execute()
    # I wish this could be made atomic, but it relies on the previous result. Scripts could make it
    # atomic, but that's a lot of overhead..
    if not batch_results[-1]:
        redis_server.zrem(_banks_set_key(), bank_key)


def _flush_bank(bank):
    """
    Clear out an entire bank and subbanks.
    """
    redis_server = _get_redis_server()
    bank_key, timestamp_key = _normalize_bank(bank)
    subbanks = _get_subbanks(redis_server, bank_key)
    if not subbanks:
        return
    redis_pipe = redis_server.pipeline()
    redis_pipe.zrem(_banks_set_key(), *subbanks)
    redis_pipe.unlink(*subbanks)
    redis_pipe.unlink(*[_timestamp_from_bank_key(bank_key) for bank_key in subbanks])
    redis_pipe.execute()


def _get_subbanks(redis_server, bank_key):
    """
    Scan the BANKS key for the sub banks of the given bank.

    The function will also return the current bank if it exists.
    """
    startrange = "[{0}".format(bank_key)
    endrange = "({0}0".format(bank_key.rstrip("/"))
    return list(_decode(redis_server.zrange(_banks_set_key(), startrange, endrange, bylex=True)))


def _decode(iterable):
    """
    Decode the iterable.
    """
    yield from (item.decode("utf8") for item in iterable)


# -----------------------------------------------------------------------------
# cache subsystem functions
# -----------------------------------------------------------------------------


def store(bank, key, data):
    """
    Store the data in a Redis key.
    """
    redis_server = _get_redis_server()
    bank_key, timestamp_key = _normalize_bank(bank)
    redis_pipe = redis_server.pipeline()
    try:
        redis_pipe.zadd(_banks_set_key(), {bank_key: 0})
        redis_pipe.hset(bank_key, key, salt.payload.dumps(data))
        redis_pipe.hset(timestamp_key, key, salt.payload.dumps(int(time.time())))
        redis_pipe.execute()
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot set the Redis cache key {rbank}.{rkey}: {rerr}".format(
            rbank=bank_key, rkey=key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)


def fetch(bank, key):
    """
    Fetch data from the Redis cache.
    """
    redis_server = _get_redis_server()
    bank_key, _ = _normalize_bank(bank)
    try:
        redis_value = redis_server.hget(bank_key, key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot fetch the Redis cache key {rbank}.{rkey}: {rerr}".format(
            rbank=bank_key, rkey=key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    return {} if redis_value is None else salt.payload.loads(redis_value)


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content. If no key is specified, remove
    the entire bank with all keys and sub-banks inside.
    """
    try:
        if key is None:
            _flush_bank(bank)
        else:
            _flush_key(bank, key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        bank_key, _ = _normalize_bank(bank)
        if key is None:
            mesg = "Cannot flush Redis cache bank {rbank}: {rerr}".format(
                rbank=bank_key, rerr=rerr,
            )
        else:
            mesg = "Cannot flush Redis cache key {rbank}.{rkey}: {rerr}".format(
                rbank=bank_key, rkey=key, rerr=rerr,
            )
        log.error(mesg)
        raise SaltCacheError(mesg)
    return True


def list_(bank):
    """
    Lists entries stored in the specified bank.
    """
    redis_server = _get_redis_server()
    bank_key, _ = _normalize_bank(bank)
    try:
        subbanks = _get_subbanks(redis_server, bank_key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot list the Redis cache key subbanks {rbank}: {rerr}".format(
            rbank=bank_key, rerr=rerr,
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    # Unfortunately we get all subsub+ banks from the _get_subbanks() function call. A simple method
    # of filter just the direct descendents is to count the number of slashes. If there is +1 slashes
    # it is a direct descendent. Also strip out the full path and extra gunk for the final listing.
    slashcount = bank_key.count('/') + 1
    listing = [
        sub.removeprefix(bank_key).rstrip('/')
        for sub in subbanks if sub.count('/') == slashcount
    ]
    try:
        listing.extend(_decode(redis_server.hkeys(bank_key)))
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot list the Redis cache key {rbank}: {rerr}".format(
            rbank=bank_key, rerr=rerr,
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    return listing


def contains(bank, key=None):
    """
    Checks if the specified bank contains the specified key.
    """
    redis_server = _get_redis_server()
    bank_key, _ = _normalize_bank(bank)
    try:
        if key is None:
            return bool(redis_server.exists(bank_key))
        return bool(redis_server.hexists(bank_key, key))
    except (RedisConnectionError, RedisResponseError) as rerr:
        if key is None:
            mesg = "Cannot check contains of Redis cache bank {rbank}: {rerr}".format(
                rbank=bank_key, rerr=rerr,
            )
        else:
            mesg = "Cannot check contains of Redis cache key {rbank}.{rkey}: {rerr}".format(
                rbank=bank_key, rkey=key, rerr=rerr,
            )
        log.error(mesg)
        raise SaltCacheError(mesg)


def updated(bank, key):
    """
    Return the Unix Epoch timestamp of when the key was last updated. Return
    None if key is not found.
    """
    redis_server = _get_redis_server()
    _, timestamp_key = _normalize_bank(bank)
    try:
        cache_time = redis_server.hget(timestamp_key, key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot get timestamp of Redis cache key {rstamp}.{rkey}: {rerr}".format(
            rstamp=timestamp_key, rkey=key, rerr=rerr,
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    return None if cache_time is None else salt.payload.loads(cache_time)
