# -*- coding: utf-8 -*-
'''
Return data to a redis server

To enable this returner the minion will need the python client for redis
installed and the following values configured in the minion or master
config, these are the defaults:

.. code-block:: yaml

    redis.db: '0'
    redis.host: 'salt'
    redis.port: 6379

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.redis.db: '0'
    alternative.redis.host: 'salt'
    alternative.redis.port: 6379

To use the redis returner, append '--return redis' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return redis

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return redis --return_config alternative
'''
from __future__ import absolute_import

# Import python libs
import json

# Import Salt libs
import salt.utils.jid
import salt.returners

# Import third party libs
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

# Define the module's virtual name
__virtualname__ = 'redis'


def __virtual__():
    if not HAS_REDIS:
        return False
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the redis options from salt.
    '''
    attrs = {'host': 'host',
             'port': 'port',
             'db': 'db'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_serv(ret=None):
    '''
    Return a redis server object
    '''
    _options = _get_options(ret)
    host = _options.get('host')
    port = _options.get('port')
    db = _options.get('db')

    return redis.Redis(
            host=host,
            port=port,
            db=db)


def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = _get_serv(ret)
    pipe = serv.pipeline()
    pipe.set('{0}:{1}'.format(ret['id'], ret['jid']), json.dumps(ret))
    pipe.lpush('{0}:{1}'.format(ret['id'], ret['fun']), ret['jid'])
    pipe.sadd('minions', ret['id'])
    pipe.sadd('jids', ret['jid'])
    pipe.execute()


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    serv.set(jid, json.dumps(load))
    serv.sadd('jids', jid)


def save_minions(jid, minions):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv(ret=None)
    data = serv.get(jid)
    if data:
        return json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion in serv.smembers('minions'):
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = json.loads(data)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion in serv.smembers('minions'):
        ind_str = '{0}:{1}'.format(minion, fun)
        try:
            jid = serv.lindex(ind_str, 0)
        except Exception:
            continue
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = json.loads(data)
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    serv = _get_serv(ret=None)
    return list(serv.smembers('jids'))


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    return list(serv.smembers('minions'))


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
