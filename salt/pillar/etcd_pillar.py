# -*- coding: utf-8 -*-
'''
Use etcd data as a Pillar source

.. versionadded:: Helium

:depends:  - python-etcd

In order to use an etcd server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_etd_config:
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
'''

# Import python libs
import logging

# Import third party libs
try:
    from salt.utils import etcd_util
    HAS_LIBS = True
except Exception:
    HAS_LIBS = False

__virtualname__ = 'etcd'

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    return __virtualname__ if HAS_LIBS else False


def ext_pillar(minion_id, pillar, conf):  # pylint: disable=W0613
    '''
    Check etcd for all data
    '''
    comps = conf.split()

    profile = None
    if comps[0]:
        profile = comps[0]
    client = etcd_util.get_conn(__opts__, profile)

    path = '/'
    if len(comps) > 1 and comps[1].startswith('root='):
        path = comps[1].replace('root=', '')

    # put the minion's ID in the path if necessary
    path %= {
        'minion_id': minion_id
    }

    try:
        pillar = etcd_util.tree(client, path)
    except KeyError:
        log.error('No such key in etcd profile %s: %s' % (profile, path))
        pillar = {}

    return pillar
