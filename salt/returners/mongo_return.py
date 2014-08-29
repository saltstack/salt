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

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.mongo.db: <database name>
    alternative.mongo.host: <server ip address>
    alternative.mongo.user: <MongoDB username>
    alternative.mongo.password: <MongoDB user password>
    alternative.mongo.port: 27017

  To use the mongo returner, append '--return mongo' to the salt command. ex:

    salt '*' test.ping --return mongo_return

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return mongo_return --return_config alternative
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
# currently only used iby _get_options
__virtualname__ = 'mongo'


def __virtual__():
    if not HAS_PYMONGO:
        return False
    return 'mongo_return'


def _remove_dots(src):
    output = {}
    for key, val in src.iteritems():
        if isinstance(val, dict):
            val = _remove_dots(val)
        output[key.replace('.', '-')] = val
    return output


def _get_options(ret):
    '''
    Get the monogo_return options from salt.
    '''
    ret_config = '{0}'.format(ret['ret_config']) if 'ret_config' in ret else ''

    attrs = {'host': 'host',
             'port': 'port',
             'db': 'db',
             'username': 'username',
             'password': 'password'}

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


def _get_conn(ret):
    '''
    Return a mongodb connection object
    '''
    _options = _get_options(ret)

    host = _options.get('host')
    port = _options.get('port')
    db = _options.get('db')
    user = _options.get('user')
    password = _options.get('password')

    conn = pymongo.Connection(host, port)
    mdb = conn[db]

    if user and password:
        mdb.authenticate(user, password)
    return conn, mdb


def returner(ret):
    '''
    Return data to a mongodb server
    '''
    conn, mdb = _get_conn(ret)
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
