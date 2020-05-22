# -*- coding: utf-8 -*-
"""
Utilities for working with memcache

:depends:  - python-memcached

This library sets up a connection object for memcache, using the configuration
passed into the get_conn() function. Normally, this is __opts__. Optionally,
a profile or specific host and port may be passed in. If neither profile nor
host and port are provided, the defaults of '`127.0.0.`` and ``11211`` are
used. The following configurations are both valid:

.. code-block:: yaml

    # No profile name
    memcached.host: 127.0.0.1
    memcached.port: 11211

    # One or more profiles defined
    my_memcached_config:
      memcached.host: 127.0.0.1
      memcached.port: 11211

Once configured, the get_conn() function is passed a set of opts, and,
optionally, the name of a profile to be used.

.. code-block:: python

    import salt.utils.memcached_utils.py
    conn = salt.utils.memcached_utils.get_conn(__opts__,
                                              profile='my_memcached_config')

It should be noted that some usages of memcached may require a profile to be
specified, rather than top-level configurations. This being the case, it is
better to always use a named configuration profile, as shown above.
"""

# Import python libs
from __future__ import absolute_import, unicode_literals

import logging

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six
from salt.ext.six import integer_types

# Import third party libs
try:
    import memcache

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11211
DEFAULT_TIME = 0
DEFAULT_MIN_COMPRESS_LEN = 0

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-ins
__func_alias__ = {"set_": "set"}


# Although utils are often directly imported, it is also possible
# to use the loader.
def __virtual__():
    """
    Only load if python-memcached is installed
    """
    return True if HAS_LIBS else False


def get_conn(opts, profile=None, host=None, port=None):
    """
    Return a conn object for accessing memcached
    """
    if not (host and port):
        opts_pillar = opts.get("pillar", {})
        opts_master = opts_pillar.get("master", {})

        opts_merged = {}
        opts_merged.update(opts_master)
        opts_merged.update(opts_pillar)
        opts_merged.update(opts)

        if profile:
            conf = opts_merged.get(profile, {})
        else:
            conf = opts_merged

        host = conf.get("memcached.host", DEFAULT_HOST)
        port = conf.get("memcached.port", DEFAULT_PORT)

    if not six.text_type(port).isdigit():
        raise SaltInvocationError("port must be an integer")

    if HAS_LIBS:
        return memcache.Client(["{0}:{1}".format(host, port)])
    else:
        raise CommandExecutionError(
            "(unable to import memcache, " "module most likely not installed)"
        )


def _check_stats(conn):
    """
    Helper function to check the stats data passed into it, and raise an
    exception if none are returned. Otherwise, the stats are returned.
    """
    stats = conn.get_stats()
    if not stats:
        raise CommandExecutionError("memcached server is down or does not exist")
    return stats


def set_(
    conn, key, value, time=DEFAULT_TIME, min_compress_len=DEFAULT_MIN_COMPRESS_LEN
):
    """
    Set a key on the memcached server, overwriting the value if it exists.
    """
    if not isinstance(time, integer_types):
        raise SaltInvocationError("'time' must be an integer")
    if not isinstance(min_compress_len, integer_types):
        raise SaltInvocationError("'min_compress_len' must be an integer")
    _check_stats(conn)
    return conn.set(key, value, time, min_compress_len)


def get(conn, key):
    """
    Retrieve value for a key
    """
    _check_stats(conn)
    return conn.get(key)
