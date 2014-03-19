# -*- coding: utf-8 -*-
'''
Return data to an etcd server or cluster

:depends: - python-etcd

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001

It is technically possible to configure etcd without using a profile, but this
is not consided to be a best practice, especially when multiple etcd servers or
clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 4001

Additionally, two more options must be specified in the top-level configuration
in order to use the etcd returner:

.. code-block:: yaml

    etcd.returner: my_etcd_config
    etcd.returner_root: /salt/return

The ``etcd.returner`` option specifies which configuration profile to use. The
``etcd.returner_root`` option specifies the path inside etcd to use as the root
of the returner system.

Once the etcd options are configured, the returner may be used:

CLI Example:

    salt '*' test.ping --return etcd
'''

# Import python libs
import logging

# Import third party libs
try:
    import salt.utils.etcd_util
    HAS_LIBS = True
except Exception:
    HAS_LIBS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'etcd'


def __virtual__():
    '''
    Only return if python-etcd is installed
    '''
    return __virtualname__ if HAS_LIBS else False


def returner(ret):
    '''
    Return data to an etcd server or cluster
    '''
    profile = __opts__.get('etcd.returner', None)
    path = __opts__.get('etcd.returner_root', '/salt/return')
    client = salt.utils.etcd_util.get_conn(__opts__, profile)

    for field in ret.keys():
        dest = '/'.join((
            path,
            ret['jid'],
            ret['id'],
            field
        ))
        client.write(dest, ret[field])
