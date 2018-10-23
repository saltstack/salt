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

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return memcache --return_kwargs '{"host": "hostname.domain.com"}'

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

import salt.utils.jid
import salt.utils.json
import salt.returners
from salt.ext import six

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
        return False, 'Could not import memcache returner; ' \
                      'memcache python client is not installed.'
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

    log.debug('memcache server: %s:%s', host, port)
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


def _get_list(serv, key):
    value = serv.get(key)
    if value:
        return value.strip(',').split(',')
    return []


def _append_list(serv, key, value):
    if value in _get_list(serv, key):
        return
    r = serv.append(key, '{0},'.format(value))
    if not r:
        serv.add(key, '{0},'.format(value))


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def returner(ret):
    '''
    Return data to a memcache data store
    '''
    serv = _get_serv(ret)
    minion = ret['id']
    jid = ret['jid']
    fun = ret['fun']
    rets = salt.utils.json.dumps(ret)
    serv.set('{0}:{1}'.format(jid, minion), rets)  # cache for get_jid
    serv.set('{0}:{1}'.format(fun, minion), rets)  # cache for get_fun

    # The following operations are neither efficient nor atomic.
    # If there is a way to make them so, this should be updated.
    _append_list(serv, 'minions', minion)
    _append_list(serv, 'jids', jid)


def save_load(jid, load, minions=None):
    '''
    Save the load to the specified jid
    '''
    serv = _get_serv(ret=None)
    serv.set(jid, salt.utils.json.dumps(load))
    _append_list(serv, 'jids', jid)


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
    data = serv.get(jid)
    if data:
        return salt.utils.json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv(ret=None)
    minions = _get_list(serv, 'minions')
    returns = serv.get_multi(minions, key_prefix='{0}:'.format(jid))
    # returns = {minion: return, minion: return, ...}
    ret = {}
    for minion, data in six.iteritems(returns):
        ret[minion] = salt.utils.json.loads(data)
    return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv(ret=None)
    minions = _get_list(serv, 'minions')
    returns = serv.get_multi(minions, key_prefix='{0}:'.format(fun))
    # returns = {minion: return, minion: return, ...}
    ret = {}
    for minion, data in six.iteritems(returns):
        ret[minion] = salt.utils.json.loads(data)
    return ret


def get_jids():
    '''
    Return a list of all job ids
    '''
    serv = _get_serv(ret=None)
    jids = _get_list(serv, 'jids')
    loads = serv.get_multi(jids)  # {jid: load, jid: load, ...}
    ret = {}
    for jid, load in six.iteritems(loads):
        ret[jid] = salt.utils.jid.format_jid_instance(jid, salt.utils.json.loads(load))
    return ret


def get_minions():
    '''
    Return a list of minions
    '''
    serv = _get_serv(ret=None)
    return _get_list(serv, 'minions')
