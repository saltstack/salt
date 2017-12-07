# -*- coding: utf-8 -*-

'''
Provide token storage in Redis cluster.

To get started simply start a redis cluster and assign all hashslots to the connected nodes.
Add the redis hostname and port to master configs as eauth_redis_host and eauth_redis_port.
Default values for these configs are as follow:

.. code-block:: yaml

    eauth_redis_host: localhost
    eauth_redis_port: 6379

:depends:   - redis-py-cluster Python package
'''

from __future__ import absolute_import


try:
    import rediscluster
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


import os
import logging
import hashlib

import salt.payload

log = logging.getLogger(__name__)

__virtualname__ = u'rediscluster'


def __virtual__():
    if not HAS_REDIS:
        return False, u'Could not use redis for tokens; '\
                      u'rediscluster python client is not installed.'
    return __virtualname__


def _redis_client(opts):
    '''
    Connect to the redis host and return a StrictRedisCluster client object.
    If connection fails then return None.
    '''
    redis_host = opts.get(u"eauth_redis_host", u"localhost")
    redis_port = opts.get(u"eauth_redis_port", 6379)
    try:
        return rediscluster.StrictRedisCluster(host=redis_host, port=redis_port)
    except rediscluster.exceptions.RedisClusterException as err:
        log.warning(
            u'Failed to connect to redis at %s:%s - %s',
            redis_host, redis_port, err
        )
        return None


def mk_token(opts, tdata):
    '''
    Mint a new token using the config option hash_type and store tdata with 'token' attribute set
    to the token.
    This module uses the hash of random 512 bytes as a token.

    :param opts: Salt master config options
    :param tdata: Token data to be stored with 'token' attirbute of this dict set to the token.
    :returns: tdata with token if successful. Empty dict if failed.
    '''
    redis_client = _redis_client(opts)
    if not redis_client:
        return {}
    hash_type = getattr(hashlib, opts.get(u'hash_type', u'md5'))
    tok = str(hash_type(os.urandom(512)).hexdigest())
    try:
        while redis_client.get(tok) is not None:
            tok = str(hash_type(os.urandom(512)).hexdigest())
    except Exception as err:
        log.warning(
            u'Authentication failure: cannot get token %s from redis: %s',
            tok, err
        )
        return {}
    tdata[u'token'] = tok
    serial = salt.payload.Serial(opts)
    try:
        redis_client.set(tok, serial.dumps(tdata))
    except Exception as err:
        log.warning(
            u'Authentication failure: cannot save token %s to redis: %s',
            tok, err
        )
        return {}
    return tdata


def get_token(opts, tok):
    '''
    Fetch the token data from the store.

    :param opts: Salt master config options
    :param tok: Token value to get
    :returns: Token data if successful. Empty dict if failed.
    '''
    redis_client = _redis_client(opts)
    if not redis_client:
        return {}
    serial = salt.payload.Serial(opts)
    try:
        tdata = serial.loads(redis_client.get(tok))
        return tdata
    except Exception as err:
        log.warning(
            u'Authentication failure: cannot get token %s from redis: %s',
            tok, err
        )
        return {}


def rm_token(opts, tok):
    '''
    Remove token from the store.

    :param opts: Salt master config options
    :param tok: Token to remove
    :returns: Empty dict if successful. None if failed.
    '''
    redis_client = _redis_client(opts)
    if not redis_client:
        return
    try:
        redis_client.delete(tok)
        return {}
    except Exception as err:
        log.warning(u'Could not remove token %s: %s', tok, err)


def list_tokens(opts):
    '''
    List all tokens in the store.

    :param opts: Salt master config options
    :returns: List of dicts (token_data)
    '''
    ret = []
    redis_client = _redis_client(opts)
    if not redis_client:
        return []
    serial = salt.payload.Serial(opts)
    try:
        return [k.decode(u'utf8') for k in redis_client.keys()]
    except Exception as err:
        log.warning(u'Failed to list keys: %s', err)
        return []
