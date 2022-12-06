"""
Manage Elasticache with boto3
=============================

.. versionadded:: 2017.7.0

Create, destroy and update Elasticache clusters. Be aware that this interacts
with Amazon's services, and so may incur charges.

This module uses boto3 behind the scenes - as a result it inherits any limitations
it boto3's implementation of the AWS API.  It is also designed to as directly as
possible leverage boto3's parameter naming and semantics.  This allows one to use
http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html as an
excellent source for details too involved to reiterate here.

Note:  This module is designed to be transparent ("intentionally ignorant" is the
phrase I used to describe it to my boss) to new AWS / boto options - since all
AWS API params are passed directly through both the state and executions modules,
any new args to existing functions which become available after this documentation
is written should work immediately.

Brand new API calls, of course, would still require new functions to be added :)

This module accepts explicit elasticache credentials but can also utilize IAM
roles assigned to the instance through Instance Profiles. Dynamic credentials are
then automatically obtained from AWS API and no further configuration is necessary.
More information is available
`here <http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

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
      boto3_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

.. code-block:: yaml

    # Using a profile from pillars
    Ensure myelasticache exists:
      boto3_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - profile: myprofile

.. code-block:: yaml

    # Passing in a profile
    Ensure myelasticache exists:
      boto3_elasticache.present:
        - name: myelasticache
        - engine: redis
        - cache_node_type: cache.t1.micro
        - num_cache_nodes: 1
        - notification_topic_arn: arn:aws:sns:us-east-1:879879:my-sns-topic
        - region: us-east-1
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
"""


def __virtual__():
    """
    Only load if boto is available.
    """
    if "boto3_elasticache.cache_cluster_exists" in __salt__:
        return "boto3_elasticache"
    return (False, "boto3_elasticcache module could not be loaded")


def _diff_cache_cluster(current, desired):
    """
    If you need to enhance what modify_cache_cluster() considers when deciding what is to be
    (or can be) updated, add it to 'modifiable' below.  It's a dict mapping the param as used
    in modify_cache_cluster() to that in describe_cache_clusters().  Any data fiddlery that
    needs to be done to make the mappings meaningful should be done in the munging section
    below as well.

    This function will ONLY touch settings that are explicitly called out in 'desired' - any
    settings which might have previously been changed from their 'default' values will not be
    changed back simply by leaving them out of 'desired'.  This is both intentional, and
    much, much easier to code :)
    """
    ### The data formats are annoyingly (and as far as I can can tell, unnecessarily)
    ### different - we have to munge to a common format to compare...
    if current.get("SecurityGroups") is not None:
        current["SecurityGroupIds"] = [
            s["SecurityGroupId"] for s in current["SecurityGroups"]
        ]
    if current.get("CacheSecurityGroups") is not None:
        current["CacheSecurityGroupNames"] = [
            c["CacheSecurityGroupName"] for c in current["CacheSecurityGroups"]
        ]
    if current.get("NotificationConfiguration") is not None:
        current["NotificationTopicArn"] = current["NotificationConfiguration"][
            "TopicArn"
        ]
        current["NotificationTopicStatus"] = current["NotificationConfiguration"][
            "TopicStatus"
        ]
    if current.get("CacheParameterGroup") is not None:
        current["CacheParameterGroupName"] = current["CacheParameterGroup"][
            "CacheParameterGroupName"
        ]

    modifiable = {
        "AutoMinorVersionUpgrade": "AutoMinorVersionUpgrade",
        "AZMode": "AZMode",
        "CacheNodeType": "CacheNodeType",
        "CacheNodeIdsToRemove": None,
        "CacheParameterGroupName": "CacheParameterGroupName",
        "CacheSecurityGroupNames": "CacheSecurityGroupNames",
        "EngineVersion": "EngineVersion",
        "NewAvailabilityZones": None,
        "NotificationTopicArn": "NotificationTopicArn",
        "NotificationTopicStatus": "NotificationTopicStatus",
        "NumCacheNodes": "NumCacheNodes",
        "PreferredMaintenanceWindow": "PreferredMaintenanceWindow",
        "SecurityGroupIds": "SecurityGroupIds",
        "SnapshotRetentionLimit": "SnapshotRetentionLimit",
        "SnapshotWindow": "SnapshotWindow",
    }

    need_update = {}
    for m, o in modifiable.items():
        if m in desired:
            if not o:
                # Always pass these through - let AWS do the math...
                need_update[m] = desired[m]
            else:
                if m in current:
                    # Equivalence testing works fine for current simple type comparisons
                    # This might need enhancement if more complex structures enter the picture
                    if current[m] != desired[m]:
                        need_update[m] = desired[m]
    return need_update


def cache_cluster_present(
    name,
    wait=900,
    security_groups=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    **args
):
    """
    Ensure a given cache cluster exists.

    name
        Name of the cache cluster (cache cluster id).

    wait
        Integer describing how long, in seconds, to wait for confirmation from AWS that the
        resource is in the desired state.  Zero meaning to return success or failure immediately
        of course.  Note that waiting for the cluster to become available is generally the
        better course, as failure to do so will often lead to subsequent failures when managing
        dependent resources.

    security_groups
        One or more VPC security groups (names and/or IDs) associated with the cache cluster.

        .. note::
            This is additive with any sec groups provided via the
            SecurityGroupIds parameter below.  Use this parameter ONLY when you
            are creating a cluster in a VPC.

    CacheClusterId
        The node group (shard) identifier. This parameter is stored as a lowercase string.

        Constraints:

        - A name must contain from 1 to 20 alphanumeric characters or hyphens.
        - The first character must be a letter.
        - A name cannot end with a hyphen or contain two consecutive hyphens.

        .. note::
            In general this parameter is not needed, as 'name' is used if it's
            not provided.

    ReplicationGroupId
        The ID of the replication group to which this cache cluster should belong. If this
        parameter is specified, the cache cluster is added to the specified replication
        group as a read replica; otherwise, the cache cluster is a standalone primary that
        is not part of any replication group.  If the specified replication group is
        Multi-AZ enabled and the Availability Zone is not specified, the cache cluster is
        created in Availability Zones that provide the best spread of read replicas across
        Availability Zones.

        .. note:
            This parameter is ONLY valid if the Engine parameter is redis. Due
            to current limitations on Redis (cluster mode disabled), this
            parameter is not supported on Redis (cluster mode enabled)
            replication groups.

    AZMode
        Specifies whether the nodes in this Memcached cluster are created in a single
        Availability Zone or created across multiple Availability Zones in the cluster's
        region. If the AZMode and PreferredAvailabilityZones are not specified,
        ElastiCache assumes single-az mode.

        .. note::
            This parameter is ONLY supported for Memcached cache clusters.

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

        Default:  System chosen Availability Zones.

        .. note::
            This option is ONLY supported on Memcached.

            If you are creating your cache cluster in an Amazon VPC
            (recommended) you can only locate nodes in Availability Zones that
            are associated with the subnets in the selected subnet group.

    NumCacheNodes
        The initial (integer) number of cache nodes that the cache cluster has.

        .. note::
            For clusters running Redis, this value must be 1.

            For clusters running Memcached, this value must be between 1 and 20.

    CacheNodeType
        The compute and memory capacity of the nodes in the node group (shard).
        Valid node types (and pricing for them) are exhaustively described at
        https://aws.amazon.com/elasticache/pricing/

        .. note::
            All T2 instances must be created in a VPC

           Redis backup/restore is not supported for Redis (cluster mode
           disabled) T1 and T2 instances. Backup/restore is supported on Redis
           (cluster mode enabled) T2 instances.

           Redis Append-only files (AOF) functionality is not supported for T1
           or T2 instances.

    Engine
        The name of the cache engine to be used for this cache cluster.  Valid values for
        this parameter are:  memcached | redis

    EngineVersion
        The version number of the cache engine to be used for this cache cluster. To view
        the supported cache engine versions, use the DescribeCacheEngineVersions operation.

        .. note::
            You can upgrade to a newer engine version but you cannot downgrade
            to an earlier engine version. If you want to use an earlier engine
            version, you must delete the existing cache cluster or replication
            group and create it anew with the earlier engine version.

    CacheParameterGroupName
        The name of the parameter group to associate with this cache cluster. If this
        argument is omitted, the default parameter group for the specified engine is used.
        You cannot use any parameter group which has cluster-enabled='yes' when creating
        a cluster.

    CacheSubnetGroupName
        The name of the Cache Subnet Group to be used for the cache cluster.  Use this
        parameter ONLY when you are creating a cache cluster within a VPC.

        .. note::
            If you're going to launch your cluster in an Amazon VPC, you need
            to create a subnet group before you start creating a cluster.

    CacheSecurityGroupNames
        A list of Cache Security Group names to associate with this cache cluster.  Use
        this parameter ONLY when you are creating a cache cluster outside of a VPC.

    SecurityGroupIds
        One or more VPC security groups associated with the cache cluster.  Use this
        parameter ONLY when you are creating a cache cluster within a VPC.

    Tags
        A list of tags to be added to this resource.  Note that due to shortcomings in the
        AWS API for Elasticache, these can only be set during resource creation - later
        modification is not (currently) supported.

    SnapshotArns
        A single-element string list containing an Amazon Resource Name (ARN) that
        uniquely identifies a Redis RDB snapshot file stored in Amazon S3. The snapshot
        file is used to populate the node group (shard). The Amazon S3 object name in
        the ARN cannot contain any commas.

        .. note::
            This parameter is ONLY valid if the Engine parameter is redis.

    SnapshotName
        The name of a Redis snapshot from which to restore data into the new node group
        (shard). The snapshot status changes to restoring while the new node group (shard)
        is being created.

        .. note::
            This parameter is ONLY valid if the Engine parameter is redis.

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

        .. note::
            The Amazon SNS topic owner must be the same as the cache cluster
            owner.

    AutoMinorVersionUpgrade
        This (boolean) parameter is currently disabled.

    SnapshotRetentionLimit
        The number of days for which ElastiCache retains automatic snapshots before
        deleting them.

        Default:  0 (i.e., automatic backups are disabled for this cache cluster).

        .. note::
            This parameter is ONLY valid if the Engine parameter is redis.

    SnapshotWindow
        The daily time range (in UTC) during which ElastiCache begins taking a daily
        snapshot of your node group (shard).  If you do not specify this parameter,
        ElastiCache automatically chooses an appropriate time range.

        Example:  05:00-09:00

        .. note::
            This parameter is ONLY valid if the Engine parameter is redis.

    AuthToken
        The password used to access a password protected server.

        Password constraints:

        - Must be only printable ASCII characters.
        - Must be at least 16 characters and no more than 128 characters in length.
        - Cannot contain any of the following characters: '/', '"', or "@".

    CacheNodeIdsToRemove
        A list of cache node IDs to be removed. A node ID is a numeric identifier (0001, 0002,
        etc.).  This parameter is only valid when NumCacheNodes is less than the existing number of
        cache nodes.  The number of cache node IDs supplied in this parameter must match the
        difference between the existing number of cache nodes in the cluster or pending cache nodes,
        whichever is greater, and the value of NumCacheNodes in the request.

    NewAvailabilityZones
        The list of Availability Zones where the new Memcached cache nodes are created.
        This parameter is only valid when NumCacheNodes in the request is greater than the sum of
        the number of active cache nodes and the number of cache nodes pending creation (which may
        be zero).  The number of Availability Zones supplied in this list must match the cache nodes
        being added in this request.
        Note:  This option is only supported on Memcached clusters.

    NotificationTopicStatus
        The status of the SNS notification topic.  Notifications are sent only if the status is active.

        Valid values:  active | inactive

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    current = __salt__["boto3_elasticache.describe_cache_clusters"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if current:
        check_update = True
    else:
        check_update = False
        only_on_modify = [
            "CacheNodeIdsToRemove",
            "NewAvailabilityZones",
            "NotificationTopicStatus",
        ]
        create_args = {}
        for k, v in args.items():
            if k in only_on_modify:
                check_update = True
            else:
                create_args[k] = v
        if __opts__["test"]:
            ret["comment"] = "Cache cluster {} would be created.".format(name)
            ret["result"] = None
            return ret
        created = __salt__["boto3_elasticache.create_cache_cluster"](
            name,
            wait=wait,
            security_groups=security_groups,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
            **create_args
        )
        if created:
            new = __salt__["boto3_elasticache.describe_cache_clusters"](
                name, region=region, key=key, keyid=keyid, profile=profile
            )
            ret["comment"] = "Cache cluster {} was created.".format(name)
            ret["changes"]["old"] = None
            ret["changes"]["new"] = new[0]
        else:
            ret["result"] = False
            ret["comment"] = "Failed to create {} cache cluster.".format(name)

    if check_update:
        # Refresh this in case we're updating from 'only_on_modify' above...
        updated = __salt__["boto3_elasticache.describe_cache_clusters"](
            name, region=region, key=key, keyid=keyid, profile=profile
        )
        need_update = _diff_cache_cluster(updated["CacheClusters"][0], args)
        if need_update:
            if __opts__["test"]:
                ret["comment"] = "Cache cluster {} would be modified.".format(name)
                ret["result"] = None
                return ret
            modified = __salt__["boto3_elasticache.modify_cache_cluster"](
                name,
                wait=wait,
                security_groups=security_groups,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
                **need_update
            )
            if modified:
                new = __salt__["boto3_elasticache.describe_cache_clusters"](
                    name, region=region, key=key, keyid=keyid, profile=profile
                )
                if ret["comment"]:  # 'create' just ran...
                    ret["comment"] += " ... and then immediately modified."
                else:
                    ret["comment"] = "Cache cluster {} was modified.".format(name)
                    ret["changes"]["old"] = current
                ret["changes"]["new"] = new[0]
            else:
                ret["result"] = False
                ret["comment"] = "Failed to modify cache cluster {}.".format(name)
        else:
            ret["comment"] = "Cache cluster {} is in the desired state.".format(name)
    return ret


def cache_cluster_absent(
    name, wait=600, region=None, key=None, keyid=None, profile=None, **args
):
    """
    Ensure a given cache cluster is deleted.

    name
        Name of the cache cluster.

    wait
        Integer describing how long, in seconds, to wait for confirmation from AWS that the
        resource is in the desired state.  Zero meaning to return success or failure immediately
        of course.  Note that waiting for the cluster to become available is generally the
        better course, as failure to do so will often lead to subsequent failures when managing
        dependent resources.

    CacheClusterId
        The node group (shard) identifier.
        Note:  In general this parameter is not needed, as 'name' is used if it's not provided.

    FinalSnapshotIdentifier
        The user-supplied name of a final cache cluster snapshot.  This is the unique name
        that identifies the snapshot.  ElastiCache creates the snapshot, and then deletes the
        cache cluster immediately afterward.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    exists = __salt__["boto3_elasticache.cache_cluster_exists"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if exists:
        if __opts__["test"]:
            ret["comment"] = "Cache cluster {} would be removed.".format(name)
            ret["result"] = None
            return ret
        deleted = __salt__["boto3_elasticache.delete_cache_cluster"](
            name,
            wait=wait,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
            **args
        )
        if deleted:
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = "Failed to delete {} cache cluster.".format(name)
    else:
        ret["comment"] = "Cache cluster {} already absent.".format(name)
    return ret


def _diff_replication_group(current, desired):
    """
    If you need to enhance what modify_replication_group() considers when deciding what is to be
    (or can be) updated, add it to 'modifiable' below.  It's a dict mapping the param as used
    in modify_replication_group() to that in describe_replication_groups().  Any data fiddlery
    that needs to be done to make the mappings meaningful should be done in the munging section
    below as well.

    This function will ONLY touch settings that are explicitly called out in 'desired' - any
    settings which might have previously been changed from their 'default' values will not be
    changed back simply by leaving them out of 'desired'.  This is both intentional, and
    much, much easier to code :)
    """
    if current.get("AutomaticFailover") is not None:
        current["AutomaticFailoverEnabled"] = (
            True if current["AutomaticFailover"] in ("enabled", "enabling") else False
        )

    modifiable = {
        # Amazingly, the AWS API provides NO WAY to query the current state of most repl group
        # settings!  All we can do is send a modify op with the desired value, just in case it's
        # different.  And THEN, we can't determine if it's been changed!  Stupid?  YOU BET!
        "AutomaticFailoverEnabled": "AutomaticFailoverEnabled",
        "AutoMinorVersionUpgrade": None,
        "CacheNodeType": None,
        "CacheParameterGroupName": None,
        "CacheSecurityGroupNames": None,
        "EngineVersion": None,
        "NotificationTopicArn": None,
        "NotificationTopicStatus": None,
        "PreferredMaintenanceWindow": None,
        "PrimaryClusterId": None,
        "ReplicationGroupDescription": "Description",
        "SecurityGroupIds": None,
        "SnapshotRetentionLimit": "SnapshotRetentionLimit",
        "SnapshottingClusterId": "SnapshottingClusterId",
        "SnapshotWindow": "SnapshotWindow",
    }

    need_update = {}
    for m, o in modifiable.items():
        if m in desired:
            if not o:
                # Always pass these through - let AWS do the math...
                need_update[m] = desired[m]
            else:
                if m in current:
                    # Equivalence testing works fine for current simple type comparisons
                    # This might need enhancement if more complex structures enter the picture
                    if current[m] != desired[m]:
                        need_update[m] = desired[m]
    return need_update


def replication_group_present(
    name,
    wait=900,
    security_groups=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
    **args
):
    """
    Ensure a replication group exists and is in the given state.

    name
        Name of replication group

    wait
        Integer describing how long, in seconds, to wait for confirmation from AWS that the
        resource is in the desired state.  Zero meaning to return success or failure immediately
        of course.  Note that waiting for the cluster to become available is generally the
        better course, as failure to do so will often lead to subsequent failures when managing
        dependent resources.

    security_groups
        One or more VPC security groups (names and/or IDs) associated with the cache cluster.

        .. note::
            This is additive with any sec groups provided via the
            SecurityGroupIds parameter below.  Use this parameter ONLY when you
            are creating a cluster in a VPC.

    ReplicationGroupId
        The replication group identifier. This parameter is stored as a lowercase string.

        Constraints:

        - A name must contain from 1 to 20 alphanumeric characters or hyphens.
        - The first character must be a letter.
        - A name cannot end with a hyphen or contain two consecutive hyphens.

        .. note::
            In general this parameter is not needed, as 'name' is used if it's
            not provided.

    ReplicationGroupDescription
        A user-created description for the replication group.

    PrimaryClusterId
        The identifier of the cache cluster that serves as the primary for this replication group.
        This cache cluster must already exist and have a status of available.  This parameter is
        not required if NumCacheClusters, NumNodeGroups, or ReplicasPerNodeGroup is specified.

    AutomaticFailoverEnabled
        Specifies whether a read-only replica is automatically promoted to read/write primary if
        the existing primary fails.  If true, Multi-AZ is enabled for this replication group. If
        false, Multi-AZ is disabled for this replication group.

        Default:  False

        .. note::
            AutomaticFailoverEnabled must be enabled for Redis (cluster mode
            enabled) replication groups.

            ElastiCache Multi-AZ replication groups is not supported on:

            - Redis versions earlier than 2.8.6.
            - Redis (cluster mode disabled): T1 and T2 node types.
            - Redis (cluster mode enabled): T2 node types.

    NumCacheClusters
        The number of clusters this replication group initially has.  This parameter is not used
        if there is more than one node group (shard). You should use ReplicasPerNodeGroup instead.
        If Multi-AZ is enabled , the value of this parameter must be at least 2.  The maximum
        permitted value for NumCacheClusters is 6 (primary plus 5 replicas).

    PreferredCacheClusterAZs
        A list of EC2 Availability Zones in which the replication group's cache clusters are
        created. The order of the Availability Zones in the list is the order in which clusters
        are allocated. The primary cluster is created in the first AZ in the list.  This parameter
        is not used if there is more than one node group (shard).  You should use
        NodeGroupConfiguration instead.  The number of Availability Zones listed must equal the
        value of NumCacheClusters.

        Default:  System chosen Availability Zones.

        .. note::
            If you are creating your replication group in an Amazon VPC
            (recommended), you can only locate cache clusters in Availability
            Zones associated with the subnets in the selected subnet group.

    NumNodeGroups
        An optional parameter that specifies the number of node groups (shards)
        for this Redis (cluster mode enabled) replication group. For Redis
        (cluster mode disabled) either omit this parameter or set it to 1.

        Default:  1

    ReplicasPerNodeGroup
        An optional parameter that specifies the number of replica nodes in
        each node group (shard). Valid values are:  0 to 5

    NodeGroupConfiguration
        A list of node group (shard) configuration options. Each node group (shard) configuration
        has the following:  Slots, PrimaryAvailabilityZone, ReplicaAvailabilityZones, ReplicaCount.
        If you're creating a Redis (cluster mode disabled) or a Redis (cluster mode enabled)
        replication group, you can use this parameter to configure one node group (shard) or you
        can omit this parameter.  For fiddly details of the expected data layout of this param, see
        http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html?#ElastiCache.Client.create_replication_group

    CacheNodeType
        The compute and memory capacity of the nodes in the node group (shard).
        See https://aws.amazon.com/elasticache/pricing/ for current sizing, prices, and constraints.

        .. note:
            All T2 instances are created in an Amazon Virtual Private Cloud
            (Amazon VPC). Backup/restore is not supported for Redis (cluster
            mode disabled) T1 and T2 instances. Backup/restore is supported on
            Redis (cluster mode enabled) T2 instances. Redis Append-only files
            (AOF) functionality is not supported for T1 or T2 instances.

    Engine
        The name of the cache engine to be used for the cache clusters in this replication group.

    EngineVersion
        The version number of the cache engine to be used for the cache clusters in this replication
        group. To view the supported cache engine versions, use the DescribeCacheEngineVersions
        operation.

        .. note::
            You can upgrade to a newer engine version but you cannot downgrade
            to an earlier engine version. If you want to use an earlier engine
            version, you must delete the existing cache cluster or replication
            group and create it anew with the earlier engine version.

    CacheParameterGroupName
        The name of the parameter group to associate with this replication group. If this argument
        is omitted, the default cache parameter group for the specified engine is used.

        .. note::
            If you are running Redis version 3.2.4 or later, only one node
            group (shard), and want to use a default parameter group, we
            recommend that you specify the parameter group by name.

            To create a Redis (cluster mode disabled) replication group, use
            CacheParameterGroupName=default.redis3.2

            To create a Redis (cluster mode enabled) replication group, use
            CacheParameterGroupName=default.redis3.2.cluster.on

    CacheSubnetGroupName
        The name of the cache subnet group to be used for the replication group.

        .. note::
            If you're going to launch your cluster in an Amazon VPC, you need
            to create a s group before you start creating a cluster. For more
            information, see Subnets and Subnet Groups.

    CacheSecurityGroupNames
        A list of cache security group names to associate with this replication group.

    SecurityGroupIds
        One or more Amazon VPC security groups associated with this replication group.  Use this
        parameter only when you are creating a replication group in an VPC.

    Tags
        A list of tags to be added to this resource.  Note that due to shortcomings in the
        AWS API for Elasticache, these can only be set during resource creation - later
        modification is not (currently) supported.

    SnapshotArns
        A list of ARNs that uniquely identify the Redis RDB snapshot files stored in Amazon S3.
        These snapshot files are used to populate the replication group.  The Amazon S3 object name
        in the ARN cannot contain any commas. The list must match the number of node groups (shards)
        in the replication group, which means you cannot repartition.

        .. note::
            This parameter is only valid if the Engine parameter is redis.

    SnapshotName
        The name of a snapshot from which to restore data into the new replication group.  The
        snapshot status changes to restoring while the new replication group is being created.
        Note:  This parameter is only valid if the Engine parameter is redis.

    PreferredMaintenanceWindow
        Specifies the weekly time range during which maintenance on the cluster is performed. It is
        specified as a range in the format ddd:hh24:mi-ddd:hh24:mi (24H Clock UTC). The minimum
        maintenance window is a 60 minute period.
        Valid values for ddd are:  sun, mon, tue, wed, thu, fri, sat

        Example:  sun:23:00-mon:01:30

    Port
        The port number on which each member of the replication group accepts connections.

    NotificationTopicArn
        The ARN of an SNS topic to which notifications are sent.

        .. note::
            The SNS topic owner must be the same as the cache cluster owner.

    AutoMinorVersionUpgrade
        This parameter is currently disabled.

    SnapshotRetentionLimit
        The number of days for which ElastiCache will retain automatic snapshots before deleting
        them.

        Default:  0 (that is, automatic backups are disabled for this cache cluster).

        .. note::
            This parameter is only valid if the Engine parameter is redis.

    SnapshotWindow
        The daily time range (in UTC) during which ElastiCache begins taking a daily snapshot of
        your node group (shard).  If you do not specify this parameter, ElastiCache automatically
        chooses an appropriate time range.

        Example:  05:00-09:00

        .. note::
            This parameter is only valid if the Engine parameter is redis.

    AuthToken
        The password used to access a password protected server.
        Password constraints:

        - Must be only printable ASCII characters.
        - Must be at least 16 characters and no more than 128 characters in length.
        - Cannot contain any of the following characters: '/', '"', or "@".

    SnapshottingClusterId
        The cache cluster ID that is used as the daily snapshot source for the replication group.

    NotificationTopicStatus
        The status of the SNS notification topic.  Notifications are sent only if the status is active.
        Valid values:  active | inactive

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    current = __salt__["boto3_elasticache.describe_replication_groups"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if current:
        check_update = True
    else:
        check_update = False
        only_on_modify = ["SnapshottingClusterId", "NotificationTopicStatus"]
        create_args = {}
        for k, v in args.items():
            if k in only_on_modify:
                check_update = True
            else:
                create_args[k] = v
        if __opts__["test"]:
            ret["comment"] = "Replication group {} would be created.".format(name)
            ret["result"] = None
            return ret
        created = __salt__["boto3_elasticache.create_replication_group"](
            name,
            wait=wait,
            security_groups=security_groups,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
            **create_args
        )
        if created:
            new = __salt__["boto3_elasticache.describe_replication_groups"](
                name, region=region, key=key, keyid=keyid, profile=profile
            )
            ret["comment"] = "Replication group {} was created.".format(name)
            ret["changes"]["old"] = None
            ret["changes"]["new"] = new[0]
        else:
            ret["result"] = False
            ret["comment"] = "Failed to create {} replication group.".format(name)

    if check_update:
        # Refresh this in case we're updating from 'only_on_modify' above...
        updated = __salt__["boto3_elasticache.describe_replication_groups"](
            name, region=region, key=key, keyid=keyid, profile=profile
        )[0]
        need_update = _diff_replication_group(updated, args)
        if need_update:
            if __opts__["test"]:
                ret["comment"] = "Replication group {} would be modified.".format(name)
                ret["result"] = None
                return ret
            modified = __salt__["boto3_elasticache.modify_replication_group"](
                name,
                wait=wait,
                security_groups=security_groups,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
                **need_update
            )
            if modified:
                new = __salt__["boto3_elasticache.describe_replication_groups"](
                    name, region=region, key=key, keyid=keyid, profile=profile
                )
                if ret["comment"]:  # 'create' just ran...
                    ret["comment"] += " ... and then immediately modified."
                else:
                    ret["comment"] = "Replication group {} was modified.".format(name)
                    ret["changes"]["old"] = current[0] if current else None
                ret["changes"]["new"] = new[0]
            else:
                ret["result"] = False
                ret["comment"] = "Failed to modify replication group {}.".format(name)
        else:
            ret["comment"] = "Replication group {} is in the desired state.".format(
                name
            )
    return ret


def replication_group_absent(
    name, wait=600, region=None, key=None, keyid=None, profile=None, **args
):
    """
    Ensure a given replication group is deleted.

    name
        Name of the replication group.

    wait
        Integer describing how long, in seconds, to wait for confirmation from AWS that the
        resource is in the desired state.  Zero meaning to return success or failure immediately
        of course.  Note that waiting for the cluster to become available is generally the
        better course, as failure to do so will often lead to subsequent failures when managing
        dependent resources.

    ReplicationGroupId
        The replication group identifier.
        Note:  In general this parameter is not needed, as 'name' is used if it's not provided.

    RetainPrimaryCluster
        If set to true, all of the read replicas are deleted, but the primary node is retained.

    FinalSnapshotIdentifier
        The name of a final node group (shard) snapshot.  ElastiCache creates the snapshot from
        the primary node in the cluster, rather than one of the replicas; this is to ensure that
        it captures the freshest data.  After the final snapshot is taken, the replication group is
        immediately deleted.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    exists = __salt__["boto3_elasticache.replication_group_exists"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if exists:
        if __opts__["test"]:
            ret["comment"] = "Replication group {} would be removed.".format(name)
            ret["result"] = None
            return ret
        deleted = __salt__["boto3_elasticache.delete_replication_group"](
            name,
            wait=wait,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
            **args
        )
        if deleted:
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = "Failed to delete {} replication group.".format(name)
    else:
        ret["comment"] = "Replication group {} already absent.".format(name)
    return ret


def _diff_cache_subnet_group(current, desired):
    """
    If you need to enhance what modify_cache_subnet_group() considers when deciding what is to be
    (or can be) updated, add it to 'modifiable' below.  It's a dict mapping the param as used
    in modify_cache_subnet_group() to that in describe_cache_subnet_group().  Any data fiddlery that
    needs to be done to make the mappings meaningful should be done in the munging section
    below as well.

    This function will ONLY touch settings that are explicitly called out in 'desired' - any
    settings which might have previously been changed from their 'default' values will not be
    changed back simply by leaving them out of 'desired'.  This is both intentional, and
    much, much easier to code :)
    """
    modifiable = {
        "CacheSubnetGroupDescription": "CacheSubnetGroupDescription",
        "SubnetIds": "SubnetIds",
    }

    need_update = {}
    for m, o in modifiable.items():
        if m in desired:
            if not o:
                # Always pass these through - let AWS do the math...
                need_update[m] = desired[m]
            else:
                if m in current:
                    # Equivalence testing works fine for current simple type comparisons
                    # This might need enhancement if more complex structures enter the picture
                    if current[m] != desired[m]:
                        need_update[m] = desired[m]
    return need_update


def cache_subnet_group_present(
    name, subnets=None, region=None, key=None, keyid=None, profile=None, **args
):
    """
    Ensure cache subnet group exists.

    name
        A name for the cache subnet group. This value is stored as a lowercase string.
        Constraints:  Must contain no more than 255 alphanumeric characters or hyphens.

    subnets
        A list of VPC subnets (IDs, Names, or a mix) for the cache subnet group.

    CacheSubnetGroupName
        A name for the cache subnet group. This value is stored as a lowercase string.
        Constraints:  Must contain no more than 255 alphanumeric characters or hyphens.
        Note:  In general this parameter is not needed, as 'name' is used if it's not provided.

    CacheSubnetGroupDescription
        A description for the cache subnet group.

    SubnetIds
        A list of VPC subnet IDs for the cache subnet group.  This is ADDITIVE with 'subnets' above.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    current = __salt__["boto3_elasticache.describe_cache_subnet_groups"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if current:
        check_update = True
    else:
        check_update = False
        if __opts__["test"]:
            ret["comment"] = "Cache subnet group {} would be created.".format(name)
            ret["result"] = None
            return ret
        created = __salt__["boto3_elasticache.create_cache_subnet_group"](
            name,
            subnets=subnets,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
            **args
        )
        if created:
            new = __salt__["boto3_elasticache.describe_cache_subnet_groups"](
                name, region=region, key=key, keyid=keyid, profile=profile
            )
            ret["comment"] = "Cache subnet group {} was created.".format(name)
            ret["changes"]["old"] = None
            ret["changes"]["new"] = new[0]
        else:
            ret["result"] = False
            ret["comment"] = "Failed to create {} cache subnet group.".format(name)

    if check_update:
        need_update = _diff_cache_subnet_group(current, args)
        if need_update:
            if __opts__["test"]:
                ret["comment"] = "Cache subnet group {} would be modified.".format(name)
                ret["result"] = None
                return ret
            modified = __salt__["boto3_elasticache.modify_cache_subnet_group"](
                name,
                subnets=subnets,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile,
                **need_update
            )
            if modified:
                new = __salt__["boto3_elasticache.describe_cache_subnet_groups"](
                    name, region=region, key=key, keyid=keyid, profile=profile
                )
                ret["comment"] = "Cache subnet group {} was modified.".format(name)
                ret["changes"]["old"] = current["CacheSubetGroups"][0]
                ret["changes"]["new"] = new[0]
            else:
                ret["result"] = False
                ret["comment"] = "Failed to modify cache subnet group {}.".format(name)
        else:
            ret["comment"] = "Cache subnet group {} is in the desired state.".format(
                name
            )
    return ret


def cache_subnet_group_absent(
    name, region=None, key=None, keyid=None, profile=None, **args
):
    """
    Ensure a given cache subnet group is deleted.

    name
        Name of the cache subnet group.

    CacheSubnetGroupName
        A name for the cache subnet group.
        Note:  In general this parameter is not needed, as 'name' is used if it's not provided.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    args = {k: v for k, v in args.items() if not k.startswith("_")}
    exists = __salt__["boto3_elasticache.cache_subnet_group_exists"](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if exists:
        if __opts__["test"]:
            ret["comment"] = "Cache subnet group {} would be removed.".format(name)
            ret["result"] = None
            return ret
        deleted = __salt__["boto3_elasticache.delete_cache_subnet_group"](
            name, region=region, key=key, keyid=keyid, profile=profile, **args
        )
        if deleted:
            ret["changes"]["old"] = name
            ret["changes"]["new"] = None
        else:
            ret["result"] = False
            ret["comment"] = "Failed to delete {} cache_subnet group.".format(name)
    else:
        ret["comment"] = "Cache subnet group {} already absent.".format(name)
    return ret
