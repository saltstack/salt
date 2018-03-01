# -*- coding: utf-8 -*-
'''
Execution module for Amazon Elasticache using boto3
===================================================

.. versionadded:: 2017.7.0

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
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time

# Import Salt libs
from salt.exceptions import SaltInvocationError, CommandExecutionError
import salt.utils.boto3
import salt.utils.compat
import salt.utils.versions


log = logging.getLogger(__name__)

# Import third party libs
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
    return salt.utils.versions.check_boto_reqs()


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


def _describe_resource(name=None, name_param=None, res_type=None, info_node=None, conn=None,
                            region=None, key=None, keyid=None, profile=None, **args):
    if conn is None:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        func = 'describe_'+res_type+'s'
        f = getattr(conn, func)
    except (AttributeError, KeyError) as e:
        raise SaltInvocationError("No function '{0}()' found: {1}".format(func, e.message))
    # Undocumented, but you can't pass 'Marker' if searching for a specific resource...
    args.update({name_param: name} if name else {'Marker': ''})
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        return _collect_results(f, info_node, args)
    except botocore.exceptions.ClientError as e:
        log.debug(e)
        return None


def _delete_resource(name, name_param, desc, res_type, wait=0, status_param=None,
                     status_gone='deleted', region=None, key=None, keyid=None, profile=None,
                     **args):
    '''
    Delete a generic Elasticache resource.
    '''
    try:
        wait = int(wait)
    except:
        raise SaltInvocationError("Bad value ('{0}') passed for 'wait' param - must be an "
                                  "int or boolean.".format(wait))
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if name_param in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided '%s: %s'",
            name, name_param, args[name_param]
        )
        name = args[name_param]
    else:
        args[name_param] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        func = 'delete_'+res_type
        f = getattr(conn, func)
        if wait:
            func = 'describe_'+res_type+'s'
            s = globals()[func]
    except (AttributeError, KeyError) as e:
        raise SaltInvocationError("No function '{0}()' found: {1}".format(func, e.message))
    try:

        f(**args)
        if not wait:
            log.info('%s %s deletion requested.', desc.title(), name)
            return True
        log.info('Waiting up to %s seconds for %s %s to be deleted.', wait, desc, name)
        orig_wait = wait
        while wait > 0:
            r = s(name=name, conn=conn)
            if not r or not len(r) or r[0].get(status_param) == status_gone:
                log.info('%s %s deleted.', desc.title(), name)
                return True
            sleep = wait if wait % 60 == wait else 60
            log.info('Sleeping %s seconds for %s %s to be deleted.',
                     sleep, desc, name)
            time.sleep(sleep)
            wait -= sleep
        log.error('%s %s not deleted after %s seconds!', desc.title(), name, orig_wait)

        return False
    except botocore.exceptions.ClientError as e:
        log.error('Failed to delete %s %s: %s', desc, name, e)
        return False


def _create_resource(name, name_param=None, desc=None, res_type=None, wait=0, status_param=None,
                     status_good='available', region=None, key=None, keyid=None, profile=None,
                     **args):
    try:
        wait = int(wait)
    except:
        raise SaltInvocationError("Bad value ('{0}') passed for 'wait' param - must be an "
                                  "int or boolean.".format(wait))
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if name_param in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided '%s: %s'",
            name, name_param, args[name_param]
        )
        name = args[name_param]
    else:
        args[name_param] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        func = 'create_'+res_type
        f = getattr(conn, func)
        if wait:
            func = 'describe_'+res_type+'s'
            s = globals()[func]
    except (AttributeError, KeyError) as e:
        raise SaltInvocationError("No function '{0}()' found: {1}".format(func, e.message))
    try:
        f(**args)
        if not wait:
            log.info('%s %s created.', desc.title(), name)
            return True
        log.info('Waiting up to %s seconds for %s %s to be become available.',
                 wait, desc, name)
        orig_wait = wait
        while wait > 0:
            r = s(name=name, conn=conn)
            if r and r[0].get(status_param) == status_good:
                log.info('%s %s created and available.', desc.title(), name)
                return True
            sleep = wait if wait % 60 == wait else 60
            log.info('Sleeping %s seconds for %s %s to become available.',
                     sleep, desc, name)
            time.sleep(sleep)
            wait -= sleep
        log.error('%s %s not available after %s seconds!',
                  desc.title(), name, orig_wait)
        return False
    except botocore.exceptions.ClientError as e:
        msg = 'Failed to create {0} {1}: {2}'.format(desc, name, e)
        log.error(msg)
        return False


def _modify_resource(name, name_param=None, desc=None, res_type=None, wait=0, status_param=None,
                     status_good='available', region=None, key=None, keyid=None, profile=None,
                     **args):
    try:
        wait = int(wait)
    except:
        raise SaltInvocationError("Bad value ('{0}') passed for 'wait' param - must be an "
                                  "int or boolean.".format(wait))
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if name_param in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided '%s: %s'",
            name, name_param, args[name_param]
        )
        name = args[name_param]
    else:
        args[name_param] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        func = 'modify_'+res_type
        f = getattr(conn, func)
        if wait:
            func = 'describe_'+res_type+'s'
            s = globals()[func]
    except (AttributeError, KeyError) as e:
        raise SaltInvocationError("No function '{0}()' found: {1}".format(func, e.message))
    try:
        f(**args)
        if not wait:
            log.info('%s %s modification requested.', desc.title(), name)
            return True
        log.info('Waiting up to %s seconds for %s %s to be become available.',
                 wait, desc, name)
        orig_wait = wait
        while wait > 0:
            r = s(name=name, conn=conn)
            if r and r[0].get(status_param) == status_good:
                log.info('%s %s modified and available.', desc.title(), name)
                return True
            sleep = wait if wait % 60 == wait else 60
            log.info('Sleeping %s seconds for %s %s to become available.',
                     sleep, desc, name)
            time.sleep(sleep)
            wait -= sleep
        log.error('%s %s not available after %s seconds!',
                  desc.title(), name, orig_wait)
        return False
    except botocore.exceptions.ClientError as e:
        msg = 'Failed to modify {0} {1}: {2}'.format(desc, name, e)
        log.error(msg)
        return False


def describe_cache_clusters(name=None, conn=None, region=None, key=None,
                            keyid=None, profile=None, **args):
    '''
    Return details about all (or just one) Elasticache cache clusters.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.describe_cache_clusters
        salt myminion boto3_elasticache.describe_cache_clusters myelasticache
    '''
    return _describe_resource(name=name, name_param='CacheClusterId', res_type='cache_cluster',
                              info_node='CacheClusters', conn=conn, region=region, key=key,
                              keyid=keyid, profile=profile, **args)


def cache_cluster_exists(name, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a cache cluster exists.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.cache_cluster_exists myelasticache
    '''
    return bool(describe_cache_clusters(name=name, conn=conn, region=region, key=key, keyid=keyid, profile=profile))


def create_cache_cluster(name, wait=600, security_groups=None,
                         region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create a cache cluster.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_cache_cluster name=myCacheCluster \
                                                             Engine=redis \
                                                             CacheNodeType=cache.t2.micro \
                                                             NumCacheNodes=1 \
                                                             SecurityGroupIds='[sg-11223344]' \
                                                             CacheSubnetGroupName=myCacheSubnetGroup
    '''
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _create_resource(name, name_param='CacheClusterId', desc='cache cluster',
                            res_type='cache_cluster', wait=wait, status_param='CacheClusterStatus',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def modify_cache_cluster(name, wait=600, security_groups=None, region=None,
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
            practice this is not particularly useful and should probably be avoided.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_cache_cluster name=myCacheCluster \
                                                             NotificationTopicStatus=inactive
    '''
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _modify_resource(name, name_param='CacheClusterId', desc='cache cluster',
                            res_type='cache_cluster', wait=wait, status_param='CacheClusterStatus',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def delete_cache_cluster(name, wait=600, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete a cache cluster.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.delete myelasticache
    '''
    return _delete_resource(name, name_param='CacheClusterId', desc='cache cluster',
                            res_type='cache_cluster', wait=wait,
                            status_param='CacheClusterStatus',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def describe_replication_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache replication groups.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.describe_replication_groups
        salt myminion boto3_elasticache.describe_replication_groups myelasticache
    '''
    return _describe_resource(name=name, name_param='ReplicationGroupId',
                              res_type='replication_group', info_node='ReplicationGroups',
                              conn=conn, region=region, key=key, keyid=keyid, profile=profile)


def replication_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a replication group exists.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.replication_group_exists myelasticache
    '''
    return bool(describe_replication_groups(name=name, region=region, key=key, keyid=keyid,
                profile=profile))


def create_replication_group(name, wait=600, security_groups=None, region=None, key=None, keyid=None,
                             profile=None, **args):
    '''
    Create a replication group.
    Params are extensive and variable - see
    http://boto3.readthedocs.io/en/latest/reference/services/elasticache.html?#ElastiCache.Client.create_replication_group
    for in-depth usage documentation.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_replication_group \
                                                  name=myelasticache \
                                                  ReplicationGroupDescription=description
    '''
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _create_resource(name, name_param='ReplicationGroupId', desc='replication group',
                            res_type='replication_group', wait=wait, status_param='Status',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def modify_replication_group(name, wait=600, security_groups=None, region=None, key=None, keyid=None,
                             profile=None, **args):
    '''
    Modify a replication group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.modify_replication_group \
                                                  name=myelasticache \
                                                  ReplicationGroupDescription=newDescription
    '''
    if security_groups:
        if not isinstance(security_groups, list):
            security_groups = [security_groups]
        sgs = __salt__['boto_secgroup.convert_to_group_ids'](groups=security_groups, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if 'SecurityGroupIds' not in args:
            args['SecurityGroupIds'] = []
        args['SecurityGroupIds'] += sgs
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _modify_resource(name, name_param='ReplicationGroupId', desc='replication group',
                            res_type='replication_group', wait=wait, status_param='Status',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def delete_replication_group(name, wait=600, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete an ElastiCache replication group, optionally taking a snapshot first.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.delete_replication_group my-replication-group
    '''
    return _delete_resource(name, name_param='ReplicationGroupId', desc='replication group',
                            res_type='replication_group', wait=wait, status_param='Status',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def describe_cache_subnet_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache replication groups.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.describe_cache_subnet_groups region=us-east-1
    '''
    return _describe_resource(name=name, name_param='CacheSubnetGroupName',
                              res_type='cache_subnet_group', info_node='CacheSubnetGroups',
                              conn=conn, region=region, key=key, keyid=keyid, profile=profile)


def cache_subnet_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ElastiCache subnet group exists.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.cache_subnet_group_exists my-subnet-group
    '''
    return bool(describe_cache_subnet_groups(name=name, region=region, key=key, keyid=keyid, profile=profile))


def list_cache_subnet_groups(region=None, key=None, keyid=None, profile=None):
    '''
    Return a list of all cache subnet group names

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.list_cache_subnet_groups region=us-east-1
    '''
    return [g['CacheSubnetGroupName'] for g in
            describe_cache_subnet_groups(None, region, key, keyid, profile)]


def create_cache_subnet_group(name, subnets=None, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create an ElastiCache subnet group

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_cache_subnet_group name=my-subnet-group \
                                              CacheSubnetGroupDescription="description" \
                                              subnets='[myVPCSubnet1,myVPCSubnet2]'
    '''
    if subnets:
        if 'SubnetIds' not in args:
            args['SubnetIds'] = []
        if not isinstance(subnets, list):
            subnets = [subnets]
        for subnet in subnets:
            if subnet.startswith('subnet-'):
                # Moderately safe assumption... :)  Will be caught further down if incorrect.
                args['SubnetIds'] += [subnet]
                continue
            sn = __salt__['boto_vpc.describe_subnets'](subnet_names=subnet, region=region, key=key,
                                                       keyid=keyid, profile=profile).get('subnets')
            if not sn:
                raise SaltInvocationError(
                    'Could not resolve Subnet Name {0} to an ID.'.format(subnet))
            if len(sn) == 1:
                args['SubnetIds'] += [sn[0]['id']]
            elif len(sn) > 1:
                raise CommandExecutionError(
                    'Subnet Name {0} returned more than one ID.'.format(subnet))
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _create_resource(name, name_param='CacheSubnetGroupName', desc='cache subnet group',
                            res_type='cache_subnet_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def modify_cache_subnet_group(name, subnets=None, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Modify an ElastiCache subnet group

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.modify_cache_subnet_group \
                                              name=my-subnet-group \
                                              subnets='[myVPCSubnet3]'
    '''
    if subnets:
        if 'SubnetIds' not in args:
            args['SubnetIds'] = []
        if not isinstance(subnets, list):
            subnets = [subnets]
        for subnet in subnets:
            sn = __salt__['boto_vpc.describe_subnets'](subnet_names=subnet,
                                                       region=region, key=key, keyid=keyid,
                                                       profile=profile).get('subnets')
            if len(sn) == 1:
                args['SubnetIds'] += [sn[0]['id']]
            elif len(sn) > 1:
                raise CommandExecutionError(
                    'Subnet Name {0} returned more than one ID.'.format(subnet))
            elif subnet.startswith('subnet-'):
                # Moderately safe assumption... :)  Will be caught later if incorrect.
                args['SubnetIds'] += [subnet]
            else:
                raise SaltInvocationError(
                    'Could not resolve Subnet Name {0} to an ID.'.format(subnet))
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    return _modify_resource(name, name_param='CacheSubnetGroupName', desc='cache subnet group',
                            res_type='cache_subnet_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def delete_cache_subnet_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete an ElastiCache subnet group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.delete_subnet_group my-subnet-group region=us-east-1
    '''
    return _delete_resource(name, name_param='CacheSubnetGroupName',
                            desc='cache subnet group', res_type='cache_subnet_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def describe_cache_security_groups(name=None, conn=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return details about all (or just one) Elasticache cache clusters.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.describe_cache_security_groups
        salt myminion boto3_elasticache.describe_cache_security_groups mycachesecgrp
    '''
    return _describe_resource(name=name, name_param='CacheSecurityGroupName',
                              res_type='cache_security_group',
                              info_node='CacheSecurityGroups', conn=conn, region=region, key=key,
                              keyid=keyid, profile=profile)


def cache_security_group_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an ElastiCache security group exists.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.cache_security_group_exists mysecuritygroup
    '''
    return bool(describe_cache_security_groups(name=name, region=region, key=key, keyid=keyid, profile=profile))


def create_cache_security_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create a cache security group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_cache_security_group mycachesecgrp Description='My Cache Security Group'
    '''
    return _create_resource(name, name_param='CacheSecurityGroupName', desc='cache security group',
                            res_type='cache_security_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def delete_cache_security_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete a cache security group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.delete_cache_security_group myelasticachesg
    '''
    return _delete_resource(name, name_param='CacheSecurityGroupName',
                            desc='cache security group', res_type='cache_security_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def authorize_cache_security_group_ingress(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Authorize network ingress from an ec2 security group to a cache security group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.authorize_cache_security_group_ingress \
                                        mycachesecgrp \
                                        EC2SecurityGroupName=someEC2sg \
                                        EC2SecurityGroupOwnerId=SOMEOWNERID
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'CacheSecurityGroupName: %s'",
            name, args['CacheSecurityGroupName']
        )
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.authorize_cache_security_group_ingress(**args)
        log.info('Authorized %s to cache security group %s.',
                 args['EC2SecurityGroupName'], name)
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to update security group %s: %s', name, e)
        return False


def revoke_cache_security_group_ingress(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Revoke network ingress from an ec2 security group to a cache security
    group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.revoke_cache_security_group_ingress \
                                        mycachesecgrp \
                                        EC2SecurityGroupName=someEC2sg \
                                        EC2SecurityGroupOwnerId=SOMEOWNERID
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'CacheSecurityGroupName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'CacheSecurityGroupName: %s'",
            name, args['CacheSecurityGroupName']
        )
        name = args['CacheSecurityGroupName']
    else:
        args['CacheSubnetGroupName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.revoke_cache_security_group_ingress(**args)
        log.info('Revoked %s from cache security group %s.',
                 args['EC2SecurityGroupName'], name)
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to update security group %s: %s', name, e)
        return False


def list_tags_for_resource(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    List tags on an Elasticache resource.

    Note that this function is essentially useless as it requires a full AWS ARN for the
    resource being operated on, but there is no provided API or programmatic way to find
    the ARN for a given object from its name or ID alone.  It requires specific knowledge
    about the account number, AWS partition, and other magic details to generate.

    If you happen to have those handy, feel free to utilize this however...

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.list_tags_for_resource \
                name'=arn:aws:elasticache:us-west-2:0123456789:snapshot:mySnapshot'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'ResourceName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'ResourceName: %s'", name, args['ResourceName']
        )
        name = args['ResourceName']
    else:
        args['ResourceName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        r = conn.list_tags_for_resource(**args)
        if r and 'Taglist' in r:
            return r['TagList']
        return []
    except botocore.exceptions.ClientError as e:
        log.error('Failed to list tags for resource %s: %s', name, e)
        return []


def add_tags_to_resource(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Add tags to an Elasticache resource.

    Note that this function is essentially useless as it requires a full AWS ARN for the
    resource being operated on, but there is no provided API or programmatic way to find
    the ARN for a given object from its name or ID alone.  It requires specific knowledge
    about the account number, AWS partition, and other magic details to generate.

    If you happen to have those at hand though, feel free to utilize this function...

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.add_tags_to_resource \
                name'=arn:aws:elasticache:us-west-2:0123456789:snapshot:mySnapshot' \
                Tags="[{'Key': 'TeamOwner', 'Value': 'infrastructure'}]"
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'ResourceName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'ResourceName: %s'", name, args['ResourceName']
        )
        name = args['ResourceName']
    else:
        args['ResourceName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.add_tags_to_resource(**args)
        log.info('Added tags %s to %s.', args['Tags'], name)
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to add tags to %s: %s', name, e)
        return False


def remove_tags_from_resource(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Remove tags from an Elasticache resource.

    Note that this function is essentially useless as it requires a full AWS ARN for the
    resource being operated on, but there is no provided API or programmatic way to find
    the ARN for a given object from its name or ID alone.  It requires specific knowledge
    about the account number, AWS partition, and other magic details to generate.

    If you happen to have those at hand though, feel free to utilize this function...

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.remove_tags_from_resource \
                name'=arn:aws:elasticache:us-west-2:0123456789:snapshot:mySnapshot' \
                TagKeys="['TeamOwner']"
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'ResourceName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'ResourceName: %s'", name, args['ResourceName']
        )
        name = args['ResourceName']
    else:
        args['ResourceName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.remove_tags_from_resource(**args)
        log.info('Added tags %s to %s.', args['Tags'], name)
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to add tags to %s: %s', name, e)
        return False


def copy_snapshot(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Make a copy of an existing snapshot.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.copy_snapshot name=mySnapshot \
                                                      TargetSnapshotName=copyOfMySnapshot
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if 'SourceSnapshotName' in args:
        log.info(
            "'name: %s' param being overridden by explicitly provided "
            "'SourceSnapshotName: %s'", name, args['SourceSnapshotName']
        )
        name = args['SourceSnapshotName']
    else:
        args['SourceSnapshotName'] = name
    args = dict([(k, v) for k, v in args.items() if not k.startswith('_')])
    try:
        conn.copy_snapshot(**args)
        log.info('Snapshot %s copied to %s.', name, args['TargetSnapshotName'])
        return True
    except botocore.exceptions.ClientError as e:
        log.error('Failed to copy snapshot %s: %s', name, e)
        return False


def describe_cache_parameter_groups(name=None, conn=None, region=None, key=None, keyid=None,
                                    profile=None):
    '''
    Return details about all (or just one) Elasticache cache clusters.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.describe_cache_parameter_groups
        salt myminion boto3_elasticache.describe_cache_parameter_groups myParameterGroup
    '''
    return _describe_resource(name=name, name_param='CacheParameterGroupName',
                              res_type='cache_parameter_group', info_node='CacheParameterGroups',
                              conn=conn, region=region, key=key, keyid=keyid, profile=profile)


def create_cache_parameter_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Create a cache parameter group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.create_cache_parameter_group \
                name=myParamGroup \
                CacheParameterGroupFamily=redis2.8 \
                Description="My Parameter Group"
    '''
    return _create_resource(name, name_param='CacheParameterGroupName',
                            desc='cache parameter group', res_type='cache_parameter_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)


def delete_cache_parameter_group(name, region=None, key=None, keyid=None, profile=None, **args):
    '''
    Delete a cache parameter group.

    Example:

    .. code-block:: bash

        salt myminion boto3_elasticache.delete_cache_parameter_group myParamGroup
    '''
    return _delete_resource(name, name_param='CacheParameterGroupName',
                            desc='cache parameter group', res_type='cache_parameter_group',
                            region=region, key=key, keyid=keyid, profile=profile, **args)
