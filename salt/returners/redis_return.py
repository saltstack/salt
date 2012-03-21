'''
Return data to a redis server
This is a VERY simple example for pushing data to a redis server and is not
necessarily intended as a usable interface.

Required python modules: redis
'''

import json

try:
    import redis
    has_redis = True
except ImportError:
    has_redis = False

__opts__ = {'redis.db': '0',
            'redis.host': 'mcp',
            'redis.port': 6379}


def __virtual__():
    if not has_redis:
        return False
    return 'redis_return'


def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = redis.Redis(host=__opts__['redis.host'],
                       port=__opts__['redis.port'],
                       db=__opts__['redis.db'])

    serv.sadd("%(id)s:jobs" % ret, ret['jid'])
    serv.set("%(jid)s:%(id)s" % ret, json.dumps(ret['return']))
    serv.sadd('jobs', ret['jid'])
    serv.sadd(ret['jid'], ret['id'])
