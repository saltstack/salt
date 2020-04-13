# -*- coding: utf-8 -*-
"""
Memcached sdb Module

:maintainer:    SaltStack
:maturity:      New
:depends:       python-memcached
:platform:      all

This module allows access to memcached using an ``sdb://`` URI. This
package is located at ``https://pypi.python.org/pypi/python-memcached``.

Like all sdb modules, the memcached module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    mymemcache:
      driver: memcached
      memcached.host: localhost
      memcached.port: 11211

The ``driver`` refers to the memcached module, ``host`` and ``port`` the
memcached server to connect to (defaults to ``localhost`` and ``11211``,
and ``mymemcached`` refers to the name that will appear in the URI:

.. code-block:: yaml

    password: sdb://mymemcached/mykey

"""
from __future__ import absolute_import, print_function, unicode_literals

# import python libs
import logging

# import Salt libs
import salt.utils.memcached

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11211
DEFAULT_EXPIRATION = 0

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only load the module if memcached is installed
    """
    if salt.utils.memcached.HAS_LIBS:
        return True
    return False


def set_(key, value, profile=None):
    """
    Set a key/value pair in memcached
    """
    conn = salt.utils.memcached.get_conn(profile)
    time = profile.get("expire", DEFAULT_EXPIRATION)
    return salt.utils.memcached.set_(conn, key, value, time=time)


def get(key, profile=None):
    """
    Get a value from memcached
    """
    conn = salt.utils.memcached.get_conn(profile)
    return salt.utils.memcached.get(conn, key)
