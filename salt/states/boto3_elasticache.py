# -*- coding: utf-8 -*-
'''
Manage Elasticache
==================

.. versionadded:: 2014.7.0

Create, destroy and update Elasticache clusters. Be aware that this interacts
with Amazon's services, and so may incur charges.

This module uses boto3 behind the scenes - as a result it inherits any limitations
it boto3's implementation of the AWS API.  It is also designed to as directly as
possible leverage boto3's parameter naming and semantics.  This allows one to use
http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html as an
excellent source for details too involved to reiterate here.

Note:  This module is designed to be transparent to new AWS / boto options - since
all params are passed through directly, any new args to existing functions which
become available after this documentation is written should work immediately.

Brand new API calls, of course, would still require new functions to be added :)

XXX Note: This module currently only supports creation and deletion of
elasticache resources and will not modify clusters when their configuration
changes in your state files.

This module accepts explicit elasticache credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    elasticache.keyid: GKTADJGHEIQSXMKKRBJ08H
    elasticache.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
      keyid: GKTADJGHEIQSXMKKRBJ08H
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    Ensure myelasticache exists:
      boto_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars
    Ensure myelasticache exists:
      boto_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - profile: myprofile

    # Passing in a profile
    Ensure myelasticache exists:
      boto_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''

# Import Python Libs
from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    if 'boto3_elasticache.cache_cluster_exists' in __salt__:
        return 'boto3_elasticache'
    else:
        return False


def cache_cluster_present(name, wait=True, security_groups=None, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Ensure the cache cluster exists.

    name
        Name of the cache cluster (cache cluster id).

    wait
        Boolean, or tuple of 3 integers (the default, 'True', evaluates to '(10, 6, 10)'
        on the backend.  Wait (up to (X * Y * Z) seconds) for confirmation from AWS that the
        cluster is in the 'available' state.

    security_groups
        One or more VPC security groups (names and/or IDs) associated with the cache cluster.
        Note:  This is additive with any sec groups provided via the SecurityGroupIds parameter
               below.  Use this parameter ONLY when you are creating a cluster in a VPC.

    CacheClusterId
        The node group (shard) identifier. This parameter is stored as a lowercase string.
        Constraints:
        - A name must contain from 1 to 20 alphanumeric characters or hyphens.
        - The first character must be a letter.
        - A name cannot end with a hyphen or contain two consecutive hyphens.
        Note:  In the general case this parameter is not needed, as 'name' is used if it's
               not provided.

    ReplicationGroupId
        The ID of the replication group to which this cache cluster should belong. If this
        parameter is specified, the cache cluster is added to the specified replication
        group as a read replica; otherwise, the cache cluster is a standalone primary that
        is not part of any replication group.  If the specified replication group is
        Multi-AZ enabled and the Availability Zone is not specified, the cache cluster is
        created in Availability Zones that provide the best spread of read replicas across
        Availability Zones.
        Notes:  This parameter is ONLY valid if the Engine parameter is redis.
                Due to current limitations on Redis (cluster mode disabled), this parameter
        is not supported on Redis (cluster mode enabled) replication groups.

    AZMode
        Specifies whether the nodes in this Memcached cluster are created in a single
        Availability Zone or created across multiple Availability Zones in the cluster's
        region.  If the AZMode and PreferredAvailabilityZones are not specified,
        ElastiCache assumes single-az mode.
        Note:  This parameter is ONLY supported for Memcached cache clusters.

    PreferredAvailabilityZone
        The EC2 Availability Zone in which the cache cluster is created.  All nodes
        belonging to this Memcached cache cluster are placed in the preferred Availability
        Zone. If you want to create your nodes across multiple Availability Zones, use
        PreferredAvailabilityZones.
        Default:  System chosen Availability Zone.

    PreferredAvailabilityZones
        A list of the Availability Zones in which cache nodes are created. The order of
        the zones in the list is not important.  The number of Availability Zones listed
        must equal the value of NumCacheNodes.  If you want all the nodes in the same
        Availability Zone, use PreferredAvailabilityZone instead, or repeat the
        Availability Zone multiple times in the list.
        Note:  This option is ONLY supported on Memcached.
        Note:  If you are creating your cache cluster in an Amazon VPC (recommended) you
               can only locate nodes in Availability Zones that are associated with the
               subnets in the selected subnet group.
        Default:  System chosen Availability Zones.

    NumCacheNodes
        The initial (integer) number of cache nodes that the cache cluster has.
        Notes:  For clusters running Redis, this value must be 1.
                For clusters running Memcached, this value must be between 1 and 20.

    CacheNodeType
        The compute and memory capacity of the nodes in the node group (shard).
        Valid node types (and pricing for them) are exhaustively described at
        https://aws.amazon.com/elasticache/pricing/
        Notes:  All T2 instances must be created in a VPC
                Redis backup/restore is not supported for Redis (cluster mode disabled)
                T1 and T2 instances. Backup/restore is supported on Redis (cluster mode
                enabled) T2 instances.
                Redis Append-only files (AOF) functionality is not supported for T1 or
                T2 instances.

    Engine
        The name of the cache engine to be used for this cache cluster.  Valid values for
        this parameter are:  memcached | redis

    EngineVersion
        The version number of the cache engine to be used for this cache cluster. To view
        the supported cache engine versions, use the DescribeCacheEngineVersions operation.
        Note:  You can upgrade to a newer engine version but you cannot downgrade to an
               earlier engine version. If you want to use an earlier engine version, you
               must delete the existing cache cluster or replication group and create it
               anew with the earlier engine version.

    CacheParameterGroupName
        The name of the parameter group to associate with this cache cluster. If this
        argument is omitted, the default parameter group for the specified engine is used.
        You cannot use any parameter group which has cluster-enabled='yes' when creating
        a cluster.

    CacheSubnetGroupName
        The name of the Cache Subnet Group to be used for the cache cluster.  Use this
        parameter ONLY when you are creating a cache cluster within a VPC.

        Note:  If you're going to launch your cluster in an Amazon VPC, you need to create
        a subnet group before you start creating a cluster.

    CacheSecurityGroupNames
        A list of Cache Security Group names to associate with this cache cluster.  Use
        this parameter ONLY when you are creating a cache cluster outside of a VPC.

    SecurityGroupIds
        One or more VPC security groups associated with the cache cluster.  Use this
        parameter ONLY when you are creating a cache cluster within a VPC.

    Tags
        A list of tags to be added to this resource.

    SnapshotArns
        A single-element string list containing an Amazon Resource Name (ARN) that
        uniquely identifies a Redis RDB snapshot file stored in Amazon S3. The snapshot
        file is used to populate the node group (shard). The Amazon S3 object name in
        the ARN cannot contain any commas.
        Note: This parameter is ONLY valid if the Engine parameter is redis.

    SnapshotName
        The name of a Redis snapshot from which to restore data into the new node group
        (shard). The snapshot status changes to restoring while the new node group (shard)
        is being created.
        Note:  This parameter is ONLY valid if the Engine parameter is redis.

    PreferredMaintenanceWindow
        Specifies the weekly time range during which maintenance on the cache cluster is
        permitted.  It is specified as a range in the format ddd:hh24:mi-ddd:hh24:mi
        (24H Clock UTC).  The minimum maintenance window is a 60 minute period.
        Valid values for ddd are:  sun, mon, tue, wed, thu, fri, sat
        Example:  sun:23:00-mon:01:30

    Port
        The port number on which each of the cache nodes accepts connections.
        Default:  6379

    NotificationTopicArn
        The Amazon Resource Name (ARN) of the Amazon Simple Notification Service (SNS)
        topic to which notifications are sent.
        Note: The Amazon SNS topic owner must be the same as the cache cluster owner.

    AutoMinorVersionUpgrade
        This (boolean) parameter is currently disabled.

    SnapshotRetentionLimit
        The number of days for which ElastiCache retains automatic snapshots before
        deleting them.
        Note: This parameter is ONLY valid if the Engine parameter is redis.
        Default:  0 (i.e., automatic backups are disabled for this cache cluster).

    SnapshotWindow
        The daily time range (in UTC) during which ElastiCache begins taking a daily
        snapshot of your node group (shard).  If you do not specify this parameter,
        ElastiCache automatically chooses an appropriate time range.
        Note:  This parameter is ONLY valid if the Engine parameter is redis.
        Example:  05:00-09:00

    AuthToken
        The password used to access a password protected server.
        Password constraints:
            Must be only printable ASCII characters.
            Must be at least 16 characters and no more than 128 characters in length.
            Cannot contain any of the following characters: '/', '"', or "@".

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    current = __salt__['boto3_elasticache.describe_cache_clusters'](
            name=name, region=region, key=key, keyid=keyid, profile=profile)
    if current is None:
        if __opts__['test']:
            msg = 'Cache cluster {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['boto3_elasticache.create_cache_cluster'](
            name=name, wait=wait, security_groups=security_groups,
            region=region, key=key, keyid=keyid, profile=profile, **args)
        if created:
            ret['changes']['old'] = None
            config = __salt__['boto_elasticache.get_config'](name, region, key,
                                                             keyid, profile)
            ret['changes']['new'] = config
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} cache cluster.'.format(name)
            return ret
    # TODO: support modification of existing elasticache clusters
    else:
        ret['comment'] = 'Cache cluster {0} is present.'.format(name)
    return ret


def subnet_group_present(name, subnet_ids=None, subnet_names=None,
                         description=None, tags=None, region=None,
                         key=None, keyid=None, profile=None):
    '''
    Ensure ElastiCache subnet group exists.

    .. versionadded:: 2015.8.0

    name
        The name for the ElastiCache subnet group. This value is stored as a lowercase string.

    subnet_ids
        A list of VPC subnet IDs for the cache subnet group.  Exclusive with subnet_names.

    subnet_names
        A list of VPC subnet names for the cache subnet group.  Exclusive with subnet_ids.

    description
        Subnet group description.

    tags
        A list of tags.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_elasticache.subnet_group_exists'](name=name, tags=tags, region=region, key=key,
                                                              keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Subnet group {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_elasticache.create_subnet_group'](name=name, subnet_ids=subnet_ids,
                                                                   subnet_names=subnet_names,
                                                                   description=description, tags=tags,
                                                                   region=region, key=key, keyid=keyid,
                                                                   profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} subnet group.'.format(name)
            return ret
        ret['changes']['old'] = None
        ret['changes']['new'] = name
        ret['comment'] = 'Subnet group {0} created.'.format(name)
        return ret
    ret['comment'] = 'Subnet group present.'
    return ret


def cache_cluster_absent(*args, **kwargs):
    return absent(*args, **kwargs)


def absent(name, wait=True, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the named elasticache cluster is deleted.

    name
        Name of the cache cluster.

    wait
        Boolean. Wait for confirmation from boto that the cluster is in the
        deleting state.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['boto_elasticache.exists'](name, region, key, keyid, profile)

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'Cache cluster {0} is set to be removed.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_elasticache.delete'](name, wait, region, key,
                                                      keyid, profile)
        if deleted:
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} cache cluster.'.format(name)
    else:
        ret['comment'] = '{0} does not exist in {1}.'.format(name, region)
    return ret


def replication_group_present(*args, **kwargs):
    return creategroup(*args, **kwargs)


def creategroup(name, primary_cluster_id, replication_group_description, wait=None,
                region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the a replication group is create.

    name
        Name of replication group

    wait
        Waits for the group to be available

    primary_cluster_id
        Name of the master cache node

    replication_group_description
        Description for the group

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    is_present = __salt__['boto_elasticache.group_exists'](name, region, key, keyid,
                                                                 profile)
    if not is_present:
        if __opts__['test']:
            ret['comment'] = 'Replication {0} is set to be created.'.format(
                name)
            ret['result'] = None
        created = __salt__['boto_elasticache.create_replication_group'](name, primary_cluster_id,
                                                                        replication_group_description,
                                                                        wait, region, key, keyid, profile)
        if created:
            config = __salt__['boto_elasticache.describe_replication_group'](name, region, key, keyid, profile)
            ret['changes']['old'] = None
            ret['changes']['new'] = config
            ret['result'] = True
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} replication group.'.format(name)
    else:
        ret['comment'] = '{0} replication group exists .'.format(name)
        ret['result'] = True
    return ret


def subnet_group_absent(name, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_elasticache.subnet_group_exists'](name=name, tags=tags, region=region, key=key,
                                                              keyid=keyid, profile=profile)
    if not exists:
        ret['result'] = True
        ret['comment'] = '{0} ElastiCache subnet group does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'ElastiCache subnet group {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_elasticache.delete_subnet_group'](name, region, key, keyid, profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete {0} ElastiCache subnet group.'.format(name)
        return ret
    ret['changes']['old'] = name
    ret['changes']['new'] = None
    ret['comment'] = 'ElastiCache subnet group {0} deleted.'.format(name)
    return ret


def replication_group_absent(name, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_elasticache.group_exists'](name=name, region=region, key=key,
                                                       keyid=keyid, profile=profile)
    if not exists:
        ret['result'] = True
        ret['comment'] = '{0} ElastiCache replication group does not exist.'.format(name)
        log.info(ret['comment'])
        return ret

    if __opts__['test']:
        ret['comment'] = 'ElastiCache replication group {0} is set to be removed.'.format(name)
        ret['result'] = True
        return ret
    deleted = __salt__['boto_elasticache.delete_replication_group'](name, region, key, keyid, profile)
    if not deleted:
        ret['result'] = False
        log.error(ret['comment'])
        ret['comment'] = 'Failed to delete {0} ElastiCache replication group.'.format(name)
        return ret
    ret['changes']['old'] = name
    ret['changes']['new'] = None
    ret['comment'] = 'ElastiCache replication group {0} deleted.'.format(name)
    log.info(ret['comment'])
    return ret
