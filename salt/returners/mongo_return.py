'''
Return data to a mongodb server

Required python modules: pymongo
'''

import logging

try:
    import pymongo
    has_pymongo = True
except ImportError:
    has_pymongo = False


log = logging.getLogger(__name__)

__opts__ = {'mongo.db': 'salt',
            'mongo.host': 'salt',
            'mongo.password': '',
            'mongo.port': 27017,
            'mongo.user': ''}


def __virtual__():
    if not has_pymongo:
        return False
    return 'mongo_return'


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
        for key in ret['return']:
            back[key.replace('.', '-')] = ret['return'][key]
    else:
        back = ret['return']

    log.debug(back)
    col.insert({ret['jid']: back})
