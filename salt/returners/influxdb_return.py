# -*- coding: utf-8 -*-
'''
Return data to an influxdb server.

.. versionadded:: 2015.8.0

To enable this returner the minion will need the python client for influxdb
installed and the following values configured in the minion or master
config, these are the defaults:

.. code-block:: yaml

    influxdb.db: 'salt'
    influxdb.user: 'salt'
    influxdb.password: 'salt'
    influxdb.host: 'localhost'
    influxdb.port: 8086


Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.influxdb.db: 'salt'
    alternative.influxdb.user: 'salt'
    alternative.influxdb.password: 'salt'
    alternative.influxdb.host: 'localhost'
    alternative.influxdb.port: 6379

To use the influxdb returner, append '--return influxdb' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return influxdb

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return influxdb --return_config alternative
'''
from __future__ import absolute_import

# Import python libs
import json
import logging

# Import Salt libs
import salt.utils.jid
import salt.returners

# Import third party libs
try:
    import influxdb.influxdb08
    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'influxdb'


def __virtual__():
    if not HAS_INFLUXDB:
        return False
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the influxdb options from salt.
    '''
    attrs = {'host': 'host',
             'port': 'port',
             'db': 'db',
             'user': 'user',
             'password': 'password'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_serv(ret=None):
    '''
    Return an influxdb client object
    '''
    _options = _get_options(ret)
    host = _options.get('host')
    port = _options.get('port')
    database = _options.get('db')
    user = _options.get('user')
    password = _options.get('password')

    return influxdb.influxdb08.InfluxDBClient(host=host,
                                              port=port,
                                              username=user,
                                              password=password,
                                              database=database)


def returner(ret):
    '''
    Return data to a influxdb data store
    '''
    serv = _get_serv(ret)

    req = [
            {
                'name': 'returns',
                'columns': ['fun', 'id', 'jid', 'return', 'full_ret'],
                'points': [
                    [ret['fun'], ret['id'], ret['jid'], json.dumps(ret['return']), json.dumps(ret)]
                ],
            }
        ]

    try:
        serv.write_points(req)
    except Exception as ex:
        log.critical('Failed to store return with InfluxDB returner: {0}'.format(ex))


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    req = [
        {
            'name': 'jids',
            'columns': ['jid', 'load'],
            'points': [
                        [jid, json.dumps(load)]
                    ],
        }
    ]

    try:
        serv.write_points(req)
    except Exception as ex:
        log.critical('Failed to store load with InfluxDB returner: {0}'.format(ex))


def save_minions(jid, minions):  # pylint: disable=unused-argument
    '''
    Included for API consistency
    '''
    pass


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv(ret=None)
    sql = "select load from jids where jid = '{0}'".format(jid)

    log.debug(">> Now in get_load {0}".format(jid))
    data = serv.query(sql)
    log.debug(">> Now Data: {0}".format(data))
    if data:
        return data
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)

    sql = "select id, full_ret from returns where jid = '{0}'".format(jid)

    data = serv.query(sql)
    ret = {}
    if data:
        points = data[0]['points']
        for point in points:
            ret[point[3]] = json.loads(point[2])

    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv(ret=None)

    sql = '''select first(id) as fid, first(full_ret) as fret
            from returns
            where fun = '{0}'
            group by fun, id
          '''.format(fun)

    data = serv.query(sql)
    ret = {}
    if data:
        points = data[0]['points']
        for point in points:
            ret[point[1]] = json.loads(point[2])

    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    serv = _get_serv(ret=None)
    sql = "select distinct(jid) from jids"

    #  [{u'points': [[0, u'saltdev']], u'name': u'returns', u'columns': [u'time', u'distinct']}]
    data = serv.query(sql)
    ret = []
    if data:
        for jid in data[0]['points']:
            ret.append(jid[1])

    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    sql = "select distinct(id) from returns"

    data = serv.query(sql)
    ret = []
    if data:
        for jid in data[0]['points']:
            ret.append(jid[1])

    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
