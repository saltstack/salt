# -*- coding: utf-8 -*-
'''
Utilities for working with etcd

.. versionadded:: 2014.7.0

:depends:  - python-etcd

This library sets up a client object for etcd, using the configuration passed
into the client() function. Normally, this is __opts__. Optionally, a profile
may be passed in. The following configurations are both valid:

.. code-block:: yaml

    # No profile name
    etcd.host: 127.0.0.1
    etcd.port: 4001

    # One or more profiles defined
    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

Once configured, the client() function is passed a set of opts, and optionally,
the name of a profile to be used.

.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.client(__opts__, profile='my_etcd_config')

It should be noted that some usages of etcd require a profile to be specified,
rather than top-level configurations. This being the case, it is better to
always use a named configuration profile, as shown above.
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError

# Import third party libs
try:
    import etcd
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Set up logging
log = logging.getLogger(__name__)


def get_conn(opts, profile=None):
    '''
    .. versionadded:: 2014.7.0

    Return a client object for accessing etcd
    '''
    opts_pillar = opts.get('pillar', {})
    opts_master = opts_pillar.get('master', {})

    opts_merged = {}
    opts_merged.update(opts_master)
    opts_merged.update(opts_pillar)
    opts_merged.update(opts)

    if profile:
        conf = opts_merged.get(profile, {})
    else:
        conf = opts_merged

    host = conf.get('etcd.host', '127.0.0.1')
    port = conf.get('etcd.port', 4001)

    if HAS_LIBS:
        return etcd.Client(host, port)
    else:
        raise CommandExecutionError(
            '(unable to import etcd, '
            'module most likely not installed)'
        )


def tree(client, path):
    '''
    .. versionadded:: 2014.7.0

    Recurse through etcd and return all values
    '''
    ret = {}
    items = client.get(path)

    for item in items.children:
        comps = str(item.key).split('/')
        if item.dir is True:
            if item.key == path:
                continue
            ret[comps[-1]] = tree(client, item.key)
        else:
            ret[comps[-1]] = item.value
    return ret
