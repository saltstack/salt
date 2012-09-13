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

'''

import logging

try:
    import pymongo
    has_pymongo = True
except ImportError:
    has_pymongo = False


log = logging.getLogger(__name__)

# These options should be overridden in the minion config file
__opts__ = {'mongo.db': 'salt',
            'mongo.host': 'salt',
            'mongo.password': '',
            'mongo.port': 27017,
            'mongo.user': ''}


def __virtual__():
    if not has_pymongo:
        return False
    return 'mongo_return'

def _remove_dots(d):
    output = {}
    for k, v in d.iteritems():
        if isinstance(v, dict):
            v = _remove_dots(v)
        output[k.replace('.', '-')] = v
    return output

def returner(ret):
    '''
    Return data to a mongodb server
    '''
    conn = pymongo.Connection(__opts__['mongo.host'],
                              __opts__['mongo.port'])
    db = conn[__opts__['mongo.db']]

    user = __opts__.get('mongo.user')
    password = __opts__.get('mongo.password')

    if user and password:
        db.authenticate(user, password)

    col = db[ret['id']]
    back = {}

    if isinstance(ret['return'], dict):
        back = _remove_dots(ret['return'])
    else:
        back = ret['return']

    log.debug(back)
    col.insert({ret['jid']: back})
