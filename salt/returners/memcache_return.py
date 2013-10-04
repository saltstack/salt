# -*- coding: utf-8 -*-
'''
Return data to a memcache server

To enable this returner the minion will need the python client for memcache
installed and the following values configured in the minion or master
config, these are the defaults:

    memcache.host: 'localhost'
    memcache.port: '11211'

python2-memcache uses 'localhost' and '11211' as syntax on connection.
'''

# Import python libs
import json
import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import memcache
    HAS_MEMCACHE = True
except ImportError:
    HAS_MEMCACHE = False


def __virtual__():
    if not HAS_MEMCACHE:
        return False
    return 'memcache'


def _get_serv():
    '''
    Return a memcache server object
    '''
    host = __salt__['config.option']('memcache.host')
    port = __salt__['config.option']('memcache.port')
    log.debug('memcache server: {0}:{1}'.format(host, port))
    if not host or not port:
        log.error('Host or port not defined in salt config')
        return
    #Combine host and port to conform syntax of python memcache client
    memcacheoptions = (host, port)

    return memcache.Client([':'.join(memcacheoptions)], debug=0)
    ## TODO: make memcacheoptions cluster aware
    # Servers can be passed in two forms:
    # 1. Strings of the form C{"host:port"}, which implies a default weight of 1
    # 2. Tuples of the form C{("host:port", weight)}, where C{weight} is
    #    an integer weight value.


def returner(ret):
    '''
    Return data to a memcache data store
    '''
    serv = _get_serv()
    serv.set('{0}:{1}'.format(ret['id'], ret['jid']), json.dumps(ret))
    serv.prepend('{0}:{1}'.format(ret['id'], ret['fun']), ret['jid'])
    serv.append('minions', ret['id'])
    serv.append('jids', ret['jid'])


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv()
    serv.set(jid, json.dumps(load))
    serv.append('jids', jid)


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
    return serv.get_multi('jids')


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv()
    return serv.get_multi('minions')
