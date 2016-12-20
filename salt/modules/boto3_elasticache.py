# -*- coding: utf-8 -*-
'''
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

:depends: boto3
'''

# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import socket
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module
import time
import random

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
from salt.exceptions import SaltInvocationError, CommandExecutionError
from salt.ext.six.moves import range  # pylint: disable=import-error

# from salt.utils import exactly_one
# TODO: Uncomment this and s/_exactly_one/exactly_one/
# See note in utils.boto
PROVISIONING = 'provisioning'
PENDING_ACCEPTANCE = 'pending-acceptance'
ACTIVE = 'active'

log = logging.getLogger(__name__)

# Import third party libs
import salt.ext.six as six
try:
    #pylint: disable=unused-import
    import botocore
    import boto3
    #pylint: enable=unused-import
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    if not HAS_BOTO3:
        return (False, 'The boto3_elasticache module could not be loaded: boto3 libraries not found')
### Version reqs (if any) currently undetermined
#    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
#        return (False, 'The boto3_elasticache module could not be loaded: boto3 library version 1.2.6 is required')
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'elasticache',
                  get_conn_funcname='_get_conn',
                  cache_id_funcname='_cache_id',
                  exactly_one_funcname=None)


def _collect_results(func, item, args, marker='Marker'):
    ret = []
    Marker = args[marker] if marker in args else ''
    while Marker is not None:
        r = func(**args)
        ret += r.get(item)
        Marker = r.get(marker)
        args.update({marker: Marker})
    return ret


def describe_cache_clusters(name=None, ShowCacheNodeInfo=False, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache cache clusters.

    CLI example::

        salt myminion boto3_elasticache.describe_cache_clusters
        salt myminion boto3_elasticache.describe_cache_clusters myelasticache
    '''
    if conn == None:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        args = {'CacheClusterId': name} if name else {'Marker': ''}
        args.update({'ShowCacheNodeInfo': ShowCacheNodeInfo}) if ShowCacheNodeInfo else None
        return _collect_results(conn.describe_cache_clusters, 'CacheClusters', args)
    except botocore.exceptions.ClientError as e:
        log.debug(e)
        return None


def cache_cluster_exists(name, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a cache cluster exists.

    CLI example::

        salt myminion boto3_elasticache.cache_cluster_exists myelasticache
    '''
    return bool(describe_cache_clusters(name=name, conn=conn, region=region, key=key, keyid=keyid, profile=profile))


def create_cache_cluster(name, wait=True, security_groups=None,
                         region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create a cache cluster.

    CLI example::

        salt myminion boto3_elasticache.create_cache_cluster name=myCacheCluster \
                                                             Engine=redis \
                                                             CacheNodeType=cache.t2.micro \
                                                             NumCacheNodes=1 \
                                                             SecurityGroupIds='[sg-11223344]' \
                                                             CacheSubnetGroupName=myCacheSubnetGroup
    '''
    if wait is True:
        wait = (10, 6, 10)
    try:
        o, i, s = wait; o = int(o); i=int(i); s = int(s)
    except:
        log.warning("Invalid value for 'wait' param - must be a bool or tuple of three integers.")
        wait = False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheClusterId' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheClusterId: {1}'".format(name, args['CacheClusterId']))
        name = args['CacheClusterId']
    else:
        args['CacheClusterId'] = name
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.create_cache_cluster(**args)
        if not wait:
            log.info('Cache cluster {0} created.'.format(name))
            return True
        for outer in range(o):
            for inner in range(i):
                r = describe_cache_clusters(name=name, conn=conn)
                if r and r[0].get('CacheClusterStatus') == 'available':
                    log.info('Cache cluster {0} created and available.'.format(name))
                    return True
                time.sleep(s)
            log.info('Waiting up to {0} seconds for cache cluster {1} to become '
                     'available.'.format(o * i * s, name))
        log.error('Cache cluster {0} not available after {1} seconds!'.format(name, o * i * s))
        return False
    except botocore.exceptions.ClientError as e:
        log.error('Failed to create cache cluster {0}: {1}'.format(name, e))
        return False


def modify_cache_cluster(name, wait=True, security_groups=None, region=None,
                         key=None, keyid=None, profile=None, **args):
    '''
    Update a cache cluster in place.

    Notes:  {ApplyImmediately: False} is pretty danged silly in the context of salt.
            You can pass it, but for fairly obvious reasons the results over multiple
            runs will be undefined and probably contrary to your desired state.
            Reducing the number of nodes requires an EXPLICIT CacheNodeIdsToRemove be
            passed, which until a reasonable heuristic for programmatically deciding
            which nodes to remove has been established, MUST be decided and populated
            intentionally before a state call, and removed again before the next.  In
            practice this is not particularly useful and should generally be avoided.

    CacheClusterId
        Cannot be changed.  Required param as it tells AWS what we'll be modifying.

    NumCacheNodes
        The number of cache nodes that the cache cluster should have. If the value for
        NumCacheNodes is greater than the sum of the number of current cache nodes and
        the number of cache nodes pending creation (which may be zero), more nodes are
        added. If the value is less than the number of existing cache nodes, nodes are
        removed. If the value is equal to the number of current cache nodes, any
        pending add or remove requests are canceled.  If you are removing cache nodes,
        you MUST use the CacheNodeIdsToRemove parameter to provide the IDs of the
        specific cache nodes to remove.  For clusters running Redis, this value MUST be 1.
        For clusters running Memcached, this value must be between 1 and 20.

    CacheNodeIdsToRemove
        A list of cache node IDs to be removed. A node ID is a numeric identifier (0001,
        0002, etc.). This parameter is only valid when NumCacheNodes is less than the
        existing number of cache nodes. The number of cache node IDs supplied in this
        parameter must match the difference between the existing number of cache nodes in
        the cluster or pending cache nodes, whichever is greater, and the value of
        NumCacheNodes in the request.  For example: If you have 3 active cache nodes,
        7 pending cache nodes, and the number of cache nodes in this ModifyCacheCluser
        call is 5, you must list 2 (7 - 5) cache node IDs to remove.

    AZMode
        Specifies whether the new nodes in this Memcached cache cluster are all created
        in a single Availability Zone or created across multiple Availability Zones.
        Valid values:  single-az | cross-az
        Notes:  This option is ONLY supported for Memcached cache clusters.
                You cannot specify single-az if the Memcached cache cluster already has
                cache nodes in different Availability Zones. If cross-az is specified,
                existing Memcached nodes remain in their current Availability Zone.
                Only newly created nodes are located in different Availability Zones.
                For instructions on how to move existing Memcached nodes to different
                Availability Zones, see the AWS docs.

    NewAvailabilityZones
        The list of Availability Zones where the new Memcached cache nodes are created.
        This parameter is only valid when NumCacheNodes in the request is greater than
        the sum of the number of active cache nodes and the number of cache nodes pending
        creation (which may be zero). The number of Availability Zones supplied in this
        list must match the cache nodes being added in this request.
        Note:  This option is ONLY supported on Memcached clusters.

    CacheSecurityGroupNames
        A list of cache security group names to authorize on this cache cluster.  This
        change is asynchronously applied as soon as possible.  You can use this parameter
        only with clusters that are created outside of a VPC.
        Constraints:  Must contain no more than 255 alphanumeric characters.
                      Must not be "Default".

    SecurityGroupIds
        Specifies the VPC Security Groups associated with the cache cluster.  This
        parameter can ONLY be used with clusters that are created in a VPC.

    PreferredMaintenanceWindow
        Desired maintenance window, as described for create_cache_cluster() above.

    NotificationTopicArn
        The Amazon Resource Name (ARN) of the Amazon SNS topic to which notifications
        are sent.
        Note:  The Amazon SNS topic owner must be same as the cache cluster owner.

    CacheParameterGroupName
        The name of the cache parameter group to apply to this cache cluster.  This
        change is asynchronously applied as soon as possible when {ApplyImmediately:
        True} is set for this request.

    NotificationTopicStatus
        The status of the Amazon SNS notification topic. Notifications are sent only
        if the status is active.
        Valid values:  active | inactive

    ApplyImmediately
        If True, this parameter causes the modifications in this request and any
        pending modifications to be applied, asynchronously and as soon as possible,
        regardless of the PreferredMaintenanceWindow setting for the cache cluster.
        If False, changes to the cache cluster are applied on the next maintenance
        reboot, or the next failure reboot, whichever occurs first.
        Note:  If you perform a ModifyCacheCluster before a pending modification is
               applied, the pending modification is replaced by the newer modification.
        Default:  False

    EngineVersion
        The upgraded version of the cache engine to be run on the cache nodes.
        Note:  You can upgrade to a newer engine version but you cannot downgrade to
        an earlier engine version. If you want to use an earlier engine version, you
        must delete the existing cache cluster and create it anew with the earlier
        engine version.

    AutoMinorVersionUpgrade
        Per AWS, this parameter is currently disabled.

    SnapshotRetentionLimit
        The number of days for which ElastiCache retains automatic cache cluster
        snapshots before deleting them.
        Note: If the value of SnapshotRetentionLimit is set to zero (0), backups
              are turned off.

    SnapshotWindow
        The daily time range (in UTC) during which ElastiCache begins taking a
        daily snapshot of your cache cluster, as described above for
        create_cache_cluster().

    CacheNodeType
        A valid cache node type (as described for create_cache_cluster() above)
        that you want to scale this cache cluster to.
    '''
    if wait is True:
        wait = (10, 6, 10)
    try:
        o, i, s = wait; o = int(o); i=int(i); s = int(s)
    except:
        log.warning("Invalid value for 'wait' param - must be a bool or tuple of three integers.")
        wait = False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheClusterId' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheClusterId: {1}'".format(name, args['CacheClusterId']))
        name = args['CacheClusterId']
    else:
        args['CacheClusterId'] = name
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.modify_cache_cluster(**args)
        if not wait:
            log.info('Cache cluster {0} being modified.'.format(name))
            return True
        for outer in range(o):
            for inner in range(i):
                r = describe_cache_clusters(name=name, conn=conn)
                if r and r[0].get('CacheClusterStatus') == 'available':
                    log.info('Cache cluster {0} modified and available.'.format(name))
                    return True
                time.sleep(s)
            log.info('Waiting up to {0} seconds for cache cluster {1} to become '
                     'available.'.format(o * i * s, name))
        log.error('Cache cluster {0} not available after {1} seconds!'.format(name, o * i * s))
        return False
    except botocore.exceptions.ClientError as e:
        log.error('Failed to modify cache cluster {0}: {1}'.format(name, e))
        return False


def delete_cache_cluster(name, wait=True, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete a cache cluster.

    CLI example::

        salt myminion boto3_elasticache.delete myelasticache
    '''
    if wait is True:
        wait = (10, 6, 10)
    try:
        o, i, s = wait; o = int(o); i=int(i); s = int(s)
    except:
        log.warning("Invalid value for 'wait' param - must be a bool or tuple of three integers.")
        wait = False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheClusterId' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheClusterId: {1}'".format(name, args['CacheClusterId']))
        name = args['CacheClusterId']
    else:
        args['CacheClusterId'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.delete_cache_cluster(**args)
        if not wait:
            log.info('Cache cluster {0} deleting.'.format(name))
            return True
        for outer in range(o):
            for inner in range(i):
                r = describe_cache_clusters(name=name, conn=conn)
                if not r or r[0].get('CacheClusterStatus') == 'deleted':
                    log.info('Cache cluster {0} deleted.'.format(name))
                    return True
                time.sleep(s)
            log.info('Waiting up to {0} seconds for cache cluster {1} to be '
                     'deleted.'.format(o * i * s, name))
        log.error('Cache cluster {0} not deleted after {1} seconds!'.format(name, o * i * s))
        return False
    except botocore.exceptions.ClientError as e:
        log.error('Failed to delete cache cluster {0}: {1}'.format(name, e))
        return False


def describe_replication_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache replication groups.

    CLI example::

        salt myminion boto3_elasticache.describe_replication_groups
        salt myminion boto3_elasticache.describe_replication_groups myelasticache
    '''
    if conn == None:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        args = {'ReplicationGroupId': name} if name else {'Marker': ''}
        return _collect_results(conn.describe_replication_groups, 'ReplicationGroups', args)
    except botocore.exceptions.ClientError as e:
        log.debug(e)
        return False


def replication_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a replication group exists.

    CLI example::

        salt myminion boto3_elasticache.replication_group_exists myelasticache
    '''
    return bool(describe_replication_groups(name=name, region=region, key=key, keyid=keyid, profile=profile))


def create_replication_group(name, wait=True, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create replication group.
    Params are extensive and variable - see
    http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html?#ElastiCache.Client.create_replication_group
    for in-depth usage documentation.

    CLI example::

        salt myminion boto3_elasticache.create_replication_group name=myelasticache ReplicationGroupDescription=description
    '''
    if wait is True:
        wait = (10, 6, 10)
    try:
        o, i, s = wait; o = int(o); i=int(i); s = int(s)
    except:
        log.warning("Invalid value for 'wait' param - must be a bool or tuple of three integers.")
        wait = False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'ReplicationGroupId' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'ReplicationGroupId: {1}'".format(name, args['ReplicationGroupId']))
        name = args['ReplicationGroupId']
    else:
        args['ReplicationGroupId'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.create_replication_group(**args)
        if not wait:
            log.info('Replication group {0} created.'.format(name))
            return True
        for outer in range(o):
            for inner in range(i):
                r = describe_replication_groups(name, conn)
                if r and r[0].get('Status') == 'available':
                    log.info('Replication group {0} created and available.'.format(name))
                    return True
                time.sleep(s)
            log.info('Waiting up to {0} seconds for replication group {1} to become '
                     'available.'.format(o * i * s, name))
        log.error('Replication group {0} not available after {1} seconds!'.format(name, o * i * s))
        return False
    except botocore.exceptions.ClientError as e:
        msg = 'Failed to create replication group {0}: {1}'.format(name, e)
        log.error(msg)
        return False


def delete_replication_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete an ElastiCache replication group, optionally taking a snapshot first.

    CLI example::

        salt myminion boto3_elasticache.delete_replication_group my-replication-group
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'ReplicationGroupId' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'ReplicationGroupId: {1}'".format(name, args['ReplicationGroupId']))
        name = args['ReplicationGroupId']
    else:
        args['ReplicationGroupId'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.delete_replication_group(**args)
        log.info('Replication group {0} deleted.'.format(name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to delete Replication group {0}: {1}'.format(name, e))
        return False


def describe_cache_subnet_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache replication groups.

    CLI example::

        salt myminion boto3_elasticache.describe_cache_subnet_groups region=us-east-1
    '''
    if conn == None:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        args = {'CacheSubnetGroupName': name} if name else {'Marker': ''}
        return _collect_results(conn.describe_cache_subnet_groups, 'CacheSubnetGroups', args)
    except botocore.exceptions.ClientError as e:
        log.debug(e)
        return None


def cache_subnet_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ElastiCache subnet group exists.

    CLI example::

        salt myminion boto3_elasticache.cache_subnet_group_exists my-subnet-group
    '''
    return bool(describe_cache_subnet_groups(name=name, region=region, key=key, keyid=keyid, profile=profile))


def list_cache_subnet_groups(region=None, key=None, keyid=None, profile=None):
    '''
    Return a list of all cache subnet group names

    CLI example::

        salt myminion boto3_elasticache.list_cache_subnet_groups region=us-east-1
    '''
    return [g['CacheSubnetGroupName'] for g in
            describe_cache_subnet_groups(None, region, key, keyid, profile)]


def create_cache_subnet_group(name, subnets=None, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create an ElastiCache subnet group

    CLI example to create an ElastiCache subnet group::

        salt myminion boto3_elasticache.create_cache_subnet_group my-subnet-group \ XXX
            "group description" subnet_ids='[subnet-12345678, subnet-87654321]' \
            region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSubnetGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSubnetGroupName: {1}'".format(name, args['CacheSubnetGroupName']))
        name = args['CacheSubnetGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    if subnets:
        if 'SubnetIds' not in args:
            args['SubnetIds'] = []
        if not isinstance(subnets, list):
            subnets = [subnets]
        for subnet in subnets:
            sn = __salt__['boto_vpc.describe_subnets'](subnet_names=security_groups,
                                                       region=region, key=key, keyid=keyid,
                                                       profile=profile).get('subnets')
            if len(sn) == 1:
                args['SubnetIds'] += [sn[0]['id']]
            elif len(sn) > 1:
                raise CommandExecutionError('Subnet Name {0} returned more than one '
                                          'ID.'.format(subnet))
            elif subnet.startswith('subnet-'):
                # Moderately safe assumption... :)  Will be caught later if incorrect.
                args['SubnetIds'] += [subnet]
            else:
                raise SaltInvocationError('Could not resolve Subnet Name {0} to an '
                                          'ID.'.format(subnet))
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.create_cache_subnet_group(**args)
        log.info('Cache subnet group {0} created.'.format(name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to create cache subnet group {0}: {1}'.format(name, e))
        return False


def delete_cache_subnet_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete an ElastiCache subnet group.

    CLI example::

        salt myminion boto3_elasticache.delete_subnet_group my-subnet-group region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSubnetGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSubnetGroupName: {1}'".format(name, args['CacheSubnetGroupName']))
        name = args['CacheSubnetGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.delete_cache_subnet_group(**args)
        log.info('Cache subnet group {0} deleted.'.format(name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to delete cache subnet group {0}: {1}'.format(name, e))
        return False


def describe_cache_security_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache cache clusters.

    CLI example::

        salt myminion boto3_elasticache.describe_cache_security_groups
        salt myminion boto3_elasticache.describe_cache_security_groups mycachesecgrp
    '''
    if conn == None:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        args = {'CacheSecurityGroupName': name} if name else {'Marker': ''}
        return _collect_results(conn.describe_cache_security_groups, 'CacheSecurityGroups', args)
    except botocore.exceptions.ClientError as e:
        log.debug(e)
        return None


def cache_security_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ElastiCache security group exists.

    CLI example::

        salt myminion boto3_elasticache.cache_security_group_exists mysecuritygroup
    '''
    return bool(describe_cache_security_groups(name=name, region=region, key=key, keyid=keyid, profile=profile))


def create_cache_security_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create a cache security group.

    CLI example::

        salt myminion boto3_elasticache.create_cache_security_group mycachesecgrp Description='My Cache Security Group'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSecurityGroupName: {1}'".format(name, args['CacheSecurityGroupName']))
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSecurityGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.create_cache_security_group(**args)
        log.info('Created cache security group {0}.'.format(name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to create cache security group {0}: {1}'.format(name, e))
        return False


def delete_cache_security_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete a cache security group.

    CLI example::

        salt myminion boto3_elasticache.delete_cache_security_group myelasticachesg
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSecurityGroupName: {1}'".format(name, args['CacheSecurityGroupName']))
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.delete_cache_security_group(**args)
        log.info('Cache security group {0} deleted.'.format(name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to delete cache security group {0}: {1}'.format(name, e))
        return False


def authorize_cache_security_group_ingress(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Authorize network ingress from an ec2 security group to a cache security group.

    CLI example::

        salt myminion boto3_elasticache.authorize_cache_security_group_ingress \
                                        mycachesecgrp \
                                        EC2SecurityGroupName=someEC2sg \
                                        EC2SecurityGroupOwnerId=SOMEOWNERID
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSecurityGroupName: {1}'".format(name, args['CacheSecurityGroupName']))
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.authorize_cache_security_group_ingress(**args)
        log.info('Authorized {0} to cache security group {1}.'.format(args['EC2SecurityGroupName'], name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to update security group {0}: {1}'.format(name, e))
        return False


def revoke_cache_security_group_ingress(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Revoke network ingress from an ec2 security group to a cache security
    group.

    CLI example::

        salt myminion boto3_elasticache.revoke_cache_security_group_ingress \
                                        mycachesecgrp \
                                        EC2SecurityGroupName=someEC2sg \
                                        EC2SecurityGroupOwnerId=SOMEOWNERID
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info("'name: {0}' param being overridden by explicitly provided "
                 "'CacheSecurityGroupName: {1}'".format(name, args['CacheSecurityGroupName']))
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.revoke_cache_security_group_ingress(**args)
        log.info('Revoked {0} from cache security group {1}.'.format(args['EC2SecurityGroupName'], name))
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to update security group {0}: {1}'.format(name, e))
        return False
