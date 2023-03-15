"""
Minion data cache plugin for Etcd key/value data store.

.. versionadded:: 2018.3.0
.. versionchanged:: 3005

It is up to the system administrator to set up and configure the Etcd
infrastructure. All is needed for this plugin is a working Etcd agent
with a read-write access to the key-value store.

The related documentation can be found in the `Etcd documentation`_.

To enable this cache plugin, the master will need the python client for
Etcd installed. This can be easily installed with pip:

.. code-block:: bash

    pip install python-etcd

.. note::

    While etcd API v3 has been implemented in other places within salt,
    etcd_cache does not support it at this time due to fundamental differences in
    how the versions are designed and v3 not being compatible with the cache API.

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

In Phosphorus, ls/list was changed to always return the final name in the path.
This should only make a difference if you were directly using ``ls`` on paths
that were more or less nested than, for example: ``1/2/3/4``.

.. _`Etcd documentation`: https://github.com/coreos/etcd
.. _`python-etcd documentation`: http://python-etcd.readthedocs.io/en/latest/

"""

import base64
import logging
import time

import salt.payload
from salt.exceptions import SaltCacheError

try:
    import etcd

    HAS_ETCD = True
except ImportError:
    HAS_ETCD = False


_DEFAULT_PATH_PREFIX = "/salt_cache"

if HAS_ETCD:
    # The client logging tries to decode('ascii') binary data
    # and is too verbose
    etcd._log.setLevel(logging.INFO)  # pylint: disable=W0212

log = logging.getLogger(__name__)
client = None
path_prefix = None
_tstamp_suffix = ".tstamp"

# Module properties

__virtualname__ = "etcd"
__func_alias__ = {"ls": "list"}


def __virtual__():
    """
    Confirm that python-etcd package is installed.
    """
    if not HAS_ETCD:
        return (
            False,
            "Please install python-etcd package to use etcd data cache driver",
        )

    return __virtualname__


def _init_client():
    """Setup client and init datastore."""
    global client, path_prefix, _tstamp_suffix
    if client is not None:
        return

    etcd_kwargs = {
        "host": __opts__.get("etcd.host", "127.0.0.1"),
        "port": __opts__.get("etcd.port", 2379),
        "protocol": __opts__.get("etcd.protocol", "http"),
        "allow_reconnect": __opts__.get("etcd.allow_reconnect", True),
        "allow_redirect": __opts__.get("etcd.allow_redirect", False),
        "srv_domain": __opts__.get("etcd.srv_domain", None),
        "read_timeout": __opts__.get("etcd.read_timeout", 60),
        "username": __opts__.get("etcd.username", None),
        "password": __opts__.get("etcd.password", None),
        "cert": __opts__.get("etcd.cert", None),
        "ca_cert": __opts__.get("etcd.ca_cert", None),
    }
    _tstamp_suffix = __opts__.get("etcd.timestamp_suffix", _tstamp_suffix)
    path_prefix = __opts__.get("etcd.path_prefix", _DEFAULT_PATH_PREFIX)
    if path_prefix != "":
        path_prefix = "/{}".format(path_prefix.strip("/"))
    log.info("etcd: Setting up client with params: %r", etcd_kwargs)
    client = etcd.Client(**etcd_kwargs)
    try:
        client.read(path_prefix)
    except etcd.EtcdKeyNotFound:
        log.info("etcd: Creating dir %r", path_prefix)
        client.write(path_prefix, None, dir=True)


def store(bank, key, data):
    """
    Store a key value.
    """
    _init_client()
    etcd_key = "{}/{}/{}".format(path_prefix, bank, key)
    etcd_tstamp_key = "{}/{}/{}".format(path_prefix, bank, key + _tstamp_suffix)
    try:
        value = salt.payload.dumps(data)
        client.write(etcd_key, base64.b64encode(value))
        client.write(etcd_tstamp_key, int(time.time()))
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            "There was an error writing the key, {}: {}".format(etcd_key, exc)
        )


def fetch(bank, key):
    """
    Fetch a key value.
    """
    _init_client()
    etcd_key = "{}/{}/{}".format(path_prefix, bank, key)
    try:
        value = client.read(etcd_key).value
        return salt.payload.loads(base64.b64decode(value))
    except etcd.EtcdKeyNotFound:
        return {}
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            "There was an error reading the key, {}: {}".format(etcd_key, exc)
        )


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content.
    """
    _init_client()
    if key is None:
        etcd_key = "{}/{}".format(path_prefix, bank)
        tstamp_key = None
    else:
        etcd_key = "{}/{}/{}".format(path_prefix, bank, key)
        tstamp_key = "{}/{}/{}".format(path_prefix, bank, key + _tstamp_suffix)
    try:
        client.read(etcd_key)
    except etcd.EtcdKeyNotFound:
        return  # nothing to flush
    try:
        if tstamp_key:
            client.delete(tstamp_key)
        client.delete(etcd_key, recursive=True)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            "There was an error removing the key, {}: {}".format(etcd_key, exc)
        )


def _walk(r):
    """
    Recursively walk dirs. Return flattened list of keys.
    r: etcd.EtcdResult
    """
    if not r.dir:
        if r.key.endswith(_tstamp_suffix):
            return []
        else:
            return [r.key.rsplit("/", 1)[-1]]

    keys = []
    for c in client.read(r.key).children:
        keys.extend(_walk(c))
    return keys


def ls(bank):
    """
    Return an iterable object containing all entries stored in the specified
    bank.
    """
    _init_client()
    path = "{}/{}".format(path_prefix, bank)
    try:
        return _walk(client.read(path))
    except etcd.EtcdKeyNotFound:
        return []
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            'There was an error getting the key "{}": {}'.format(bank, exc)
        ) from exc


def contains(bank, key):
    """
    Checks if the specified bank contains the specified key.
    """
    _init_client()
    etcd_key = "{}/{}/{}".format(path_prefix, bank, key or "")
    try:
        r = client.read(etcd_key)
        # return True for keys, not dirs, unless key is None
        return r.dir if key is None else r.dir is False
    except etcd.EtcdKeyNotFound:
        return False
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            "There was an error getting the key, {}: {}".format(etcd_key, exc)
        )


def updated(bank, key):
    """
    Return Unix Epoch based timestamp of when the bank/key was updated.
    """
    _init_client()
    tstamp_key = "{}/{}/{}".format(path_prefix, bank, key + _tstamp_suffix)
    try:
        value = client.read(tstamp_key).value
        return int(value)
    except etcd.EtcdKeyNotFound:
        return None
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            "There was an error reading the key, {}: {}".format(tstamp_key, exc)
        )
