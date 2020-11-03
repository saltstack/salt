# -*- coding: utf-8 -*-
"""
Module to provide ceph control with salt.

:depends:   - ceph_cfg Python module

.. versionadded:: 2016.11.0
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

log = logging.getLogger(__name__)

__virtualname__ = "ceph"

try:
    import ceph_cfg

    HAS_CEPH_CFG = True
except ImportError:
    HAS_CEPH_CFG = False


def __virtual__():
    if HAS_CEPH_CFG is False:
        msg = "ceph_cfg unavailable: {0} execution module cant be loaded ".format(
            __virtualname__
        )
        return False, msg
    return __virtualname__


def partition_list():
    """
    List partitions by disk

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.partition_list
    """
    return ceph_cfg.partition_list()


def partition_list_osd():
    """
    List all OSD data partitions by partition

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.partition_list_osd
    """
    return ceph_cfg.partition_list_osd()


def partition_list_journal():
    """
    List all OSD journal partitions by partition

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.partition_list_journal
    """
    return ceph_cfg.partition_list_journal()


def osd_discover():
    """
    List all OSD by cluster

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.osd_discover

    """
    return ceph_cfg.osd_discover()


def partition_is(dev):
    """
    Check whether a given device path is a partition or a full disk.

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.partition_is /dev/sdc1
    """
    return ceph_cfg.partition_is(dev)


def zap(target=None, **kwargs):
    """
    Destroy the partition table and content of a given disk.

    .. code-block:: bash

        salt '*' ceph.osd_prepare 'dev'='/dev/vdc' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    dev
        The block device to format.

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    if target is not None:
        log.warning("Depricated use of function, use kwargs")
    target = kwargs.get("dev", target)
    kwargs["dev"] = target
    return ceph_cfg.zap(**kwargs)


def osd_prepare(**kwargs):
    """
    Prepare an OSD

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.osd_prepare 'osd_dev'='/dev/vdc' \\
                'journal_dev'='device' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid' \\
                'osd_fs_type'='xfs' \\
                'osd_uuid'='2a143b73-6d85-4389-a9e9-b8a78d9e1e07' \\
                'journal_uuid'='4562a5db-ff6f-4268-811d-12fd4a09ae98'

    cluster_uuid
        The device to store the osd data on.

    journal_dev
        The journal device. defaults to osd_dev.

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster date will be added too. Defaults to the value found in local config.

    osd_fs_type
        set the file system to store OSD data with. Defaults to "xfs".

    osd_uuid
        set the OSD data UUID. If set will return if OSD with data UUID already exists.

    journal_uuid
        set the OSD journal UUID. If set will return if OSD with journal UUID already exists.
    """
    return ceph_cfg.osd_prepare(**kwargs)


def osd_activate(**kwargs):
    """
    Activate an OSD

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.osd_activate 'osd_dev'='/dev/vdc'
    """
    return ceph_cfg.osd_activate(**kwargs)


def keyring_create(**kwargs):
    """
    Create keyring for cluster

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_create \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.keyring_create(**kwargs)


def keyring_save(**kwargs):
    """
    Create save keyring locally

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_save \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.keyring_save(**kwargs)


def keyring_purge(**kwargs):
    """
    Delete keyring for cluster

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_purge \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.

    If no ceph config file is found, this command will fail.
    """
    return ceph_cfg.keyring_purge(**kwargs)


def keyring_present(**kwargs):
    """
    Returns ``True`` if the keyring is present on disk, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_present \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.keyring_present(**kwargs)


def keyring_auth_add(**kwargs):
    """
    Add keyring to authorized list

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_auth_add \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.keyring_auth_add(**kwargs)


def keyring_auth_del(**kwargs):
    """
    Remove keyring from authorised list

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_osd_auth_del \\
                'keyring_type'='admin' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    keyring_type (required)
        One of ``admin``, ``mon``, ``osd``, ``rgw``, ``mds``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.keyring_auth_del(**kwargs)


def mon_is(**kwargs):
    """
    Returns ``True`` if the target is a mon node, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mon_is \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    return ceph_cfg.mon_is(**kwargs)


def mon_status(**kwargs):
    """
    Get status from mon daemon

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mon_status \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.status(**kwargs)


def mon_quorum(**kwargs):
    """
    Returns ``True`` if the mon daemon is in the quorum, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mon_quorum \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.mon_quorum(**kwargs)


def mon_active(**kwargs):
    """
    Returns ``True`` if the mon daemon is running, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mon_active \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.mon_active(**kwargs)


def mon_create(**kwargs):
    """
    Create a mon node

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mon_create \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.mon_create(**kwargs)


def rgw_pools_create(**kwargs):
    """
    Create pools for rgw

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.rgw_pools_create

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.rgw_pools_create(**kwargs)


def rgw_pools_missing(**kwargs):
    """
    Show pools missing for rgw

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.rgw_pools_missing

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.rgw_pools_missing(**kwargs)


def rgw_create(**kwargs):
    """
    Create a rgw

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.rgw_create \\
                'name' = 'rgw.name' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    name (required)
        The RGW client name. Must start with ``rgw.``

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.rgw_create(**kwargs)


def rgw_destroy(**kwargs):
    """
    Remove a rgw

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.rgw_destroy \\
                'name' = 'rgw.name' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    name (required)
        The RGW client name (must start with ``rgw.``)

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.rgw_destroy(**kwargs)


def mds_create(**kwargs):
    """
    Create a mds

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mds_create \\
                'name' = 'mds.name' \\
                'port' = 1000, \\
                'addr' = 'fqdn.example.org' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    name (required)
        The MDS name (must start with ``mds.``)

    port (required)
        Port to which the MDS will listen

    addr (required)
        Address or IP address for the MDS to listen

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.mds_create(**kwargs)


def mds_destroy(**kwargs):
    """
    Remove a mds

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.mds_destroy \\
                'name' = 'mds.name' \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    name (required)
        The MDS name (must start with ``mds.``)

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.mds_destroy(**kwargs)


def keyring_auth_list(**kwargs):
    """
    List all cephx authorization keys

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.keyring_auth_list \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    return ceph_cfg.keyring_auth_list(**kwargs)


def pool_list(**kwargs):
    """
    List all pools

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.pool_list \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    return ceph_cfg.pool_list(**kwargs)


def pool_add(pool_name, **kwargs):
    """
    Create a pool

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.pool_add pool_name \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    pg_num
        Default to 8

    pgp_num
        Default to pg_num

    pool_type
        can take values "replicated" or "erasure"

    erasure_code_profile
        The "erasure_code_profile"

    crush_ruleset
        The crush map rule set
    """
    return ceph_cfg.pool_add(pool_name, **kwargs)


def pool_del(pool_name, **kwargs):
    """
    Delete a pool

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.pool_del pool_name \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    return ceph_cfg.pool_del(pool_name, **kwargs)


def purge(**kwargs):
    """
    purge ceph configuration on the node

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.purge \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_name
        The cluster name. Defaults to ``ceph``.

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.
    """
    return ceph_cfg.purge(**kwargs)


def ceph_version():
    """
    Get the version of ceph installed

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.ceph_version
    """
    return ceph_cfg.ceph_version()


def cluster_quorum(**kwargs):
    """
    Get the cluster's quorum status

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.cluster_quorum \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.cluster_quorum(**kwargs)


def cluster_status(**kwargs):
    """
    Get the cluster status, including health if in quorum

    CLI Example:

    .. code-block:: bash

        salt '*' ceph.cluster_status \\
                'cluster_name'='ceph' \\
                'cluster_uuid'='cluster_uuid'

    cluster_uuid
        The cluster UUID. Defaults to value found in ceph config file.

    cluster_name
        The cluster name. Defaults to ``ceph``.
    """
    return ceph_cfg.cluster_status(**kwargs)
