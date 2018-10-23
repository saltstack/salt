# -*- coding: utf-8 -*-
'''
Read pillar data from a Redis backend
=====================================

.. versionadded:: 2014.7.0

:depends:   - redis Python module (on master)

Salt Master Redis Configuration
===============================

The module shares the same base Redis connection variables as
:py:mod:`salt.returners.redis_return`. These variables go in your master
config file.

* ``redis.db`` - The Redis database to use. Defaults to ``0``.
* ``redis.host`` - The Redis host to connect to. Defaults to ``'salt'``.
* ``redis.port`` - The port that the Redis database is listening on. Defaults
  to ``6379``.
* ``redis.password`` - The password for authenticating with Redis. Only
  required if you are using master auth. Defaults to ``None``.

Configuring the Redis ext_pillar
================================

    .. code-block:: yaml

        ext_pillar:
          - redis: {function: key_value}

'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.json

__virtualname__ = 'redis'


def __virtual__():
    '''
    Only load if the redis module is in __salt__
    '''
    if 'redis.get_key' in __salt__:
        return __virtualname__
    return False


def ext_pillar(minion_id, pillar, function, **kwargs):
    '''
    Grabs external pillar data based on configured function
    '''
    if function.startswith('_') or function not in globals():
        return {}
    # Call specified function to pull redis data
    return globals()[function](minion_id, pillar, **kwargs)


def key_value(minion_id,
              pillar,  # pylint: disable=W0613
              pillar_key='redis_pillar'):
    '''
    Looks for key in redis matching minion_id, returns a structure based on the
    data type of the redis key. String for string type, dict for hash type and
    lists for lists, sets and sorted sets.

    pillar_key
        Pillar key to return data into
    '''
    # Identify key type and process as needed based on that type
    key_type = __salt__['redis.key_type'](minion_id)
    if key_type == 'string':
        return {pillar_key: __salt__['redis.get_key'](minion_id)}
    elif key_type == 'hash':
        return {pillar_key: __salt__['redis.hgetall'](minion_id)}
    elif key_type == 'list':
        list_size = __salt__['redis.llen'](minion_id)
        if not list_size:
            return {}
        return {pillar_key: __salt__['redis.lrange'](minion_id, 0,
                                                     list_size - 1)}
    elif key_type == 'set':
        return {pillar_key: __salt__['redis.smembers'](minion_id)}
    elif key_type == 'zset':
        set_size = __salt__['redis.zcard'](minion_id)
        if not set_size:
            return {}
        return {pillar_key: __salt__['redis.zrange'](minion_id, 0,
                                                     set_size - 1)}
    # Return nothing for unhandled types
    return {}


def key_json(minion_id,
             pillar,  # pylint: disable=W0613
             pillar_key=None):
    '''
    Pulls a string from redis and deserializes it from json. Deserialized
    dictionary data loaded directly into top level if pillar_key is not set.

    pillar_key
        Pillar key to return data into
    '''
    key_data = __salt__['redis.get_key'](minion_id)
    # Return nothing for non-existent keys
    if not key_data:
        return {}

    data = salt.utils.json.loads(key_data)
    # Return as requested
    if isinstance(data, dict) and not pillar_key:
        return data
    elif not pillar_key:
        return {'redis_pillar': data}
    else:
        return {pillar_key: data}
