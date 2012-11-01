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

try:
    import redis
    has_redis = True
except ImportError:
    has_redis = False


def __virtual__():
    if not has_redis:
        return False
    return 'redis_return'


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
    serv.sadd('{0}:jobs'.format(ret['id']))
    serv.set('{0}:{1}'.format(ret['jid'], json.dumps(ret['return'])))
    serv.sadd('jobs', ret['jid'])
    serv.sadd(ret['jid'], ret['id'])
