# -*- coding: utf-8 -*-
'''
Execution module to work with etcd

:depends:  - python-etcd

Configuration
-------------

To work with an etcd server you must configure an etcd profile. The etcd config
can be set in either the Salt Minion configuration file or in pillar:

.. code-block:: yaml

    my_etd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 4001

.. note::

    The etcd configuration can also be set in the Salt Master config file,
    but in order to use any etcd configurations defined in the Salt Master
    config, the :conf_master:`pillar_opts` must be set to ``True``.

    Be aware that setting ``pillar_opts`` to ``True`` has security implications
    as this makes all master configuration settings available in all minion's
    pillars.

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import third party libs
try:
    import salt.utils.etcd_util  # pylint: disable=W0611
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

__virtualname__ = 'etcd'

# Set up logging
log = logging.getLogger(__name__)


# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    'get_': 'get',
    'set_': 'set',
    'rm_': 'rm',
    'ls_': 'ls'
}


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The etcd_mod execution module cannot be loaded: '
            'python etcd library not available.')


def get_(key, recurse=False, profile=None, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Get a value from etcd, by direct path.  Returns None on failure.

    CLI Examples:

    .. code-block:: bash

        salt myminion etcd.get /path/to/key
        salt myminion etcd.get /path/to/key profile=my_etcd_config
        salt myminion etcd.get /path/to/key recurse=True profile=my_etcd_config
        salt myminion etcd.get /path/to/key host=127.0.0.1 port=2379
    '''
    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    if recurse:
        return client.tree(key)
    else:
        return client.get(key, recurse=recurse)


def set_(key, value, profile=None, ttl=None, directory=False, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Set a key in etcd by direct path. Optionally, create a directory
    or set a TTL on the key.  Returns None on failure.

    CLI Example:

    .. code-block:: bash

        salt myminion etcd.set /path/to/key value
        salt myminion etcd.set /path/to/key value profile=my_etcd_config
        salt myminion etcd.set /path/to/key value host=127.0.0.1 port=2379
        salt myminion etcd.set /path/to/dir '' directory=True
        salt myminion etcd.set /path/to/key value ttl=5
    '''

    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.set(key, value, ttl=ttl, directory=directory)


def update(fields, path='', profile=None, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Sets a dictionary of values in one call.  Useful for large updates
    in syndic environments.  The dictionary can contain a mix of formats
    such as:

    .. code-block:: python

        {
          '/some/example/key': 'bar',
          '/another/example/key': 'baz'
        }

    Or it may be a straight dictionary, which will be flattened to look
    like the above format:

    .. code-block:: python

        {
            'some': {
                'example': {
                    'key': 'bar'
                }
            },
            'another': {
                'example': {
                    'key': 'baz'
                }
            }
        }

    You can even mix the two formats and it will be flattened to the first
    format.  Leading and trailing '/' will be removed.

    Empty directories can be created by setting the value of the key to an
    empty dictionary.

    The 'path' parameter will optionally set the root of the path to use.

    CLI Example:

    .. code-block:: bash

        salt myminion etcd.update "{'/path/to/key': 'baz', '/another/key': 'bar'}"
        salt myminion etcd.update "{'/path/to/key': 'baz', '/another/key': 'bar'}" profile=my_etcd_config
        salt myminion etcd.update "{'/path/to/key': 'baz', '/another/key': 'bar'}" host=127.0.0.1 port=2379
        salt myminion etcd.update "{'/path/to/key': 'baz', '/another/key': 'bar'}" path='/some/root'
    '''
    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.update(fields, path)


def watch(key, recurse=False, profile=None, timeout=0, index=None, **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Makes a best effort to watch for a key or tree change in etcd.
    Returns a dict containing the new key value ( or None if the key was
    deleted ), the modifiedIndex of the key, whether the key changed or
    not, the path to the key that changed and whether it is a directory or not.

    If something catastrophic happens, returns {}

    CLI Example:

    .. code-block:: bash

        salt myminion etcd.watch /path/to/key
        salt myminion etcd.watch /path/to/key timeout=10
        salt myminion etcd.watch /patch/to/key profile=my_etcd_config index=10
        salt myminion etcd.watch /patch/to/key host=127.0.0.1 port=2379
    '''

    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.watch(key, recurse=recurse, timeout=timeout, index=index)


def ls_(path='/', profile=None, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Return all keys and dirs inside a specific path. Returns an empty dict on
    failure.

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.ls /path/to/dir/
        salt myminion etcd.ls /path/to/dir/ profile=my_etcd_config
        salt myminion etcd.ls /path/to/dir/ host=127.0.0.1 port=2379
    '''
    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.ls(path)


def rm_(key, recurse=False, profile=None, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Delete a key from etcd.  Returns True if the key was deleted, False if it wasn
    not and None if there was a failure.

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.rm /path/to/key
        salt myminion etcd.rm /path/to/key profile=my_etcd_config
        salt myminion etcd.rm /path/to/key host=127.0.0.1 port=2379
        salt myminion etcd.rm /path/to/dir recurse=True profile=my_etcd_config
    '''
    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.rm(key, recurse=recurse)


def tree(path='/', profile=None, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Recurse through etcd and return all values.  Returns None on failure.

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.tree
        salt myminion etcd.tree profile=my_etcd_config
        salt myminion etcd.tree host=127.0.0.1 port=2379
        salt myminion etcd.tree /path/to/keys profile=my_etcd_config
    '''
    client = __utils__['etcd_util.get_conn'](__opts__, profile, **kwargs)
    return client.tree(path)
