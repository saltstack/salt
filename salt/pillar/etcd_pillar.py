"""
Use etcd data as a Pillar source

.. versionadded:: 2014.7.0

.. versionchanged:: 3009.0

    Restored for the etcd v3 API after its removal in 3008.0. It uses
    :mod:`salt.utils.etcd_util`, so the etcd v2 API and the
    ``etcd.require_v2`` option are no longer supported.

:depends:  - etcd3gw

In order to use an etcd server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379

The profile takes the other ``etcd.*`` options of :mod:`salt.utils.etcd_util`
as well, such as ``etcd.username``/``etcd.password`` and the TLS options.

Values are read msgpack-decoded unless the profile sets
``etcd.encode_values: False``. Set it when the values are written by other
tools, such as ``etcdctl``, rather than by Salt.

After the profile is created, configure the external pillar system to use it.
Optionally, a root may be specified.

.. code-block:: yaml

    ext_pillar:
      - etcd: my_etcd_config

    ext_pillar:
      - etcd: my_etcd_config root=/salt

The pillar data is the tree of keys under the root, split on ``/``. Only the
root key and the keys under ``<root>/`` are read, so ``root=/salt`` does not
pick up ``/saltstack``. A root with no keys under it adds no pillar data. An
error talking to etcd fails the pillar render instead of returning empty
pillar data.

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

Using the configuration above, with ``etcd.encode_values: False`` in both
profiles, the following commands could be used to share a key with all minions
but override its value for a specific minion::

    etcdctl put /salt-shared/mykey my_value
    etcdctl put /salt-private/special_minion_id/mykey my_other_value

"""

import logging

import salt.utils.etcd_util

__virtualname__ = "etcd"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only return if etcd3gw is installed
    """
    if salt.utils.etcd_util.HAS_ETCD_V3:
        return __virtualname__
    return (False, "The etcd ext_pillar requires the etcd3gw library")


def ext_pillar(minion_id, pillar, conf):  # pylint: disable=W0613
    """
    Check etcd for all data
    """
    comps = conf.split()

    profile = comps[0] if comps else None
    path = "/"
    for comp in comps[1:]:
        if comp.startswith("root="):
            path = comp[len("root=") :]

    # put the minion's ID in the path if necessary
    path %= {"minion_id": minion_id}

    client = salt.utils.etcd_util.get_conn(__opts__, profile)
    data = client.tree(path)
    if data is None:
        log.debug("etcd ext_pillar: nothing under %s in profile %s", path, profile)
        return {}
    return data
