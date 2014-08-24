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
the default location::

    alternative.redis.db: '0'
    alternative.redis.host: 'salt'
    alternative.redis.port: 6379

  To use the redis returner, append '--return redis' to the salt command. ex:

    salt '*' test.ping --return redis

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return redis --return_config alternative
'''

# Import python libs
import json

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


def _get_options(ret):
    '''
    Get the redis options from salt.
    '''
    ret_config = '{0}'.format(ret['ret_config']) if 'ret_config' in ret else ''

    attrs = {'host': 'host',
             'port': 'port',
             'db': 'db'}

    _options = {}
    for attr in attrs:
        if 'config.option' in __salt__:
            cfg = __salt__['config.option']
            c_cfg = cfg('{0}'.format(__virtualname__), {})
            if ret_config:
                ret_cfg = cfg('{0}.{1}'.format(ret_config, __virtualname__), {})
                if ret_cfg.get(attrs[attr], cfg('{0}.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg('{0}.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg('{0}.{1}'.format(__virtualname__, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg('{0}.{1}'.format(__virtualname__, attrs[attr])))
        else:
            cfg = __opts__
            c_cfg = cfg.get('{0}'.format(__virtualname__), {})
            if ret_config:
                ret_cfg = cfg.get('{0}.{1}'.format(ret_config, __virtualname__), {})
                if ret_cfg.get(attrs[attr], cfg.get('{0}.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg.get('{0}.{1}.{2}'.format(ret_config, __virtualname__, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg.get('{0}.{1}'.format(__virtualname__, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg.get('{0}.{1}'.format(__virtualname__, attrs[attr])))
        if not _attr:
            _options[attr] = None
            continue
        _options[attr] = _attr
    return _options


def _get_serv(ret):
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
    return list(serv.smembers('jids'))


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv()
    return list(serv.smembers('minions'))
