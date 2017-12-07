# -*- coding: utf-8 -*-
'''
Minion data cache plugin for Etcd key/value data store.

.. versionadded:: develop

It is up to the system administrator to set up and configure the Etcd
infrastructure. All is needed for this plugin is a working Etcd agent
with a read-write access to the key-value store.

The related documentation can be found in the `Etcd documentation`_.

To enable this cache plugin, the master will need the python client for
Etcd installed. This can be easily installed with pip:

.. code-block: bash

    pip install python-etcd

Optionally, depending on the Etcd agent configuration, the following values
could be set in the master config. These are the defaults:

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 2379
    etcd.protocol: http
    etcd.allow_reconnect: True
    etcd.allow_redirect: False
    etcd.srv_domain: None
    etcd.read_timeout: 60
    etcd.username: None
    etcd.password: None
    etcd.cert: None
    etcd.ca_cert: None

Related docs could be found in the `python-etcd documentation`_.

To use the etcd as a minion data cache backend, set the master ``cache`` config
value to ``etcd``:

.. code-block:: yaml

    cache: etcd


.. _`Etcd documentation`: https://github.com/coreos/etcd
.. _`python-etcd documentation`: http://python-etcd.readthedocs.io/en/latest/

'''
from __future__ import absolute_import
import logging
try:
    import etcd
    HAS_ETCD = True
except ImportError:
    HAS_ETCD = False

from salt.exceptions import SaltCacheError

_DEFAULT_PATH_PREFIX = u"/salt_cache"

if HAS_ETCD:
    # The client logging tries to decode('ascii') binary data
    # and is too verbose
    etcd._log.setLevel(logging.INFO)  # pylint: disable=W0212

log = logging.getLogger(__name__)
client = None
path_prefix = None

# Module properties

__virtualname__ = u'etcd'
__func_alias__ = {u'ls': u'list'}


def __virtual__():
    '''
    Confirm that python-etcd package is installed.
    '''
    if not HAS_ETCD:
        return (
            False,
            u"Please install python-etcd package to use etcd data cache driver"
        )

    return __virtualname__


def _init_client():
    '''
    Setup client and init datastore
    '''
    global client, path_prefix
    if client is not None:
        return

    etcd_kwargs = {
            u'host': __opts__.get(u'etcd.host', u'127.0.0.1'),
            u'port': __opts__.get(u'etcd.port', 2379),
            u'protocol': __opts__.get(u'etcd.protocol', u'http'),
            u'allow_reconnect': __opts__.get(u'etcd.allow_reconnect', True),
            u'allow_redirect': __opts__.get(u'etcd.allow_redirect', False),
            u'srv_domain': __opts__.get(u'etcd.srv_domain', None),
            u'read_timeout': __opts__.get(u'etcd.read_timeout', 60),
            u'username': __opts__.get(u'etcd.username', None),
            u'password': __opts__.get(u'etcd.password', None),
            u'cert': __opts__.get(u'uetcd.cert', None),
            u'ca_cert': __opts__.get(u'etcd.ca_cert', None),
    }
    path_prefix = __opts__.get(u'etcd.path_prefix', _DEFAULT_PATH_PREFIX)
    if path_prefix != u"":
        path_prefix = u'/{0}'.format(path_prefix.strip(u'/'))
    log.info(u"etcd: Setting up client with params: %r", etcd_kwargs)
    client = etcd.Client(**etcd_kwargs)
    try:
        client.get(path_prefix)
    except etcd.EtcdKeyNotFound:
        log.info(u"etcd: Creating dir %r", path_prefix)
        client.write(path_prefix, None, dir=True)


def store(bank, key, data):
    '''
    Store a key value.
    '''
    _init_client()
    etcd_key = u'{0}/{1}/{2}'.format(path_prefix, bank, key)
    try:
        value = __context__[u'serial'].dumps(data)
        client.set(etcd_key, value)
    except Exception as exc:
        raise SaltCacheError(
            u'There was an error writing the key, {0}: {1}'.format(etcd_key, exc)
        )


def fetch(bank, key):
    '''
    Fetch a key value.
    '''
    _init_client()
    etcd_key = u'{0}/{1}/{2}'.format(path_prefix, bank, key)
    try:
        value = client.get(etcd_key).value
        if value is None:
            return {}
        return __context__[u'serial'].loads(value)
    except Exception as exc:
        raise SaltCacheError(
            u'There was an error reading the key, {0}: {1}'.format(
                etcd_key, exc
            )
        )


def flush(bank, key=None):
    '''
    Remove the key from the cache bank with all the key content.
    '''
    _init_client()
    if key is None:
        etcd_key = u'{0}/{1}'.format(path_prefix, bank)
    else:
        etcd_key = u'{0}/{1}/{2}'.format(path_prefix, bank, key)
    try:
        client.get(etcd_key)
    except etcd.EtcdKeyNotFound:
        return  # nothing to flush
    try:
        client.delete(etcd_key, recursive=True)
    except Exception as exc:
        raise SaltCacheError(
            u'There was an error removing the key, {0}: {1}'.format(
                etcd_key, exc
            )
        )


def _walk(r):
    '''
    Recursively walk dirs. Return flattened list of keys.
    r: etcd.EtcdResult
    '''
    if not r.dir:
        return [r.key.split(u'/', 3)[3]]

    keys = []
    for c in client.get(r.key).children:
        keys.extend(_walk(c))
    return keys


def ls(bank):
    '''
    Return an iterable object containing all entries stored in the specified
    bank.
    '''
    _init_client()
    path = u'{0}/{1}'.format(path_prefix, bank)
    try:
        return _walk(client.get(path))
    except Exception as exc:
        raise SaltCacheError(
            u'There was an error getting the key "{0}": {1}'.format(
                bank, exc
            )
        )


def contains(bank, key):
    '''
    Checks if the specified bank contains the specified key.
    '''
    _init_client()
    etcd_key = u'{0}/{1}/{2}'.format(path_prefix, bank, key)
    try:
        r = client.get(etcd_key)
        # return True for keys, not dirs
        return r.dir is False
    except etcd.EtcdKeyNotFound:
        return False
    except Exception as exc:
        raise SaltCacheError(
            u'There was an error getting the key, {0}: {1}'.format(
                etcd_key, exc
            )
        )
