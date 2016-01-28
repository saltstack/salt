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

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: Boron

.. code-block:: bash

    salt '*' test.ping --return redis --return_kwargs '{"db": "another-salt"}'

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


def _get_ttl():
    return __opts__['keep_jobs'] * 3600


def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = _get_serv(ret)
    pipeline = serv.pipeline(transaction=False)
    minion, jid = ret['id'], ret['jid']
    pipeline.hset('ret:{0}'.format(jid), minion, json.dumps(ret))
    pipeline.expire('ret:{0}'.format(jid), _get_ttl())
    pipeline.set('{0}:{1}'.format(minion, ret['fun']), jid)
    pipeline.sadd('minions', minion)
    pipeline.execute()


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    serv.setex('load:{0}'.format(jid), json.dumps(load), _get_ttl())


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv(ret=None)
    data = serv.get('load:{0}'.format(jid))
    if data:
        return json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion, data in serv.hgetall('ret:{0}'.format(jid)).iteritems():
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
            jid = serv.get(ind_str)
        except Exception:
            continue
        if not jid:
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
    return list(serv.keys('load:*'))


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    return list(serv.smembers('minions'))


def clean_old_jobs():
    '''
    Clean out minions's return data for old jobs.
    '''
    serv = _get_serv(ret=None)
    living_jids = set(serv.keys('load:*'))
    to_remove = []
    for ret_key in serv.keys('ret:*'):
        load_key = ret_key.replace('ret:', 'load:', 1)
        if load_key not in living_jids:
            to_remove.append(ret_key)
    serv.delete(**to_remove)


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
