"""
etcd Database Module

:depends:       etcd3gw
:platform:      all

.. versionadded:: 2015.5.0

.. versionchanged:: 3009.0

    Restored for the etcd v3 API after its removal in 3008.0. It uses
    :mod:`salt.utils.etcd_util`, so the etcd v2 API and the
    ``etcd.require_v2`` option are no longer supported.

This module allows access to the etcd database using an ``sdb://`` URI. It
needs the ``etcd3gw`` library (``salt-pip install etcd3gw``).

Like all sdb modules, the etcd module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    myetcd:
      driver: etcd
      etcd.host: 127.0.0.1
      etcd.port: 2379

The ``driver`` refers to the etcd module, ``etcd.host`` refers to the host that
is hosting the etcd database and ``etcd.port`` refers to the port on that host.
The profile takes the other ``etcd.*`` options of :mod:`salt.utils.etcd_util`
as well, such as ``etcd.username``/``etcd.password`` and the TLS options.

.. code-block:: yaml

    password: sdb://myetcd/mypassword

Values are stored msgpack-encoded unless the profile sets
``etcd.encode_values: False``. Set it to read values written by other tools,
such as ``etcdctl``.

``get`` returns ``None`` for a key that does not exist. Errors talking to etcd,
such as an unreachable server, bad credentials or a permission error, raise
instead of reading as a missing key.
"""

import salt.utils.etcd_util

__func_alias__ = {"set_": "set"}

__virtualname__ = "etcd"


def __virtual__():
    """
    Only load the module if etcd3gw is installed
    """
    if salt.utils.etcd_util.HAS_ETCD_V3:
        return __virtualname__
    return (False, "The etcd sdb module requires the etcd3gw library")


def set_(key, value, service=None, profile=None):  # pylint: disable=W0613
    """
    Set a key/value pair in the etcd service. Returns the value written.
    """
    return _get_conn(profile).set(key, value)


def get(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Get a value from the etcd service, or ``None`` if the key does not exist
    """
    return _get_conn(profile).get(key)


def delete(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Delete a key from the etcd service. Returns ``True`` if the key was
    deleted and ``False`` if it did not exist.
    """
    return bool(_get_conn(profile).delete(key))


def _get_conn(profile):
    """
    Get a connection from the sdb profile
    """
    return salt.utils.etcd_util.get_conn(profile or {})
