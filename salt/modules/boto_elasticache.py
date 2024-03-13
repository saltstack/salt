"""
Connection module for Amazon Elasticache

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit elasticache credentials but can
    also utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        elasticache.keyid: GKTADJGHEIQSXMKKRBJ08H
        elasticache.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        elasticache.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
"""

# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602


import logging
import time

import salt.utils.odict as odict
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

try:
    # pylint: disable=unused-import
    import boto
    import boto.elasticache

    # pylint: enable=unused-import
    import boto.utils

    logging.getLogger("boto").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

__deprecated__ = (
    3009,
    "boto",
    "https://github.com/salt-extensions/saltext-boto",
)


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs(check_boto3=False)
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](__name__, "elasticache", pack=__salt__)

    return has_boto_reqs


def exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if a cache cluster exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.exists myelasticache
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.describe_cache_clusters(name)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def group_exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if a replication group exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.group_exists myelasticache
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.describe_replication_groups(name)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create_replication_group(
    name,
    primary_cluster_id,
    replication_group_description,
    wait=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create replication group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.create_replication_group myelasticache myprimarycluster description
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not conn:
        return None
    try:
        cc = conn.create_replication_group(
            name, primary_cluster_id, replication_group_description
        )
        if not wait:
            log.info("Created cache cluster %s.", name)
            return True
        while True:
            time.sleep(3)
            config = describe_replication_group(name, region, key, keyid, profile)
            if not config:
                return True
            if config["status"] == "available":
                return True
    except boto.exception.BotoServerError as e:
        msg = f"Failed to create replication group {name}."
        log.error(msg)
        log.debug(e)
        return {}


def delete_replication_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete an ElastiCache replication group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.delete_replication_group my-replication-group \
                region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    try:
        conn.delete_replication_group(name)
        msg = f"Deleted ElastiCache replication group {name}."
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = f"Failed to delete ElastiCache replication group {name}"
        log.error(msg)
        return False


def describe_replication_group(
    name, region=None, key=None, keyid=None, profile=None, parameter=None
):
    """
    Get replication group information.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.describe_replication_group mygroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not conn:
        return None
    try:
        cc = conn.describe_replication_groups(name)
    except boto.exception.BotoServerError as e:
        msg = f"Failed to get config for cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return {}
    ret = odict.OrderedDict()
    cc = cc["DescribeReplicationGroupsResponse"]["DescribeReplicationGroupsResult"]
    cc = cc["ReplicationGroups"][0]

    attrs = [
        "status",
        "description",
        "primary_endpoint",
        "member_clusters",
        "replication_group_id",
        "pending_modified_values",
        "primary_cluster_id",
        "node_groups",
    ]
    for key, val in cc.items():
        _key = boto.utils.pythonize_name(key)
        if _key == "status":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
        if _key == "description":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
        if _key == "replication_group_id":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
        if _key == "member_clusters":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
        if _key == "node_groups":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
        if _key == "pending_modified_values":
            if val:
                ret[_key] = val
            else:
                ret[_key] = None
    return ret


def get_config(name, region=None, key=None, keyid=None, profile=None):
    """
    Get the configuration for a cache cluster.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.get_config myelasticache
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not conn:
        return None
    try:
        cc = conn.describe_cache_clusters(name, show_cache_node_info=True)
    except boto.exception.BotoServerError as e:
        msg = f"Failed to get config for cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return {}
    cc = cc["DescribeCacheClustersResponse"]["DescribeCacheClustersResult"]
    cc = cc["CacheClusters"][0]
    ret = odict.OrderedDict()
    attrs = [
        "engine",
        "cache_parameter_group",
        "cache_cluster_id",
        "cache_security_groups",
        "replication_group_id",
        "auto_minor_version_upgrade",
        "num_cache_nodes",
        "preferred_availability_zone",
        "security_groups",
        "cache_subnet_group_name",
        "engine_version",
        "cache_node_type",
        "notification_configuration",
        "preferred_maintenance_window",
        "configuration_endpoint",
        "cache_cluster_status",
        "cache_nodes",
    ]
    for key, val in cc.items():
        _key = boto.utils.pythonize_name(key)
        if _key not in attrs:
            continue
        if _key == "cache_parameter_group":
            if val:
                ret[_key] = val["CacheParameterGroupName"]
            else:
                ret[_key] = None
        elif _key == "cache_nodes":
            if val:
                ret[_key] = [k for k in val]
            else:
                ret[_key] = []
        elif _key == "cache_security_groups":
            if val:
                ret[_key] = [k["CacheSecurityGroupName"] for k in val]
            else:
                ret[_key] = []
        elif _key == "configuration_endpoint":
            if val:
                ret["port"] = val["Port"]
                ret["address"] = val["Address"]
            else:
                ret["port"] = None
                ret["address"] = None
        elif _key == "notification_configuration":
            if val:
                ret["notification_topic_arn"] = val["TopicArn"]
            else:
                ret["notification_topic_arn"] = None
        else:
            ret[_key] = val
    return ret


def get_node_host(name, region=None, key=None, keyid=None, profile=None):
    """
    Get hostname from cache node

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.get_node_host myelasticache
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not conn:
        return None
    try:
        cc = conn.describe_cache_clusters(name, show_cache_node_info=True)
    except boto.exception.BotoServerError as e:
        msg = f"Failed to get config for cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return {}

    cc = cc["DescribeCacheClustersResponse"]["DescribeCacheClustersResult"]
    host = cc["CacheClusters"][0]["CacheNodes"][0]["Endpoint"]["Address"]
    return host


def get_group_host(name, region=None, key=None, keyid=None, profile=None):
    """
    Get hostname from replication cache group

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.get_group_host myelasticachegroup
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not conn:
        return None
    try:
        cc = conn.describe_replication_groups(name)
    except boto.exception.BotoServerError as e:
        msg = f"Failed to get config for cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return {}

    cc = cc["DescribeReplicationGroupsResponse"]["DescribeReplicationGroupsResult"]
    cc = cc["ReplicationGroups"][0]["NodeGroups"][0]["PrimaryEndpoint"]
    host = cc["Address"]
    return host


def get_all_cache_subnet_groups(
    name=None, region=None, key=None, keyid=None, profile=None
):
    """
    Return a list of all cache subnet groups with details

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.get_all_subnet_groups region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        marker = ""
        groups = []
        while marker is not None:
            ret = conn.describe_cache_subnet_groups(
                cache_subnet_group_name=name, marker=marker
            )
            trimmed = ret.get("DescribeCacheSubnetGroupsResponse", {}).get(
                "DescribeCacheSubnetGroupsResult", {}
            )
            groups += trimmed.get("CacheSubnetGroups", [])
            marker = trimmed.get("Marker", None)
        if not groups:
            log.debug("No ElastiCache subnet groups found.")
        return groups
    except boto.exception.BotoServerError as e:
        log.error(e)
        return []


def list_cache_subnet_groups(
    name=None, region=None, key=None, keyid=None, profile=None
):
    """
    Return a list of all cache subnet group names

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.list_subnet_groups region=us-east-1
    """
    return [
        g["CacheSubnetGroupName"]
        for g in get_all_cache_subnet_groups(name, region, key, keyid, profile)
    ]


def subnet_group_exists(
    name, tags=None, region=None, key=None, keyid=None, profile=None
):
    """
    Check to see if an ElastiCache subnet group exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.subnet_group_exists my-param-group \
                region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    try:
        ec = conn.describe_cache_subnet_groups(cache_subnet_group_name=name)
        if not ec:
            msg = f"ElastiCache subnet group does not exist in region {region}"
            log.debug(msg)
            return False
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def create_subnet_group(
    name,
    description,
    subnet_ids=None,
    subnet_names=None,
    tags=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create an ElastiCache subnet group

    CLI example to create an ElastiCache subnet group::

        salt myminion boto_elasticache.create_subnet_group my-subnet-group \
            "group description" subnet_ids='[subnet-12345678, subnet-87654321]' \
            region=us-east-1
    """
    if not _exactly_one((subnet_ids, subnet_names)):
        raise SaltInvocationError(
            "Exactly one of either 'subnet_ids' or 'subnet_names' must be provided."
        )
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    if subnet_group_exists(name, tags, region, key, keyid, profile):
        return True
    if subnet_names:
        subnet_ids = []
        for n in subnet_names:
            r = __salt__["boto_vpc.get_resource_id"](
                "subnet", n, region=region, key=key, keyid=keyid, profile=profile
            )
            if "id" not in r:
                log.error("Couldn't resolve subnet name %s to an ID.", subnet_name)
                return False
            subnet_ids += [r["id"]]
    try:
        ec = conn.create_cache_subnet_group(name, description, subnet_ids)
        if not ec:
            msg = f"Failed to create ElastiCache subnet group {name}"
            log.error(msg)
            return False
        log.info("Created ElastiCache subnet group %s", name)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = f"Failed to create ElastiCache subnet group {name}"
        log.error(msg)
        return False


def get_cache_subnet_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Get information about a cache subnet group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.get_cache_subnet_group mycache_subnet_group
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        csg = conn.describe_cache_subnet_groups(name)
        csg = csg["DescribeCacheSubnetGroupsResponse"]
        csg = csg["DescribeCacheSubnetGroupsResult"]["CacheSubnetGroups"][0]
    except boto.exception.BotoServerError as e:
        msg = f"Failed to get cache subnet group {name}."
        log.error(msg)
        log.debug(e)
        return False
    except (IndexError, TypeError, KeyError):
        msg = f"Failed to get cache subnet group {name} (2)."
        log.error(msg)
        return False
    ret = {}
    for key, val in csg.items():
        if key == "CacheSubnetGroupName":
            ret["cache_subnet_group_name"] = val
        elif key == "CacheSubnetGroupDescription":
            ret["cache_subnet_group_description"] = val
        elif key == "VpcId":
            ret["vpc_id"] = val
        elif key == "Subnets":
            ret["subnets"] = []
            for subnet in val:
                _subnet = {}
                _subnet["subnet_id"] = subnet["SubnetIdentifier"]
                _az = subnet["SubnetAvailabilityZone"]["Name"]
                _subnet["subnet_availability_zone"] = _az
                ret["subnets"].append(_subnet)
        else:
            ret[key] = val
    return ret


def delete_subnet_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete an ElastiCache subnet group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.delete_subnet_group my-subnet-group \
                region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    try:
        conn.delete_cache_subnet_group(name)
        msg = f"Deleted ElastiCache subnet group {name}."
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = f"Failed to delete ElastiCache subnet group {name}"
        log.error(msg)
        return False


def create(
    name,
    num_cache_nodes=None,
    engine=None,
    cache_node_type=None,
    replication_group_id=None,
    engine_version=None,
    cache_parameter_group_name=None,
    cache_subnet_group_name=None,
    cache_security_group_names=None,
    security_group_ids=None,
    snapshot_arns=None,
    preferred_availability_zone=None,
    preferred_maintenance_window=None,
    port=None,
    notification_topic_arn=None,
    auto_minor_version_upgrade=None,
    wait=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Create a cache cluster.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.create myelasticache 1 redis cache.t1.micro
        cache_security_group_names='["myelasticachesg"]'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.create_cache_cluster(
            name,
            num_cache_nodes,
            cache_node_type,
            engine,
            replication_group_id,
            engine_version,
            cache_parameter_group_name,
            cache_subnet_group_name,
            cache_security_group_names,
            security_group_ids,
            snapshot_arns,
            preferred_availability_zone,
            preferred_maintenance_window,
            port,
            notification_topic_arn,
            auto_minor_version_upgrade,
        )
        if not wait:
            log.info("Created cache cluster %s.", name)
            return True
        while True:
            time.sleep(3)
            config = get_config(name, region, key, keyid, profile)
            if not config:
                return True
            if config["cache_cluster_status"] == "available":
                return True
        log.info("Created cache cluster %s.", name)
    except boto.exception.BotoServerError as e:
        msg = f"Failed to create cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return False


def delete(name, wait=False, region=None, key=None, keyid=None, profile=None):
    """
    Delete a cache cluster.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.delete myelasticache
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.delete_cache_cluster(name)
        if not wait:
            log.info("Deleted cache cluster %s.", name)
            return True
        while True:
            config = get_config(name, region, key, keyid, profile)
            if not config:
                return True
            if config["cache_cluster_status"] == "deleting":
                return True
            time.sleep(2)
        log.info("Deleted cache cluster %s.", name)
        return True
    except boto.exception.BotoServerError as e:
        msg = f"Failed to delete cache cluster {name}."
        log.error(msg)
        log.debug(e)
        return False


def create_cache_security_group(
    name, description, region=None, key=None, keyid=None, profile=None
):
    """
    Create a cache security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.create_cache_security_group myelasticachesg 'My Cache Security Group'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    created = conn.create_cache_security_group(name, description)
    if created:
        log.info("Created cache security group %s.", name)
        return True
    else:
        msg = f"Failed to create cache security group {name}."
        log.error(msg)
        return False


def delete_cache_security_group(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a cache security group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.delete_cache_security_group myelasticachesg 'My Cache Security Group'
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    deleted = conn.delete_cache_security_group(name)
    if deleted:
        log.info("Deleted cache security group %s.", name)
        return True
    else:
        msg = f"Failed to delete cache security group {name}."
        log.error(msg)
        return False


def authorize_cache_security_group_ingress(
    name,
    ec2_security_group_name,
    ec2_security_group_owner_id,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Authorize network ingress from an ec2 security group to a cache security
    group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.authorize_cache_security_group_ingress myelasticachesg myec2sg 879879
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        added = conn.authorize_cache_security_group_ingress(
            name, ec2_security_group_name, ec2_security_group_owner_id
        )
        if added:
            msg = "Added {0} to cache security group {1}."
            msg = msg.format(name, ec2_security_group_name)
            log.info(msg)
            return True
        else:
            msg = "Failed to add {0} to cache security group {1}."
            msg = msg.format(name, ec2_security_group_name)
            log.error(msg)
            return False
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = "Failed to add {0} to cache security group {1}."
        msg = msg.format(name, ec2_security_group_name)
        log.error(msg)
        return False


def revoke_cache_security_group_ingress(
    name,
    ec2_security_group_name,
    ec2_security_group_owner_id,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Revoke network ingress from an ec2 security group to a cache security
    group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_elasticache.revoke_cache_security_group_ingress myelasticachesg myec2sg 879879
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        removed = conn.revoke_cache_security_group_ingress(
            name, ec2_security_group_name, ec2_security_group_owner_id
        )
        if removed:
            msg = "Removed {0} from cache security group {1}."
            msg = msg.format(name, ec2_security_group_name)
            log.info(msg)
            return True
        else:
            msg = "Failed to remove {0} from cache security group {1}."
            msg = msg.format(name, ec2_security_group_name)
            log.error(msg)
            return False
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = "Failed to remove {0} from cache security group {1}."
        msg = msg.format(name, ec2_security_group_name)
        log.error(msg)
        return False
