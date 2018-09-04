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

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return influxdb --return_kwargs '{"db": "another-salt"}'

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import requests

# Import Salt libs
import salt.utils.jid
import salt.returners
from salt.utils.decorators import memoize

# Import third party libs
try:
    import influxdb
    import influxdb.influxdb08
    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False

# HTTP API header used to check the InfluxDB version
influxdb_version_header = "X-Influxdb-Version"

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'influxdb'


def __virtual__():
    if not HAS_INFLUXDB:
        return False, 'Could not import influxdb returner; ' \
                      'influxdb python client is not installed.'
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


@memoize
def _get_version(host, port, user, password):
    '''
    Get the InfluxDB server version
    '''
    version = None
    # check the InfluxDB version via the HTTP API
    try:
        result = requests.get("http://{0}:{1}/ping".format(host, port),
                              auth=(user, password))
        if influxdb_version_header in result.headers:
            version = result.headers[influxdb_version_header]
    except Exception as ex:
        log.critical(
            'Failed to query InfluxDB version from HTTP API within InfluxDB '
            'returner: %s', ex
        )
    return version


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
    version = _get_version(host, port, user, password)

    if version and "v0.8" in version:
        return influxdb.influxdb08.InfluxDBClient(host=host,
                            port=port,
                            username=user,
                            password=password,
                            database=database
        )
    else:
        return influxdb.InfluxDBClient(host=host,
                            port=port,
                            username=user,
                            password=password,
                            database=database
        )


def returner(ret):
    '''
    Return data to a influxdb data store
    '''
    serv = _get_serv(ret)

    # strip the 'return' key to avoid data duplication in the database
    json_return = salt.utils.json.dumps(ret['return'])
    del ret['return']
    json_full_ret = salt.utils.json.dumps(ret)

    # create legacy request in case an InfluxDB 0.8.x version is used
    if "influxdb08" in serv.__module__:
        req = [
            {
                'name': 'returns',
                'columns': ['fun', 'id', 'jid', 'return', 'full_ret'],
                'points': [
                    [ret['fun'], ret['id'], ret['jid'], json_return, json_full_ret]
                ],
            }
        ]
    # create InfluxDB 0.9+ version request
    else:
        req = [
            {
                'measurement': 'returns',
                'tags': {
                    'fun': ret['fun'],
                    'id': ret['id'],
                    'jid': ret['jid']
                },
                'fields': {
                    'return': json_return,
                    'full_ret': json_full_ret
                }
            }
        ]

    try:
        serv.write_points(req)
    except Exception as ex:
        log.critical('Failed to store return with InfluxDB returner: %s', ex)


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)

    # create legacy request in case an InfluxDB 0.8.x version is used
    if "influxdb08" in serv.__module__:
        req = [
            {
                'name': 'jids',
                'columns': ['jid', 'load'],
                'points': [
                    [jid, salt.utils.json.dumps(load)]
                ],
            }
        ]
    # create InfluxDB 0.9+ version request
    else:
        req = [
            {
                'measurement': 'jids',
                'tags': {
                    'jid': jid
                },
                'fields': {
                    'load': salt.utils.json.dumps(load)
                }
            }
        ]

    try:
        serv.write_points(req)
    except Exception as ex:
        log.critical('Failed to store load with InfluxDB returner: %s', ex)


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
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

    log.debug(">> Now in get_load %s", jid)
    data = serv.query(sql)
    log.debug(">> Now Data: %s", data)
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
            ret[point[3]] = salt.utils.json.loads(point[2])

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
            ret[point[1]] = salt.utils.json.loads(point[2])

    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    serv = _get_serv(ret=None)
    sql = "select distinct(jid) from jids group by load"

    # [{u'points': [[0, jid, load],
    #               [0, jid, load]],
    #   u'name': u'jids',
    #   u'columns': [u'time', u'distinct', u'load']}]
    data = serv.query(sql)
    ret = {}
    if data:
        for _, jid, load in data[0]['points']:
            ret[jid] = salt.utils.jid.format_jid_instance(jid, salt.utils.json.loads(load))
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
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def event_return(events):
    '''
    Return a list of events to InfluxDB

    This is largely copied from the mysql event_return function and reading over
    the following documentation:
    https://docs.saltstack.com/en/latest/ref/returners/index.html#event-returners
    https://docs.saltstack.com/en/latest/ref/returners/index.html#event-support
    https://github.com/influxdata/influxdb-python

    This was tested with pip module influxdb 5.2.0 installed in a Docker
    container against InfluxDB 1.6.0 (Docker version)


    It should be noted that this code is not very robust and is just a start to
    get this working.
    '''

    client = _get_serv()

    for event in events:
        # This should probably be redone to join all the events together
        # and then send them all at once as long as the server can handle it?
        # This method may require more handling splitting the data into more
        # manageable chunks for sending.
        req = [
            {
                'measurement': 'events',
                'tags': {
                    'master_id': __opts__.get('id', ''),
                    'fun': salt.utils.json.dumps(event['data'].get('fun', '')),
                    'minions': salt.utils.json.dumps(event['data'].get('minions', '') or event['data'].get('id', '')),
                    'jid': salt.utils.json.dumps(event['data'].get('jid', '')),
                    'tag': salt.utils.json.dumps(event['tag']),
                },
                'fields': {

                    'data': salt.utils.json.dumps(event['data']),
                    'full_event': salt.utils.json.dumps(event),
                    'stamp': salt.utils.json.dumps(event['data']['_stamp'])
                }
            }
        ]
        try:
            client.write_points(req)
        except Exception as ex:
            log.critical(
                "Failed to store event with InfluxDB event_return: %s", ex)
        finally:
            log.debug("Finished processing event %s - %s", event['tag'], event['data'])
