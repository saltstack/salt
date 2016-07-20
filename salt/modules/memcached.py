# -*- coding: utf-8 -*-
'''
Module for Management of Memcached Keys

.. versionadded:: 2014.1.0
'''
from __future__ import absolute_import

# TODO: use salt.utils.memcache

# Import python libs
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.six import integer_types

# Import third party libs
try:
    import memcache
    HAS_MEMCACHE = True
except ImportError:
    HAS_MEMCACHE = False

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 11211
DEFAULT_TIME = 0
DEFAULT_MIN_COMPRESS_LEN = 0

log = logging.getLogger(__name__)

# Don't shadow built-ins
__func_alias__ = {
    'set_': 'set'
}

__virtualname__ = 'memcached'


def __virtual__():
    '''
    Only load if python-memcache is installed
    '''
    return __virtualname__ if HAS_MEMCACHE else False


def _connect(host=DEFAULT_HOST, port=DEFAULT_PORT):
    '''
    Returns a tuple of (user, host, port) with config, pillar, or default
    values assigned to missing values.
    '''
    if str(port).isdigit():
        return memcache.Client(['{0}:{1}'.format(host, port)], debug=0)
    raise SaltInvocationError('port must be an integer')


def _check_stats(conn):
    '''
    Helper function to check the stats data passed into it, and raise an
    execption if none are returned. Otherwise, the stats are returned.
    '''
    stats = conn.get_stats()
    if not stats:
        raise CommandExecutionError(
            'memcached server is down or does not exist'
        )
    return stats


def status(host=DEFAULT_HOST, port=DEFAULT_PORT):
    '''
    Get memcached status

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.status
    '''
    conn = _connect(host, port)
    try:
        stats = _check_stats(conn)[0]
    except (CommandExecutionError, IndexError):
        return False
    else:
        return {stats[0]: stats[1]}


def get(key, host=DEFAULT_HOST, port=DEFAULT_PORT):
    '''
    Retrieve value for a key

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.get <key>
    '''
    conn = _connect(host, port)
    _check_stats(conn)
    return conn.get(key)


def set_(key,
         value,
         host=DEFAULT_HOST,
         port=DEFAULT_PORT,
         time=DEFAULT_TIME,
         min_compress_len=DEFAULT_MIN_COMPRESS_LEN):
    '''
    Set a key on the memcached server, overwriting the value if it exists.

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.set <key> <value>
    '''
    if not isinstance(time, integer_types):
        raise SaltInvocationError('\'time\' must be an integer')
    if not isinstance(min_compress_len, integer_types):
        raise SaltInvocationError('\'min_compress_len\' must be an integer')
    conn = _connect(host, port)
    _check_stats(conn)
    return conn.set(key, value, time, min_compress_len)


def delete(key,
           host=DEFAULT_HOST,
           port=DEFAULT_PORT,
           time=DEFAULT_TIME):
    '''
    Delete a key from memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.delete <key>
    '''
    if not isinstance(time, integer_types):
        raise SaltInvocationError('\'time\' must be an integer')
    conn = _connect(host, port)
    _check_stats(conn)
    return bool(conn.delete(key, time))


def add(key,
        value,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        time=DEFAULT_TIME,
        min_compress_len=DEFAULT_MIN_COMPRESS_LEN):
    '''
    Add a key to the memcached server, but only if it does not exist. Returns
    False if the key already exists.

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.add <key> <value>
    '''
    if not isinstance(time, integer_types):
        raise SaltInvocationError('\'time\' must be an integer')
    if not isinstance(min_compress_len, integer_types):
        raise SaltInvocationError('\'min_compress_len\' must be an integer')
    conn = _connect(host, port)
    _check_stats(conn)
    return conn.add(
        key,
        value,
        time=time,
        min_compress_len=min_compress_len
    )


def replace(key,
            value,
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
            time=DEFAULT_TIME,
            min_compress_len=DEFAULT_MIN_COMPRESS_LEN):
    '''
    Replace a key on the memcached server. This only succeeds if the key
    already exists. This is the opposite of :mod:`memcached.add
    <salt.modules.memcached.add>`

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.replace <key> <value>
    '''
    if not isinstance(time, integer_types):
        raise SaltInvocationError('\'time\' must be an integer')
    if not isinstance(min_compress_len, integer_types):
        raise SaltInvocationError('\'min_compress_len\' must be an integer')
    conn = _connect(host, port)
    stats = conn.get_stats()
    return conn.replace(
        key,
        value,
        time=time,
        min_compress_len=min_compress_len
    )


def increment(key, delta=1, host=DEFAULT_HOST, port=DEFAULT_PORT):
    '''
    Increment the value of a key

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.increment <key>
        salt '*' memcached.increment <key> 2
    '''
    conn = _connect(host, port)
    _check_stats(conn)
    cur = get(key)

    if cur is None:
        raise CommandExecutionError('Key {0!r} does not exist'.format(key))
    elif not isinstance(cur, integer_types):
        raise CommandExecutionError(
            'Value for key {0!r} must be an integer to be '
            'incremented'.format(key)
        )

    try:
        return conn.incr(key, delta)
    except ValueError:
        raise SaltInvocationError('Delta value must be an integer')

incr = salt.utils.alias_function(increment, 'incr')


def decrement(key, delta=1, host=DEFAULT_HOST, port=DEFAULT_PORT):
    '''
    Decrement the value of a key

    CLI Example:

    .. code-block:: bash

        salt '*' memcached.decrement <key>
        salt '*' memcached.decrement <key> 2
    '''
    conn = _connect(host, port)
    _check_stats(conn)

    cur = get(key)
    if cur is None:
        raise CommandExecutionError('Key {0!r} does not exist'.format(key))
    elif not isinstance(cur, integer_types):
        raise CommandExecutionError(
            'Value for key {0!r} must be an integer to be '
            'decremented'.format(key)
        )

    try:
        return conn.decr(key, delta)
    except ValueError:
        raise SaltInvocationError('Delta value must be an integer')

decr = salt.utils.alias_function(decrement, 'decr')
