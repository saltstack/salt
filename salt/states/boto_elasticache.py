# -*- coding: utf-8 -*-
'''
Manage Elasticache
==================

.. versionadded:: 2014.7.0

Create, destroy and update Elasticache clusters. Be aware that this interacts
with Amazon's services, and so may incur charges.

Note: This module currently only supports creation and deletion of
elasticache resources and will not modify clusters when their configuration
changes in your state files.

This module uses ``boto``, which can be installed via package, or pip.

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


def __virtual__():
    '''
    Only load if boto is available.
    '''
    if 'boto_elasticache.exists' in __salt__:
        return 'boto_elasticache'
    else:
        return False


def present(
        name,
        engine,
        cache_node_type,
        num_cache_nodes=1,
        preferred_availability_zone=None,
        port=None,
        cache_parameter_group_name=None,
        cache_security_group_names=None,
        replication_group_id=None,
        auto_minor_version_upgrade=True,
        security_group_ids=None,
        cache_subnet_group_name=None,
        engine_version=None,
        notification_topic_arn=None,
        preferred_maintenance_window=None,
        wait=True,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the cache cluster exists.

    name
        Name of the cache cluster (cache cluster id).

    engine
        The name of the cache engine to be used for this cache cluster. Valid
        values are memcached or redis.

    cache_node_type
        The compute and memory capacity of the nodes in the cache cluster.
        cache.t1.micro, cache.m1.small, etc. See: http://boto.readthedocs.org/en/latest/ref/elasticache.html#boto.elasticache.layer1.ElastiCacheConnection.create_cache_cluster

    num_cache_nodes
        The number of cache nodes that the cache cluster will have.

    preferred_availability_zone
        The EC2 Availability Zone in which the cache cluster will be created.
        All cache nodes belonging to a cache cluster are placed in the
        preferred availability zone.

    port
        The port number on which each of the cache nodes will accept
        connections.

    cache_parameter_group_name
        The name of the cache parameter group to associate with this cache
        cluster. If this argument is omitted, the default cache parameter group
        for the specified engine will be used.

    cache_security_group_names
        A list of cache security group names to associate with this cache
        cluster. Use this parameter only when you are creating a cluster
        outside of a VPC.

    replication_group_id
        The replication group to which this cache cluster should belong. If
        this parameter is specified, the cache cluster will be added to the
        specified replication group as a read replica; otherwise, the cache
        cluster will be a standalone primary that is not part of any
        replication group.

    auto_minor_version_upgrade
        Determines whether minor engine upgrades will be applied automatically
        to the cache cluster during the maintenance window. A value of True
        allows these upgrades to occur; False disables automatic upgrades.

    security_group_ids
        One or more VPC security groups associated with the cache cluster. Use
        this parameter only when you are creating a cluster in a VPC.

    cache_subnet_group_name
        The name of the cache subnet group to be used for the cache cluster.
        Use this parameter only when you are creating a cluster in a VPC.

    engine_version
        The version number of the cache engine to be used for this cluster.

    notification_topic_arn
        The Amazon Resource Name (ARN) of the Amazon Simple Notification
        Service (SNS) topic to which notifications will be sent. The Amazon SNS
        topic owner must be the same as the cache cluster owner.

    preferred_maintenance_window
        The weekly time range (in UTC) during which system maintenance can
        occur. Example: sun:05:00-sun:09:00

    wait
        Boolean. Wait for confirmation from boto that the cluster is in the
        creating state.

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
    if cache_security_group_names and cache_subnet_group_name:
        _subnet_group = __salt__['boto_elasticache.get_cache_subnet_group'](
            cache_subnet_group_name, region, key, keyid, profile
        )
        vpc_id = _subnet_group['vpc_id']
        if not security_group_ids:
            security_group_ids = []
        _security_group_ids = __salt__['boto_secgroup.convert_to_group_ids'](
            cache_security_group_names, vpc_id, region, key, keyid, profile
        )
        security_group_ids.extend(_security_group_ids)
        cache_security_group_names = None
    config = __salt__['boto_elasticache.get_config'](name, region, key, keyid,
                                                     profile)
    if config is None:
        msg = 'Failed to retrieve cache cluster info from AWS.'
        ret['comment'] = msg
        ret['result'] = None
        return ret
    elif not config:
        if __opts__['test']:
            msg = 'Cache cluster {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['boto_elasticache.create'](
            name=name, num_cache_nodes=num_cache_nodes,
            cache_node_type=cache_node_type, engine=engine,
            replication_group_id=replication_group_id,
            engine_version=engine_version,
            cache_parameter_group_name=cache_parameter_group_name,
            cache_subnet_group_name=cache_subnet_group_name,
            cache_security_group_names=cache_security_group_names,
            security_group_ids=security_group_ids,
            preferred_availability_zone=preferred_availability_zone,
            preferred_maintenance_window=preferred_maintenance_window,
            port=port, notification_topic_arn=notification_topic_arn,
            auto_minor_version_upgrade=auto_minor_version_upgrade,
            wait=wait, region=region, key=key, keyid=keyid, profile=profile)
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


def absent(
        name,
        wait=True,
        region=None,
        key=None,
        keyid=None,
        profile=None):
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

    is_present = __salt__['boto_elasticache.exists'](name, region, key, keyid,
                                                     profile)

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'Cache cluster {0} is set to be removed.'.format(
                name)
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
