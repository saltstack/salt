# -*- coding: utf-8 -*-
'''
Return data to a memcache server

To enable this returner the minion will need the python client for memcache
installed and the following values configured in the minion or master
config, these are the defaults.

.. code-block:: yaml

    memcache.host: 'localhost'
    memcache.port: '11211'

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location.

.. code-block:: yaml

    alternative.memcache.host: 'localhost'
    alternative.memcache.port: '11211'

python2-memcache uses 'localhost' and '11211' as syntax on connection.

To use the memcache returner, append '--return memcache' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return memcache

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return memcache --return_config alternative
'''
from __future__ import absolute_import

# Import python libs
import json
import logging
import salt.utils.jid

import salt.returners

log = logging.getLogger(__name__)

# Import third party libs
try:
    import memcache
    HAS_MEMCACHE = True
except ImportError:
    HAS_MEMCACHE = False

# Define the module's virtual name
__virtualname__ = 'memcache'


def __virtual__():
    if not HAS_MEMCACHE:
        return False
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the memcache options from salt.
    '''
    attrs = {'host': 'host',
             'port': 'port'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def _get_serv(ret):
    '''
    Return a memcache server object
    '''

    _options = _get_options(ret)
    host = _options.get('host')
    port = _options.get('port')

    log.debug('memcache server: {0}:{1}'.format(host, port))
    if not host or not port:
        log.error('Host or port not defined in salt config')
        return

    # Combine host and port to conform syntax of python memcache client
    memcacheoptions = (host, port)

    return memcache.Client(['{0}:{1}'.format(*memcacheoptions)], debug=0)
    # # TODO: make memcacheoptions cluster aware
    # Servers can be passed in two forms:
    # 1. Strings of the form C{"host:port"}, which implies a default weight of 1
    # 2. Tuples of the form C{("host:port", weight)}, where C{weight} is
    #    an integer weight value.


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()


def returner(ret):
    '''
    Return data to a memcache data store
    '''
    serv = _get_serv(ret)
    serv.set('{0}:{1}'.format(ret['id'], ret['jid']), json.dumps(ret))

    # The following operations are neither efficient nor atomic.
    # If there is a way to make them so, this should be updated.
    if ret['id'] not in get_minions():
        r = serv.append('minions', ret['id'] + ',')
        if not r:
            serv.add('minions', ret['id'] + ',')
    if ret['jid'] not in get_jids():
        r = serv.append('jids', ret['jid'] + ',')
        if not r:
            serv.add('jids', ret['jid'] + ',')


def save_load(jid, load):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    serv.set(jid, json.dumps(load))
    serv.append('jids', jid)


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
    data = serv.get(jid)
    if data:
        return json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)
    ret = {}
    for minion in get_minions():
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = json.loads(data)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv(ret=None)
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
    serv = _get_serv(ret=None)
    try:
        return serv.get('jids').strip(',').split(',')
    except AttributeError:
        return []


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    try:
        return serv.get('minions').strip(',').split(',')
    except AttributeError:
        return []
