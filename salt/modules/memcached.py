# -*- coding: utf-8 -*-
'''
Module to provide Memcache functionality to Salt

'''

# Import python libs
import logging

# Import salt libs
from salt.exceptions import SaltException

# Import third party libs
try:
    import memcache
    HAS_MEMCACHE = True
except ImportError:
    HAS_MEMCACHE = False

log = logging.getLogger(__name__)


def _connect(host, port):
    '''
    Returns a tuple of (user, host, port) with config, pillar, or default
    values assigned to missing values.
    '''
    if not host:
        host = __salt__['config.option']('memcache.host')
    if not port:
        port = __salt__['config.option']('memcache.port')

    if not HAS_MEMCACHE:
        raise SaltException('Error: python-memcached is not installed.')
    else:
        if str(port).isdigit():
            conn = memcache.Client(["%s:%s" % (host, port)], debug=0)
        else:
            raise SaltException('Error: port must be a number.')

    return conn


def status(host, port):
    '''
    get memcache status

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.status  <host> <port>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        return False
    else:
        ret = {}
        server = status[0][0]
        stats = status[0][1]
        ret[server] = stats

    return ret


def get(host, port, key):
    '''
    get key from  memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.get  <host> <port> <key>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        return conn.get(key)


def set(host, port, key, val, time=0, min_compress_len=0):
    '''
    insert key to  memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.set  <host> <port> <key>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        ret = conn.set(key, val, time, min_compress_len)
    return ret


def delete(host, port, key, time=0):
    '''
    delete key from  memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.delete  <host> <port> <key>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        ret = conn.delete(key, time)
        if ret:
            return True
        else:
            return False


def add(host, port, key, val, time=0, min_compress_len=0):
    '''
    add key to  memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.add  <host> <port> <key> <val>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        return conn.add(key, val, time=0, min_compress_len=0)


def incr(host, port, key, delta=1):
    '''
    incr key

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.incr  <host> <port> <key> <delta>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        try:
            ret = conn.incr(key, delta)
        except ValueError:
            raise SaltException('Error: incr key must be a number.')
        return ret


def decr(host, port, key, delta=1):
    '''
    decr key

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.decr  <host> <port> <key> <delta>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        try:
            ret = conn.decr(key, delta)
        except ValueError:
            raise SaltException('Error: decr key must be a number.')
        return ret


def replace(host, port, key, val, time=0, min_compress_len=0):
    '''
    replace key from  memcache server

    CLI Example:

    .. code-block:: bash

        salt '*' memcache.replace  <host> <port> <key> <val>
    '''
    conn = _connect(host, port)
    status = conn.get_stats()
    if status == []:
        raise SaltException('Error: memcache server is down or not exists.')
    else:
        return conn.replace(key, val, time=0, min_compress_len=0)

