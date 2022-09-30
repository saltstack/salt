"""
etcd Database Module

:maintainer:    SaltStack
:maturity:      New
:depends:       python-etcd or etcd3-py
:platform:      all

.. versionadded:: 2015.5.0

This module allows access to the etcd database using an ``sdb://`` URI. This
package is located at ``https://pypi.python.org/pypi/python-etcd``.

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

In order to choose whether to use etcd API v2 or v3, you can put the following
configuration option in the same place as your etcd configuration.  This option
defaults to true, meaning you will use v2 unless you specify otherwise.

.. code-block:: yaml

    etcd.require_v2: True

.. code-block:: yaml

    password: sdb://myetcd/mypassword

"""


import logging

try:
    import salt.utils.etcd_util

    if salt.utils.etcd_util.HAS_ETCD_V2 or salt.utils.etcd_util.HAS_ETCD_V3:
        HAS_LIBS = True
    else:
        HAS_LIBS = False
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}

__virtualname__ = "etcd"


def __virtual__():
    """
    Only load the module if keyring is installed
    """
    if HAS_LIBS:
        return __virtualname__
    return False


def set_(key, value, service=None, profile=None):  # pylint: disable=W0613
    """
    Set a key/value pair in the etcd service
    """
    client = _get_conn(profile)
    client.set(key, value)
    return get(key, service, profile)


def get(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Get a value from the etcd service
    """
    client = _get_conn(profile)
    return client.get(key)


def delete(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Get a value from the etcd service
    """
    client = _get_conn(profile)
    try:
        client.delete(key)
        return True
    except Exception:  # pylint: disable=broad-except
        return False


def _get_conn(profile):
    """
    Get a connection
    """
    return salt.utils.etcd_util.get_conn(profile)
