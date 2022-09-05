"""
Return data to an etcd server or cluster

:depends: - python-etcd or etcd3-py

In order to return to an etcd server, a profile should be created in the master
configuration file:

.. code-block:: yaml

    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379

It is technically possible to configure etcd without using a profile, but this
is not considered to be a best practice, especially when multiple etcd servers
or clusters are available.

.. code-block:: yaml

    etcd.host: 127.0.0.1
    etcd.port: 2379

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

A username and password can be set:

.. code-block:: yaml

    etcd.username: larry  # Optional; requires etcd.password to be set
    etcd.password: 123pass  # Optional; requires etcd.username to be set

You can also set a TTL (time to live) value for the returner:

.. code-block:: yaml

    etcd.ttl: 5

Authentication with username and password, and ttl, currently requires the
``master`` branch of ``python-etcd``.

You may also specify different roles for read and write operations. First,
create the profiles as specified above. Then add:

.. code-block:: yaml

    etcd.returner_read_profile: my_etcd_read
    etcd.returner_write_profile: my_etcd_write
"""

import logging

import salt.utils.jid
import salt.utils.json

try:
    import salt.utils.etcd_util

    if salt.utils.etcd_util.HAS_ETCD_V2 or salt.utils.etcd_util.HAS_ETCD_V3:
        HAS_LIBS = True
    else:
        HAS_LIBS = False
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "etcd"


def __virtual__():
    """
    Only return if python-etcd is installed
    """
    if HAS_LIBS:
        return __virtualname__

    return False, "Could not import etcd returner; python-etcd is not installed."


def _get_conn(opts, profile=None):
    """
    Establish a connection to etcd
    """
    if profile is None:
        profile = opts.get("etcd.returner")
    path = opts.get("etcd.returner_root", "/salt/return")
    return salt.utils.etcd_util.get_conn(opts, profile), path


def returner(ret):
    """
    Return data to an etcd server or cluster
    """
    write_profile = __opts__.get("etcd.returner_write_profile")
    if write_profile:
        ttl = __opts__.get(write_profile, {}).get("etcd.ttl")
    else:
        ttl = __opts__.get("etcd.ttl")

    client, path = _get_conn(__opts__, write_profile)
    # Make a note of this minion for the external job cache
    client.set(
        "/".join((path, "minions", ret["id"])),
        ret["jid"],
        ttl=ttl,
    )

    for field in ret:
        # Not using os.path.join because we're not dealing with file paths
        dest = "/".join((path, "jobs", ret["jid"], ret["id"], field))
        client.set(dest, salt.utils.json.dumps(ret[field]), ttl=ttl)


def save_load(jid, load, minions=None):
    """
    Save the load to the specified jid
    """
    log.debug("sdstack_etcd returner <save_load> called jid: %s", jid)
    write_profile = __opts__.get("etcd.returner_write_profile")
    client, path = _get_conn(__opts__, write_profile)
    if write_profile:
        ttl = __opts__.get(write_profile, {}).get("etcd.ttl")
    else:
        ttl = __opts__.get("etcd.ttl")
    client.set(
        "/".join((path, "jobs", jid, ".load.p")),
        salt.utils.json.dumps(load),
        ttl=ttl,
    )


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """
    Included for API consistency
    """


def clean_old_jobs():
    """
    Included for API consistency
    """


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    log.debug("sdstack_etcd returner <get_load> called jid: %s", jid)
    read_profile = __opts__.get("etcd.returner_read_profile")
    client, path = _get_conn(__opts__, read_profile)
    return salt.utils.json.loads(client.get("/".join((path, "jobs", jid, ".load.p"))))


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    log.debug("sdstack_etcd returner <get_jid> called jid: %s", jid)
    ret = {}
    client, path = _get_conn(__opts__)
    items = client.get("/".join((path, "jobs", jid)), recurse=True)
    for id, value in items.items():
        if str(id).endswith(".load.p"):
            continue
        id = id.split("/")[-1]
        ret[id] = {"return": salt.utils.json.loads(value["return"])}
    return ret


def get_fun(fun):
    """
    Return a dict of the last function called for all minions
    """
    log.debug("sdstack_etcd returner <get_fun> called fun: %s", fun)
    ret = {}
    client, path = _get_conn(__opts__)
    items = client.get("/".join((path, "minions")), recurse=True)
    for id, jid in items.items():
        id = str(id).split("/")[-1]
        efun = salt.utils.json.loads(
            client.get("/".join((path, "jobs", str(jid), id, "fun")))
        )
        if efun == fun:
            ret[id] = str(efun)
    return ret


def get_jids():
    """
    Return a list of all job ids
    """
    log.debug("sdstack_etcd returner <get_jids> called")
    ret = []
    client, path = _get_conn(__opts__)
    items = client.get("/".join((path, "jobs")), recurse=True)
    for key, value in items.items():
        if isinstance(value, dict):  # dict means directory
            jid = str(key).split("/")[-1]
            ret.append(jid)
    return ret


def get_minions():
    """
    Return a list of minions
    """
    log.debug("sdstack_etcd returner <get_minions> called")
    ret = []
    client, path = _get_conn(__opts__)
    items = client.get("/".join((path, "minions")), recurse=True)
    for id, _ in items.items():
        id = str(id).split("/")[-1]
        ret.append(id)
    return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    """
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
