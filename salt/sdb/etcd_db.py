# -*- coding: utf-8 -*-
'''
etcd Database Module

:maintainer:    SaltStack
:maturity:      New
:depends:       python-etcd
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
      etcd.port: 4001

The ``driver`` refers to the etcd module, ``etcd.host`` refers to the host that
is hosting the etcd database and ``etcd.port`` refers to the port on that host.

.. code-block:: yaml

    password: sdb://myetcd/mypassword

'''

# import python libs
from __future__ import absolute_import
import logging

try:
    import salt.utils.etcd_util
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}

__virtualname__ = 'etcd'


def __virtual__():
    '''
    Only load the module if keyring is installed
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


def set_(key, value, service=None, profile=None):  # pylint: disable=W0613
    '''
    Set a key/value pair in the etcd service
    '''
    client = _get_conn(profile)
    client.set(key, value)
    return get(key, service, profile)


def get(key, service=None, profile=None):  # pylint: disable=W0613
    '''
    Get a value from the etcd service
    '''
    client = _get_conn(profile)
    result = client.get(key)
    return result.value


def _get_conn(profile):
    '''
    Get a connection
    '''
    return salt.utils.etcd_util.get_conn(profile)
