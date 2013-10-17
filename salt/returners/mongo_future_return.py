# -*- coding: utf-8 -*-
'''
Return data to a mongodb server

Required python modules: pymongo


This returner will send data from the minions to a MongoDB server. To
configure the settings for your MongoDB server, add the following lines
to the minion config files::

    mongo.db: <database name>
    mongo.host: <server ip address>
    mongo.user: <MongoDB username>
    mongo.password: <MongoDB user password>
    mongo.port: 27017

This mongo returner is being developed to replace the default mongodb returner
in the future and should not be considered API stable yet.

'''

# Import python libs
import logging

# Import third party libs
try:
    import pymongo
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'mongo'


def __virtual__():
    if not HAS_PYMONGO:
        return False
    return __virtualname__


def _remove_dots(src):
    output = {}
    for key, val in src.iteritems():
        if isinstance(val, dict):
            val = _remove_dots(val)
        output[key.replace('.', '-')] = val
    return output


def _get_conn():
    '''
    Return a mongodb connection object
    '''
    conn = pymongo.Connection(
            __salt__['config.option']('mongo.host'),
            __salt__['config.option']('mongo.port'))
    mdb = conn[__salt__['config.option']('mongo.db')]

    user = __salt__['config.option']('mongo.user')
    password = __salt__['config.option']('mongo.password')

    if user and password:
        mdb.authenticate(user, password)
    return conn, mdb


def returner(ret):
    '''
    Return data to a mongodb server
    '''
    conn, mdb = _get_conn()
    col = mdb[ret['id']]

    if isinstance(ret['return'], dict):
        back = _remove_dots(ret['return'])
    else:
        back = ret['return']

    log.debug(back)
    sdata = {ret['jid']: back, 'fun': ret['fun']}
    if 'out' in ret:
        sdata['out'] = ret['out']
    col.insert(sdata)


def save_load(jid, load):
    '''
    Save the load for a given job id
    '''
    conn, mdb = _get_conn()
    col = mdb[jid]
    col.insert(load)


def get_load(jid):
    '''
    Return the load associated with a given job id
    '''
    conn, mdb = _get_conn()
    return mdb[jid].find_one()


def get_jid(jid):
    '''
    Return the return information associated with a jid
    '''
    conn, mdb = _get_conn()
    ret = {}
    for collection in mdb.collection_names():
        rdata = mdb[collection].find_one({jid: {'$exists': 'true'}})
        if rdata:
            ret[collection] = rdata
    return ret


def get_fun(fun):
    '''
    Return the most recent jobs that have executed the named function
    '''
    conn, mdb = _get_conn()
    ret = {}
    for collection in mdb.collection_names():
        rdata = mdb[collection].find_one({'fun': fun})
        if rdata:
            ret[collection] = rdata
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    conn, mdb = _get_conn()
    ret = []
    for name in mdb.collection_names():
        if len(name) == 20:
            try:
                int(name)
                continue
            except ValueError:
                pass
        ret.append(name)
    return ret


def get_jids():
    '''
    Return a list of job ids
    '''
    conn, mdb = _get_conn()
    ret = []
    for name in mdb.collection_names():
        if len(name) == 20:
            try:
                int(name)
                ret.append(name)
            except ValueError:
                pass
    return ret
