# -*- coding: utf-8 -*-
'''
Execution module to work with etcd

:depends:  - python-etcd

In order to use an etcd server, a profile should be created in the master
configuration file:

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
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import third party libs
try:
    import salt.utils.etcd_util
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
    return __virtualname__ if HAS_LIBS else False


def get_(key, recurse=False, profile=None):
    '''
    .. versionadded:: 2014.7.0

    Get a value from etcd, by direct path

    CLI Examples:

    .. code-block:: bash

        salt myminion etcd.get /path/to/key
        salt myminion etcd.get /path/to/key profile=my_etcd_config
        salt myminion etcd.get /path/to/key recurse=True profile=my_etcd_config
    '''
    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    try:
        result = client.get(key)
    except KeyError as err:
        log.error('etcd: {0}'.format(err))
        return ''
    except Exception:
        raise

    if recurse:
        return salt.utils.etcd_util.tree(client, key)
    else:
        return getattr(result, 'value')


def set_(key, value, profile=None):
    '''
    .. versionadded:: 2014.7.0

    Set a value in etcd, by direct path

    CLI Example:

    .. code-block:: bash

        salt myminion etcd.set /path/to/key value
        salt myminion etcd.set /path/to/key value profile=my_etcd_config
    '''
    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    try:
        result = client.write(key, value)
    except KeyError as err:
        log.error('etcd: {0}'.format(err))
        return ''
    except Exception:
        raise

    return getattr(result, 'value')


def ls_(path='/', profile=None):
    '''
    .. versionadded:: 2014.7.0

    Return all keys and dirs inside a specific path

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.ls /path/to/dir/
        salt myminion etcd.ls /path/to/dir/ profile=my_etcd_config
    '''
    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    try:
        items = client.get(path)
    except KeyError as err:
        log.error('etcd: {0}'.format(err))
        return {}
    except Exception:
        raise

    ret = {}
    for item in items.children:
        if item.dir is True:
            dir_name = '{0}/'.format(item.key)
            ret[dir_name] = {}
        else:
            ret[item.key] = item.value
    return {path: ret}


def rm_(key, recurse=False, profile=None):
    '''
    .. versionadded:: 2014.7.0

    Delete a key from etcd

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.rm /path/to/key
        salt myminion etcd.rm /path/to/key profile=my_etcd_config
        salt myminion etcd.rm /path/to/dir recurse=True profile=my_etcd_config
    '''
    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    try:
        if client.delete(key, recursive=recurse):
            return True
        else:
            return False
    except KeyError as err:
        log.error('etcd: {0}'.format(err))
        return False
    except Exception:
        raise


def tree(path='/', profile=None):
    '''
    .. versionadded:: 2014.7.0

    Recurse through etcd and return all values

    CLI Example:


    .. code-block:: bash

        salt myminion etcd.tree
        salt myminion etcd.tree profile=my_etcd_config
        salt myminion etcd.tree /path/to/keys profile=my_etcd_config
    '''
    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    try:
        return salt.utils.etcd_util.tree(client, path)
    except KeyError as err:
        log.error('etcd: {0}'.format(err))
        return {}
    except Exception:
        raise
