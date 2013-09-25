# -*- coding: utf-8 -*-
'''
Return data to a Cassandra ColumnFamily

Here's an example Keyspace / ColumnFamily setup that works with this
returner::

    create keyspace salt;
    use salt;
    create column family returns
      with key_validation_class='UTF8Type'
      and comparator='UTF8Type'
      and default_validation_class='UTF8Type';

Required python modules: pycassa
'''

# Import python libs
import logging

# Import third party libs
try:
    import pycassa
    HAS_PYCASSA = True
except ImportError:
    HAS_PYCASSA = False

log = logging.getLogger(__name__)

__opts__ = {'cassandra.servers': ['localhost:9160'],
            'cassandra.keyspace': 'salt',
            'cassandra.column_family': 'returns',
            'cassandra.consistency_level': 'ONE'}


def __virtual__():
    if not HAS_PYCASSA:
        return False
    return 'cassandra'


def returner(ret):
    '''
    Return data to a Cassandra ColumnFamily
    '''

    consistency_level = getattr(pycassa.ConsistencyLevel,
                                __opts__['cassandra.consistency_level'])

    pool = pycassa.ConnectionPool(__opts__['cassandra.keyspace'],
                                  __opts__['cassandra.servers'])
    ccf = pycassa.ColumnFamily(pool, __opts__['cassandra.column_family'],
                               write_consistency_level=consistency_level)

    columns = {'fun': ret['fun'],
               'id': ret['id']}
    if isinstance(ret['return'], dict):
        for key, value in ret['return'].items():
            columns['return.{0}'.format(key)] = str(value)
    else:
        columns['return'] = str(ret['return'])

    log.debug(columns)
    ccf.insert(ret['jid'], columns)
