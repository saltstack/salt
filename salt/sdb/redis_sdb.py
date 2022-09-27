"""
Redis SDB module
================

 .. versionadded:: 2019.2.0

This module allows access to Redis  using an ``sdb://`` URI.

Like all SDB modules, the Redis module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. For example:

.. code-block:: yaml

    sdb_redis:
      driver: redis
      host: 127.0.0.1
      port: 6379
      password: pass
      db: 1

The ``driver`` refers to the Redis module, all other options are optional.
For option details see: https://redis-py.readthedocs.io/en/latest/.

"""

try:
    import redis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


__func_alias__ = {"set_": "set"}
__virtualname__ = "redis"


def __virtual__():
    """
    Module virtual name.
    """
    if not HAS_REDIS:
        return (False, "Please install python-redis to use this SDB module.")
    return __virtualname__


def set_(key, value, profile=None):
    """
    Set a value into the Redis SDB.
    """
    if not profile:
        return False
    redis_kwargs = profile.copy()
    redis_kwargs.pop("driver")
    redis_conn = redis.StrictRedis(**redis_kwargs)
    return redis_conn.set(key, value)


def get(key, profile=None):
    """
    Get a value from the Redis SDB.
    """
    if not profile:
        return False
    redis_kwargs = profile.copy()
    redis_kwargs.pop("driver")
    redis_conn = redis.StrictRedis(**redis_kwargs)
    return redis_conn.get(key)


def delete(key, profile=None):
    """
    Delete a key from the Redis SDB.
    """
    if not profile:
        return False
    redis_kwargs = profile.copy()
    redis_kwargs.pop("driver")
    redis_conn = redis.StrictRedis(**redis_kwargs)
    return redis_conn.delete(key)
