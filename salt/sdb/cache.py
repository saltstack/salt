# -*- coding: utf-8 -*-
"""
cache Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2017.7.0

This module provides access to Salt's cache subsystem.

Like all sdb modules, the cache module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    mastercloudcache:
      driver: cache
      bank: cloud/active/ec2/my-ec2-conf/saltmaster
      cachedir: /var/cache/salt

The ``driver`` refers to the cache module, ``bank`` refers to the cache bank
that contains the data and ``cachedir`` (optional), if used, points to an
alternate directory for cache data storage.

.. code-block:: yaml

    master_ip: sdb://mastercloudcache/public_ips

It is also possible to override both the ``bank`` and ``cachedir`` options
inside the SDB URI:

.. code-block:: yaml

    master_ip: sdb://mastercloudcache/public_ips?cachedir=/var/cache/salt

For this reason, both the ``bank`` and the ``cachedir`` options can be
omitted from the SDB profile. However, if the ``bank`` option is omitted,
it must be specified in the URI:

.. code-block:: yaml

    master_ip: sdb://mastercloudcache/public_ips?bank=cloud/active/ec2/my-ec2-conf/saltmaster
"""

# import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.cache

__func_alias__ = {"set_": "set"}

__virtualname__ = "cache"


def __virtual__():
    """
    Only load the module if keyring is installed
    """
    return __virtualname__


def set_(key, value, service=None, profile=None):  # pylint: disable=W0613
    """
    Set a key/value pair in the cache service
    """
    key, profile = _parse_key(key, profile)
    cache = salt.cache.Cache(__opts__)
    cache.store(profile["bank"], key, value)
    return get(key, service, profile)


def get(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Get a value from the cache service
    """
    key, profile = _parse_key(key, profile)
    cache = salt.cache.Cache(__opts__)
    return cache.fetch(profile["bank"], key=key)


def delete(key, service=None, profile=None):  # pylint: disable=W0613
    """
    Get a value from the cache service
    """
    key, profile = _parse_key(key, profile)
    cache = salt.cache.Cache(__opts__)
    try:
        cache.flush(profile["bank"], key=key)
        return True
    except Exception:  # pylint: disable=broad-except
        return False


def _parse_key(key, profile):
    """
    Parse out a key and update the opts with any override data
    """
    comps = key.split("?")
    if len(comps) > 1:
        for item in comps[1].split("&"):
            newkey, newval = item.split("=")
            profile[newkey] = newval
    if "cachedir" in profile:
        __opts__["cachedir"] = profile["cachedir"]
    return comps[0], profile
