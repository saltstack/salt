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


def info(host=None, port=None, db=None, password=None):
    '''
    Get information and statistics about the server

    CLI Example:

    .. code-block:: bash

        salt '*' redis_exec.info
    '''
    server = _connect(host, port, db, password)
    return server.info()


def config_get(pattern, host=None, port=None, db=None, password=None):
    '''
    Get redis server configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' redis_exec.config_get '*'
        salt '*' redis_exec.config_get port
    '''
    server = _connect(host, port, db, password)
    return server.config_get(pattern)


def config_set(name, value, host=None, port=None, db=None, password=None):
    '''
    Set redis server configuration values

    CLI Example:

    .. code-block:: bash

        salt '*' redis_exec.config_set masterauth luv_kittens
    '''
    server = _connect(host, port, db, password)
    return server.config_set(name, value)
