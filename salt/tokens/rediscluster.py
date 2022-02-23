"""
Provide token storage in Redis cluster.

To get started simply start a redis cluster and assign all hashslots to the connected nodes.
Add the redis hostname and port to master configs as eauth_redis_host and eauth_redis_port.
Default values for these configs are as follow:

.. code-block:: yaml

    eauth_redis_host: localhost
    eauth_redis_port: 6379

:depends:   - redis-py-cluster Python package
"""


import hashlib
import logging
import os

import salt.payload

try:
    import rediscluster

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


log = logging.getLogger(__name__)

__virtualname__ = "rediscluster"


def __virtual__():
    if not HAS_REDIS:
        return (
            False,
            "Could not use redis for tokens; "
            "rediscluster python client is not installed.",
        )
    return __virtualname__


def _redis_client(opts):
    """
    Connect to the redis host and return a StrictRedisCluster client object.
    If connection fails then return None.
    """
    redis_host = opts.get("eauth_redis_host", "localhost")
    redis_port = opts.get("eauth_redis_port", 6379)
    try:
        return rediscluster.StrictRedisCluster(
            host=redis_host, port=redis_port, decode_responses=True
        )
    except rediscluster.exceptions.RedisClusterException as err:
        log.warning(
            "Failed to connect to redis at %s:%s - %s", redis_host, redis_port, err
        )
        return None


def mk_token(opts, tdata):
    """
    Mint a new token using the config option hash_type and store tdata with 'token' attribute set
    to the token.
    This module uses the hash of random 512 bytes as a token.

    :param opts: Salt master config options
    :param tdata: Token data to be stored with 'token' attribute of this dict set to the token.
    :returns: tdata with token if successful. Empty dict if failed.
    """
    redis_client = _redis_client(opts)
    if not redis_client:
        return {}
    hash_type = getattr(hashlib, opts.get("hash_type", "md5"))
    tok = str(hash_type(os.urandom(512)).hexdigest())
    try:
        while redis_client.get(tok) is not None:
            tok = str(hash_type(os.urandom(512)).hexdigest())
    except Exception as err:  # pylint: disable=broad-except
        log.warning(
            "Authentication failure: cannot get token %s from redis: %s", tok, err
        )
        return {}
    tdata["token"] = tok
    try:
        redis_client.set(tok, salt.payload.dumps(tdata))
    except Exception as err:  # pylint: disable=broad-except
        log.warning(
            "Authentication failure: cannot save token %s to redis: %s", tok, err
        )
        return {}
    return tdata


def get_token(opts, tok):
    """
    Fetch the token data from the store.

    :param opts: Salt master config options
    :param tok: Token value to get
    :returns: Token data if successful. Empty dict if failed.
    """
    redis_client = _redis_client(opts)
    if not redis_client:
        return {}
    try:
        tdata = salt.payload.loads(redis_client.get(tok))
        return tdata
    except Exception as err:  # pylint: disable=broad-except
        log.warning(
            "Authentication failure: cannot get token %s from redis: %s", tok, err
        )
        return {}


def rm_token(opts, tok):
    """
    Remove token from the store.

    :param opts: Salt master config options
    :param tok: Token to remove
    :returns: Empty dict if successful. None if failed.
    """
    redis_client = _redis_client(opts)
    if not redis_client:
        return
    try:
        redis_client.delete(tok)
        return {}
    except Exception as err:  # pylint: disable=broad-except
        log.warning("Could not remove token %s: %s", tok, err)


def list_tokens(opts):
    """
    List all tokens in the store.

    :param opts: Salt master config options
    :returns: List of dicts (token_data)
    """
    ret = []
    redis_client = _redis_client(opts)
    if not redis_client:
        return []
    try:
        return [k.decode("utf8") for k in redis_client.keys()]
    except Exception as err:  # pylint: disable=broad-except
        log.warning("Failed to list keys: %s", err)
        return []
