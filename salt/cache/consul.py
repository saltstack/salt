"""
Minion data cache plugin for Consul key/value data store.

.. versionadded:: 2016.11.2

.. versionchanged:: 3005

    Timestamp/cache updated support added.

:depends: python-consul >= 0.2.0

It is up to the system administrator to set up and configure the Consul
infrastructure. All is needed for this plugin is a working Consul agent
with a read-write access to the key-value store.

The related documentation can be found in the `Consul documentation`_.

To enable this cache plugin, the master will need the python client for
Consul installed. This can be easily installed with pip:

.. code-block:: bash

    pip install python-consul

Optionally, depending on the Consul agent configuration, the following values
could be set in the master config. These are the defaults:

.. code-block:: yaml

    consul.host: 127.0.0.1
    consul.port: 8500
    consul.token: None
    consul.scheme: http
    consul.consistency: default
    consul.dc: dc1
    consul.verify: True
    consul.timestamp_suffix: .tstamp  # Added in 3005.0

In order to bring the cache APIs into conformity, in 3005.0 timestamp
information gets stored as a separate ``{key}.tstamp`` key/value. If your
existing functionality depends on being able to store normal keys with the
``.tstamp`` suffix, override the ``consul.timestamp_suffix`` default config.

Related docs could be found in the `python-consul documentation`_.

To use the consul as a minion data cache backend, set the master ``cache`` config
value to ``consul``:

.. code-block:: yaml

    cache: consul


.. _`Consul documentation`: https://www.consul.io/docs/index.html
.. _`python-consul documentation`: https://python-consul.readthedocs.io/en/latest/#consul

"""

import logging
import time

import salt.payload
from salt.exceptions import SaltCacheError

try:
    import consul

    HAS_CONSUL = True
except ImportError:
    HAS_CONSUL = False


log = logging.getLogger(__name__)
api = None
_tstamp_suffix = ".tstamp"


# Define the module's virtual name
__virtualname__ = "consul"

__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Confirm this python-consul package is installed
    """
    if not HAS_CONSUL:
        return (
            False,
            "Please install python-consul package to use consul data cache driver",
        )

    consul_kwargs = {
        "host": __opts__.get("consul.host", "127.0.0.1"),
        "port": __opts__.get("consul.port", 8500),
        "token": __opts__.get("consul.token", None),
        "scheme": __opts__.get("consul.scheme", "http"),
        "consistency": __opts__.get("consul.consistency", "default"),
        "dc": __opts__.get("consul.dc", None),
        "verify": __opts__.get("consul.verify", True),
    }

    try:
        global api, _tstamp_suffix
        _tstamp_suffix = __opts__.get("consul.timestamp_suffix", _tstamp_suffix)
        api = consul.Consul(**consul_kwargs)
    except AttributeError:
        return (
            False,
            "Failed to invoke consul.Consul, please make sure you have python-consul >="
            " 0.2.0 installed",
        )

    return __virtualname__


def store(bank, key, data):
    """
    Store a key value.
    """
    c_key = f"{bank}/{key}"
    tstamp_key = f"{bank}/{key}{_tstamp_suffix}"

    try:
        c_data = salt.payload.dumps(data)
        api.kv.put(c_key, c_data)
        api.kv.put(tstamp_key, salt.payload.dumps(int(time.time())))
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"There was an error writing the key, {c_key}: {exc}")


def fetch(bank, key):
    """
    Fetch a key value.
    """
    c_key = f"{bank}/{key}"
    try:
        _, value = api.kv.get(c_key)
        if value is None:
            return {}
        return salt.payload.loads(value["Value"])
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"There was an error reading the key, {c_key}: {exc}")


def flush(bank, key=None):
    """
    Remove the key from the cache bank with all the key content.
    """
    if key is None:
        c_key = bank
        tstamp_key = None
    else:
        c_key = f"{bank}/{key}"
        tstamp_key = f"{bank}/{key}{_tstamp_suffix}"
    try:
        if tstamp_key:
            api.kv.delete(tstamp_key)
        return api.kv.delete(c_key, recurse=key is None)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"There was an error removing the key, {c_key}: {exc}")


def list_(bank):
    """
    Return an iterable object containing all entries stored in the specified bank.
    """
    try:
        _, keys = api.kv.get(bank + "/", keys=True, separator="/")
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f'There was an error getting the key "{bank}": {exc}')
    if keys is None:
        keys = []
    else:
        # Any key could be a branch and a leaf at the same time in Consul
        # so we have to return a list of unique names only.
        out = set()
        for key in keys:
            out.add(key[len(bank) + 1 :].rstrip("/"))
        keys = [o for o in out if not o.endswith(_tstamp_suffix)]
    return keys


def contains(bank, key):
    """
    Checks if the specified bank contains the specified key.
    """
    try:
        c_key = "{}/{}".format(bank, key or "")
        _, value = api.kv.get(c_key, keys=True)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"There was an error getting the key, {c_key}: {exc}")
    return value is not None


def updated(bank, key):
    """
    Return the Unix Epoch timestamp of when the key was last updated. Return
    None if key is not found.
    """
    c_key = f"{bank}/{key}{_tstamp_suffix}"
    try:
        _, value = api.kv.get(c_key)
        if value is None:
            return None
        return salt.payload.loads(value["Value"])
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"There was an error reading the key, {c_key}: {exc}")
