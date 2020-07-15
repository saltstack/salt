# -*- coding: utf-8 -*-
"""
Redis
=====

Redis plugin for the Salt caching subsystem.

.. versionadded:: 2017.7.0

As Redis provides a simple mechanism for very fast key-value store, in order to
privde the necessary features for the Salt caching subsystem, the following
conventions are used:

- A Redis key consists of the bank name and the cache key separated by ``/``, e.g.:
  ``$KEY_minions/alpha/stuff`` where ``minions/alpha`` is the bank name
  and ``stuff`` is the key name.
- As the caching subsystem is organised as a tree, we need to store the caching
  path and identify the bank and its offspring.  At the same time, Redis is
  linear and we need to avoid doing ``keys <pattern>`` which is very
  inefficient as it goes through all the keys on the remote Redis server.
  Instead, each bank hierarchy has a Redis SET associated which stores the list
  of sub-banks. By default, these keys begin with ``$BANK_``.
- In addition, each key name is stored in a separate SET of all the keys within
  a bank. By default, these SETs begin with ``$BANKEYS_``.

For example, to store the key ``my-key`` under the bank ``root-bank/sub-bank/leaf-bank``,
the following hierarchy will be built:

.. code-block:: text

    127.0.0.1:6379> SMEMBERS $BANK_root-bank
    1) "sub-bank"
    127.0.0.1:6379> SMEMBERS $BANK_root-bank/sub-bank
    1) "leaf-bank"
    127.0.0.1:6379> SMEMBERS $BANKEYS_root-bank/sub-bank/leaf-bank
    1) "my-key"
    127.0.0.1:6379> GET $KEY_root-bank/sub-bank/leaf-bank/my-key
    "my-value"

There are three types of keys stored:

- ``$BANK_*`` is a Redis SET containing the list of banks under the current bank
- ``$BANKEYS_*`` is a Redis SET containing the list of keys under the current bank
- ``$KEY_*`` keeps the value of the key

These prefixes and the separator can be adjusted using the configuration options:

bank_prefix: ``$BANK``
    The prefix used for the name of the Redis key storing the list of sub-banks.

bank_keys_prefix: ``$BANKEYS``
    The prefix used for the name of the Redis keyt storing the list of keys under a certain bank.

key_prefix: ``$KEY``
    The prefix of the Redis keys having the value of the keys to be cached under
    a certain bank.

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
    cache.redis.bank_prefix: #BANK
    cache.redis.bank_keys_prefix: #BANKEYS
    cache.redis.key_prefix: #KEY
    cache.redis.separator: '@'

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
    cache.redis.bank_prefix: #BANK
    cache.redis.bank_keys_prefix: #BANKEYS
    cache.redis.key_prefix: #KEY
    cache.redis.separator: '@'
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import stdlib
import logging

from salt.exceptions import SaltCacheError

# Import salt
from salt.ext.six.moves import range

# Import third party libs
try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import ResponseError as RedisResponseError

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    # pylint: disable=no-name-in-module
    from rediscluster import StrictRedisCluster

    # pylint: enable=no-name-in-module

    HAS_REDIS_CLUSTER = True
except ImportError:
    HAS_REDIS_CLUSTER = False


# -----------------------------------------------------------------------------
# module properties
# -----------------------------------------------------------------------------

__virtualname__ = "redis"
__func_alias__ = {"list_": "list"}

log = logging.getLogger(__file__)

_BANK_PREFIX = "$BANK"
_KEY_PREFIX = "$KEY"
_BANK_KEYS_PREFIX = "$BANKEYS"
_SEPARATOR = "_"

REDIS_SERVER = None

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    The redis library must be installed for this module to work.

    The redis redis cluster library must be installed if cluster_mode is True
    """
    if not HAS_REDIS:
        return (False, "Please install the python-redis package.")
    if not HAS_REDIS_CLUSTER and _get_redis_cache_opts()["cluster_mode"]:
        return (False, "Please install the redis-py-cluster package.")
    return __virtualname__


# -----------------------------------------------------------------------------
# helper functions -- will not be exported
# -----------------------------------------------------------------------------


def init_kwargs(kwargs):
    return {}


def _get_redis_cache_opts():
    """
    Return the Redis server connection details from the __opts__.
    """
    return {
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
    }


def _get_redis_server(opts=None):
    """
    Return the Redis server instance.
    Caching the object instance.
    """
    global REDIS_SERVER
    if REDIS_SERVER:
        return REDIS_SERVER
    if not opts:
        opts = _get_redis_cache_opts()

    if opts["cluster_mode"]:
        REDIS_SERVER = StrictRedisCluster(
            startup_nodes=opts["startup_nodes"],
            skip_full_coverage_check=opts["skip_full_coverage_check"],
        )
    else:
        REDIS_SERVER = redis.StrictRedis(
            opts["host"],
            opts["port"],
            unix_socket_path=opts["unix_socket_path"],
            db=opts["db"],
            password=opts["password"],
        )
    return REDIS_SERVER


def _get_redis_keys_opts():
    """
    Build the key opts based on the user options.
    """
    return {
        "bank_prefix": __opts__.get("cache.redis.bank_prefix", _BANK_PREFIX),
        "bank_keys_prefix": __opts__.get(
            "cache.redis.bank_keys_prefix", _BANK_KEYS_PREFIX
        ),
        "key_prefix": __opts__.get("cache.redis.key_prefix", _KEY_PREFIX),
        "separator": __opts__.get("cache.redis.separator", _SEPARATOR),
    }


def _get_bank_redis_key(bank):
    """
    Return the Redis key for the bank given the name.
    """
    opts = _get_redis_keys_opts()
    return "{prefix}{separator}{bank}".format(
        prefix=opts["bank_prefix"], separator=opts["separator"], bank=bank
    )


def _get_key_redis_key(bank, key):
    """
    Return the Redis key given the bank name and the key name.
    """
    opts = _get_redis_keys_opts()
    return "{prefix}{separator}{bank}/{key}".format(
        prefix=opts["key_prefix"], separator=opts["separator"], bank=bank, key=key
    )


def _get_bank_keys_redis_key(bank):
    """
    Return the Redis key for the SET of keys under a certain bank, given the bank name.
    """
    opts = _get_redis_keys_opts()
    return "{prefix}{separator}{bank}".format(
        prefix=opts["bank_keys_prefix"], separator=opts["separator"], bank=bank
    )


def _build_bank_hier(bank, redis_pipe):
    """
    Build the bank hierarchy from the root of the tree.
    If already exists, it won't rewrite.
    It's using the Redis pipeline,
    so there will be only one interaction with the remote server.
    """
    bank_list = bank.split("/")
    parent_bank_path = bank_list[0]
    for bank_name in bank_list[1:]:
        prev_bank_redis_key = _get_bank_redis_key(parent_bank_path)
        redis_pipe.sadd(prev_bank_redis_key, bank_name)
        log.debug("Adding %s to %s", bank_name, prev_bank_redis_key)
        parent_bank_path = "{curr_path}/{bank_name}".format(
            curr_path=parent_bank_path, bank_name=bank_name
        )  # this becomes the parent of the next
    return True


def _get_banks_to_remove(redis_server, bank, path=""):
    """
    A simple tree tarversal algorithm that builds the list of banks to remove,
    starting from an arbitrary node in the tree.
    """
    current_path = bank if not path else "{path}/{bank}".format(path=path, bank=bank)
    bank_paths_to_remove = [current_path]
    # as you got here, you'll be removed

    bank_key = _get_bank_redis_key(current_path)
    child_banks = redis_server.smembers(bank_key)
    if not child_banks:
        return bank_paths_to_remove  # this bank does not have any child banks so we stop here
    for child_bank in child_banks:
        bank_paths_to_remove.extend(
            _get_banks_to_remove(redis_server, child_bank, path=current_path)
        )
        # go one more level deeper
        # and also remove the children of this child bank (if any)
    return bank_paths_to_remove


# -----------------------------------------------------------------------------
# cache subsystem functions
# -----------------------------------------------------------------------------


def store(bank, key, data):
    """
    Store the data in a Redis key.
    """
    redis_server = _get_redis_server()
    redis_pipe = redis_server.pipeline()
    redis_key = _get_key_redis_key(bank, key)
    redis_bank_keys = _get_bank_keys_redis_key(bank)
    try:
        _build_bank_hier(bank, redis_pipe)
        value = __context__["serial"].dumps(data)
        redis_pipe.set(redis_key, value)
        log.debug("Setting the value for %s under %s (%s)", key, bank, redis_key)
        redis_pipe.sadd(redis_bank_keys, key)
        log.debug("Adding %s to %s", key, redis_bank_keys)
        redis_pipe.execute()
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot set the Redis cache key {rkey}: {rerr}".format(
            rkey=redis_key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)


def fetch(bank, key):
    """
    Fetch data from the Redis cache.
    """
    redis_server = _get_redis_server()
    redis_key = _get_key_redis_key(bank, key)
    redis_value = None
    try:
        redis_value = redis_server.get(redis_key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot fetch the Redis cache key {rkey}: {rerr}".format(
            rkey=redis_key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    if redis_value is None:
        return {}
    return __context__["serial"].loads(redis_value)


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content. If no key is specified, remove
    the entire bank with all keys and sub-banks inside.
    This function is using the Redis pipelining for best performance.
    However, when removing a whole bank,
    in order to re-create the tree, there are a couple of requests made. In total:

    - one for node in the hierarchy sub-tree, starting from the bank node
    - one pipelined request to get the keys under all banks in the sub-tree
    - one pipeline request to remove the corresponding keys

    This is not quite optimal, as if we need to flush a bank having
    a very long list of sub-banks, the number of requests to build the sub-tree may grow quite big.

    An improvement for this would be loading a custom Lua script in the Redis instance of the user
    (using the ``register_script`` feature) and call it whenever we flush.
    This script would only need to build this sub-tree causing problems. It can be added later and the behaviour
    should not change as the user needs to explicitly allow Salt inject scripts in their Redis instance.
    """
    redis_server = _get_redis_server()
    redis_pipe = redis_server.pipeline()
    if key is None:
        # will remove all bank keys
        bank_paths_to_remove = _get_banks_to_remove(redis_server, bank)
        # tree traversal to get all bank hierarchy
        for bank_to_remove in bank_paths_to_remove:
            bank_keys_redis_key = _get_bank_keys_redis_key(bank_to_remove)
            # Redis key of the SET that stores the bank keys
            redis_pipe.smembers(bank_keys_redis_key)  # fetch these keys
            log.debug(
                "Fetching the keys of the %s bank (%s)",
                bank_to_remove,
                bank_keys_redis_key,
            )
        try:
            log.debug("Executing the pipe...")
            subtree_keys = (
                redis_pipe.execute()
            )  # here are the keys under these banks to be removed
            # this retunrs a list of sets, e.g.:
            # [set([]), set(['my-key']), set(['my-other-key', 'yet-another-key'])]
            # one set corresponding to a bank
        except (RedisConnectionError, RedisResponseError) as rerr:
            mesg = "Cannot retrieve the keys under these cache banks: {rbanks}: {rerr}".format(
                rbanks=", ".join(bank_paths_to_remove), rerr=rerr
            )
            log.error(mesg)
            raise SaltCacheError(mesg)
        total_banks = len(bank_paths_to_remove)
        # bank_paths_to_remove and subtree_keys have the same length (see above)
        for index in range(total_banks):
            bank_keys = subtree_keys[index]  # all the keys under this bank
            bank_path = bank_paths_to_remove[index]
            for key in bank_keys:
                redis_key = _get_key_redis_key(bank_path, key)
                redis_pipe.delete(redis_key)  # kill 'em all!
                log.debug(
                    "Removing the key %s under the %s bank (%s)",
                    key,
                    bank_path,
                    redis_key,
                )
            bank_keys_redis_key = _get_bank_keys_redis_key(bank_path)
            redis_pipe.delete(bank_keys_redis_key)
            log.debug(
                "Removing the bank-keys key for the %s bank (%s)",
                bank_path,
                bank_keys_redis_key,
            )
            # delete the Redis key where are stored
            # the list of keys under this bank
            bank_key = _get_bank_redis_key(bank_path)
            redis_pipe.delete(bank_key)
            log.debug("Removing the %s bank (%s)", bank_path, bank_key)
            # delete the bank key itself
    else:
        redis_key = _get_key_redis_key(bank, key)
        redis_pipe.delete(redis_key)  # delete the key cached
        log.debug("Removing the key %s under the %s bank (%s)", key, bank, redis_key)
        bank_keys_redis_key = _get_bank_keys_redis_key(bank)
        redis_pipe.srem(bank_keys_redis_key, key)
        log.debug(
            "De-referencing the key %s from the bank-keys of the %s bank (%s)",
            key,
            bank,
            bank_keys_redis_key,
        )
        # but also its reference from $BANKEYS list
    try:
        redis_pipe.execute()  # Fluuuush
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot flush the Redis cache bank {rbank}: {rerr}".format(
            rbank=bank, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    return True


def list_(bank):
    """
    Lists entries stored in the specified bank.
    """
    redis_server = _get_redis_server()
    bank_redis_key = _get_bank_redis_key(bank)
    try:
        banks = redis_server.smembers(bank_redis_key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot list the Redis cache key {rkey}: {rerr}".format(
            rkey=bank_redis_key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
    if not banks:
        return []
    return list(banks)


def contains(bank, key):
    """
    Checks if the specified bank contains the specified key.
    """
    redis_server = _get_redis_server()
    bank_redis_key = _get_bank_redis_key(bank)
    try:
        return redis_server.sismember(bank_redis_key, key)
    except (RedisConnectionError, RedisResponseError) as rerr:
        mesg = "Cannot retrieve the Redis cache key {rkey}: {rerr}".format(
            rkey=bank_redis_key, rerr=rerr
        )
        log.error(mesg)
        raise SaltCacheError(mesg)
