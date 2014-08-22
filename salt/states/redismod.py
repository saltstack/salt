# -*- coding: utf-8 -*-
'''
Management of Redis server
==========================

.. versionadded:: 2014.7.0

:depends:   - redis Python module
:configuration: See :py:mod:`salt.modules.redis` for setup instructions.

.. code-block:: yaml

    key_in_redis:
      redis.string:
        - value: string data

The redis server information specified in the minion config file can be
overridden in states using the following arguments: ``host``, ``post``, ``db``,
``password``.

.. code-block:: yaml

    key_in_redis:
      redis.string:
        - value: string data
        - host: localhost
        - port: 6379
        - db: 0
        - password: somuchkittycat
'''

__virtualname__ = 'redis'


def __virtual__():
    '''
    Only load if the redis module is in __salt__
    '''
    if 'redis.set_key' in __salt__:
        return __virtualname__
    return False


def string(name, value, expire=None, expireat=None, **connection_args):
    '''
    Ensure that the key exists in redis with the value specified

    name
        Redis key to manage

    value
        Data to persist in key

    expire
        Sets time to live for key in seconds

    expireat
        Sets expiration time for key via UNIX timestamp, overrides `expire`
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Key already set to defined value'}

    old_key = __salt__['redis.get_key'](name, **connection_args)

    if old_key != value:
        __salt__['redis.set_key'](name, value, **connection_args)
        ret['changes'][name] = 'Value updated'
        ret['comment'] = 'Key updated to new value'

    if expireat:
        __salt__['redis.expireat'](name, expireat, **connection_args)
        ret['changes']['expireat'] = 'Key expires at {0}'.format(expireat)
    elif expire:
        __salt__['redis.expire'](name, expire, **connection_args)
        ret['changes']['expire'] = 'TTL set to {0} seconds'.format(expire)

    return ret


def absent(name, keys=None, **connection_args):
    '''
    Ensure key absent from redis

    name
        Key to ensure absent from redis

    keys
        list of keys to ensure absent, name will be ignored if this is used
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Key(s) specified already absent'}

    if keys:
        if not isinstance(keys, list):
            ret['result'] = False
            ret['comment'] = '`keys` not formed as a list type'
            return ret
        delete_list = [key for key in keys
                       if __salt__['redis.exists'](key, **connection_args)]
        if not len(delete_list):
            return ret
        __salt__['redis.delete'](*delete_list, **connection_args)
        ret['changes']['deleted'] = delete_list
        ret['comment'] = 'Keys deleted'
        return ret

    if __salt__['redis.exists'](name, **connection_args):
        __salt__['redis.delete'](name, **connection_args)
        ret['comment'] = 'Key deleted'
        ret['changes']['deleted'] = [name]
    return ret
