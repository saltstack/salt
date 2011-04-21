'''
Return data to a redis server
This is a VERY simple example for pushing data to a redis server and is not
nessisarily intended as a usable interface.
'''

import redis
import json

__opts__ = {
            'redis.host': 'mcp',
            'redis.port': 6379,
            'redis.db': '0',
           }

def returner(ret):
    '''
    Return data to a redis data store
    '''
    serv = redis.Redis(
            host=__opts__['redis.host'],
            port=__opts__['redis.port'],
            db=__opts__['redis.db'])
    serv.sadd(ret['id'] + ':' + 'jobs', ret['jid'])
    serv.set(ret['jid'] + ':' + ret['id'], json.dumps(ret['return']))
    serv.sadd('jobs', ret['jid'])
    serv.sadd(ret['jid'], ret['id'])
