'''
Return data to a redis server
This is a VERY simple example for pushing data to a redis server and is not
necessarily intended as a usable interface.
'''

import logging
import pymongo

log = logging.getLogger(__name__)

__opts__ = {
            'mongo.host': 'salt',
            'mongo.port': 27017,
            'mongo.db': 'salt',
           }

def returner(ret):
    '''
    Return data to a redis data store
    '''
    conn = pymongo.Connection(
            __opts__['mongo.host'],
            __opts__['mongo.port'],
            )
    db = conn[__opts__['mongo.db']]
    col = db[ret['id']]
    back = {}
    if type(ret['return']) == type(dict()):
        for key in ret['return']:
            back[key.replace('.', '-')] = ret['return'][key]
    else:
        back = ret['return']
    log.debug( back )
    col.insert({ret['jid']: back})
