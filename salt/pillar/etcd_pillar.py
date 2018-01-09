# -*- coding: utf-8 -*-
'''
Use etcd data as a Pillar source

.. versionadded:: 2014.7.0

:depends:  - python-etcd

In order to use an etcd server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

After the profile is created, configure the external pillar system to use it.
Optionally, a root may be specified.

.. code-block:: yaml

    ext_pillar:
      - etcd: my_etcd_config

    ext_pillar:
      - etcd: my_etcd_config root=/salt

Using these configuration profiles, multiple etcd sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - etcd: my_etcd_config
      - etcd: my_other_etcd_config

The ``minion_id`` may be used in the ``root`` path to expose minion-specific
information stored in etcd.

.. code-block:: yaml

    ext_pillar:
      - etcd: my_etcd_config root=/salt/%(minion_id)s

Minion-specific values may override shared values when the minion-specific root
appears after the shared root:

.. code-block:: yaml

    ext_pillar:
      - etcd: my_etcd_config root=/salt-shared
      - etcd: my_other_etcd_config root=/salt-private/%(minion_id)s

Using the configuration above, the following commands could be used to share a
key with all minions but override its value for a specific minion::

    etcdctl set /salt-shared/mykey my_value
    etcdctl set /salt-private/special_minion_id/mykey my_other_value

'''
from __future__ import absolute_import, print_function, unicode_literals

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


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    return __virtualname__ if HAS_LIBS else False


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Check etcd for all data
    '''
    comps = conf.split()

    profile = None
    if comps[0]:
        profile = comps[0]
    client = salt.utils.etcd_util.get_conn(__opts__, profile)

    path = '/'
    if len(comps) > 1 and comps[1].startswith('root='):
        path = comps[1].replace('root=', '')

    # put the minion's ID in the path if necessary
    path %= {
        'minion_id': minion_id
    }

    try:
        pillar = salt.utils.etcd_util.tree(client, path)
    except KeyError:
        log.error('No such key in etcd profile %s: %s', profile, path)
        pillar = {}

    return pillar
