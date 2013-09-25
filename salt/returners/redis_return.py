# -*- coding: utf-8 -*-
'''
Return data to a redis server

To enable this returner the minion will need the python client for redis
installed and the following values configured in the minion or master
config, these are the defaults:

    redis.db: '0'
    redis.host: 'salt'
    redis.port: 6379
'''

# Import python libs
import json

# Import third party libs
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


def __virtual__():
    if not HAS_REDIS:
        return False
    return 'redis'


def _get_serv():
    '''
    Return a redis server object
    '''
    return redis.Redis(
            host=__salt__['config.option']('redis.host'),
            port=__salt__['config.option']('redis.port'),
            db=__salt__['config.option']('redis.db'))


def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = _get_serv()
    serv.set('{0}:{1}'.format(ret['id'], ret['jid']), json.dumps(ret))
    serv.lpush('{0}:{1}'.format(ret['id'], ret['fun']), ret['jid'])
    serv.sadd('minions', ret['id'])
    serv.sadd('jids', ret['jid'])


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv()
    serv.set(jid, json.dumps(load))
    serv.sadd('jids', jid)


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv()
    data = serv.get(jid)
    if data:
        return json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv()
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
    serv = _get_serv()
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
    serv = _get_serv()
    return serv.smembers('jids')


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv()
    return serv.smembers('minions')
