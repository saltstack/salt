"""
Use etcd data as a Pillar source

.. versionadded:: 2014.7.0

:depends:  - python-etcd or etcd3-py

In order to use an etcd server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001


In order to choose whether to use etcd API v2 or v3, you can put the following
configuration option in the same place as your etcd configuration.  This option
defaults to true, meaning you will use v2 unless you specify otherwise.

.. code-block:: yaml

    etcd.require_v2: True

When using API v3, there are some specific options available to be configured
within your etcd profile.  They are defaulted to the following...

.. code-block:: yaml

    etcd.encode_keys: False
    etcd.encode_values: True
    etcd.raw_keys: False
    etcd.raw_values: False
    etcd.unicode_errors: "surrogateescape"

``etcd.encode_keys`` indicates whether you want to pre-encode keys using msgpack before
adding them to etcd.

.. note::

    If you set ``etcd.encode_keys`` to ``True``, all recursive functionality will no longer work.
    This includes ``tree`` and ``ls`` and all other methods if you set ``recurse``/``recursive`` to ``True``.
    This is due to the fact that when encoding with msgpack, keys like ``/salt`` and ``/salt/stack`` will have
    differing byte prefixes, and etcd v3 searches recursively using prefixes.

``etcd.encode_values`` indicates whether you want to pre-encode values using msgpack before
adding them to etcd.  This defaults to ``True`` to avoid data loss on non-string values wherever possible.

``etcd.raw_keys`` determines whether you want the raw key or a string returned.

``etcd.raw_values`` determines whether you want the raw value or a string returned.

``etcd.unicode_errors`` determines what you policy to follow when there are encoding/decoding errors.

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

"""

import logging

try:
    import salt.utils.etcd_util

    if salt.utils.etcd_util.HAS_ETCD_V2 or salt.utils.etcd_util.HAS_ETCD_V3:
        HAS_LIBS = True
    else:
        HAS_LIBS = False
except ImportError:
    HAS_LIBS = False

__virtualname__ = "etcd"

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only return if python-etcd is installed
    """
    return __virtualname__ if HAS_LIBS else False


def ext_pillar(minion_id, pillar, conf):  # pylint: disable=W0613
    """
    Check etcd for all data
    """
    comps = conf.split()

    profile = None
    if comps[0]:
        profile = comps[0]
    client = salt.utils.etcd_util.get_conn(__opts__, profile)

    path = "/"
    if len(comps) > 1 and comps[1].startswith("root="):
        path = comps[1].replace("root=", "")

    # put the minion's ID in the path if necessary
    path %= {"minion_id": minion_id}

    try:
        pillar = salt.utils.etcd_util.tree(client, path)
    except KeyError:
        log.error("No such key in etcd profile %s: %s", profile, path)
        pillar = {}

    return pillar
