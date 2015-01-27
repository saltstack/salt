# -*- coding: utf-8 -*-
'''
Connection module for Amazon Elasticache

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit elasticache credentials but can
    also utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        elasticache.keyid: GKTADJGHEIQSXMKKRBJ08H
        elasticache.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        elasticache.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
from __future__ import absolute_import

# Import Python libs
import logging
import time
import salt.ext.six as six

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.elasticache
    import boto.utils
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six import string_types
import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a cache cluster exists.

    CLI example::

        salt myminion boto_elasticache.exists myelasticache
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.describe_cache_clusters(name)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the configuration for a cache cluster.

    CLI example::

        salt myminion boto_elasticache.get_config myelasticache
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return None
    try:
        cc = conn.describe_cache_clusters(name)
    except boto.exception.BotoServerError as e:
        msg = 'Failed to get config for cache cluster {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return {}
    cc = cc['DescribeCacheClustersResponse']['DescribeCacheClustersResult']
    cc = cc['CacheClusters'][0]
    ret = odict.OrderedDict()
    attrs = ['engine', 'cache_parameter_group', 'cache_cluster_id',
             'cache_security_groups', 'replication_group_id',
             'auto_minor_version_upgrade', 'num_cache_nodes',
             'preferred_availability_zone', 'security_groups',
             'cache_subnet_group_name', 'engine_version', 'cache_node_type',
             'notification_configuration', 'preferred_maintenance_window',
             'configuration_endpoint', 'cache_cluster_status']
    for key, val in six.iteritems(cc):
        _key = boto.utils.pythonize_name(key)
        if _key not in attrs:
            continue
        if _key == 'cache_parameter_group':
            if val:
                ret[_key] = val['CacheParameterGroupName']
            else:
                ret[_key] = None
        elif _key == 'cache_security_groups':
            if val:
                ret[_key] = [k['CacheSecurityGroupName'] for k in val]
            else:
                ret[_key] = []
        elif _key == 'configuration_endpoint':
            if val:
                ret['port'] = val['Port']
                ret['address'] = val['Address']
            else:
                ret['port'] = None
                ret['address'] = None
        elif _key == 'notification_configuration':
            if val:
                ret['notification_topic_arn'] = val['TopicArn']
            else:
                ret['notification_topic_arn'] = None
        else:
            ret[_key] = val
    return ret


def get_cache_subnet_group(name, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Get information about a cache subnet group.

    CLI example::

        salt myminion boto_elasticache.get_cache_subnet_group mycache_subnet_group
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        csg = conn.describe_cache_subnet_groups(name)
        csg = csg['DescribeCacheSubnetGroupsResponse']
        csg = csg['DescribeCacheSubnetGroupsResult']['CacheSubnetGroups'][0]
    except boto.exception.BotoServerError as e:
        msg = 'Failed to get cache subnet group {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return False
    except (IndexError, TypeError, KeyError):
        msg = 'Failed to get cache subnet group {0} (2).'.format(name)
        log.error(msg)
        return False
    ret = {}
    for key, val in six.iteritems(csg):
        if key == 'CacheSubnetGroupName':
            ret['cache_subnet_group_name'] = val
        elif key == 'CacheSubnetGroupDescription':
            ret['cache_subnet_group_description'] = val
        elif key == 'VpcId':
            ret['vpc_id'] = val
        elif key == 'Subnets':
            ret['subnets'] = []
            for subnet in val:
                _subnet = {}
                _subnet['subnet_id'] = subnet['SubnetIdentifier']
                _az = subnet['SubnetAvailabilityZone']['Name']
                _subnet['subnet_availability_zone'] = _az
                ret['subnets'].append(_subnet)
        else:
            ret[key] = val
    return ret


def create(name, num_cache_nodes, engine, cache_node_type,
           replication_group_id=None, engine_version=None,
           cache_parameter_group_name=None, cache_subnet_group_name=None,
           cache_security_group_names=None, security_group_ids=None,
           snapshot_arns=None, preferred_availability_zone=None,
           preferred_maintenance_window=None, port=None,
           notification_topic_arn=None, auto_minor_version_upgrade=True,
           wait=False, region=None, key=None, keyid=None, profile=None):
    '''
    Create a cache cluster.

    CLI example::

        salt myminion boto_elasticache.create myelasticache 1 redis cache.t1.micro cache_security_group_names='["myelasticachesg"]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.create_cache_cluster(
            name, num_cache_nodes, cache_node_type, engine,
            replication_group_id, engine_version, cache_parameter_group_name,
            cache_subnet_group_name, cache_security_group_names,
            security_group_ids, snapshot_arns, preferred_availability_zone,
            preferred_maintenance_window, port, notification_topic_arn,
            auto_minor_version_upgrade)
        if not wait:
            log.info('Created cache cluster {0}.'.format(name))
            return True
        while True:
            config = get_config(name, region, key, keyid, profile)
            if not config:
                return True
            if config['cache_cluster_status'] == 'creating':
                return True
            if config['cache_cluster_status'] == 'available':
                return True
            time.sleep(2)
        log.info('Created cache cluster {0}.'.format(name))
    except boto.exception.BotoServerError as e:
        msg = 'Failed to create cache cluster {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return False


def delete(name, wait=False, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a cache cluster.

    CLI example::

        salt myminion boto_elasticache.delete myelasticache
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_cache_cluster(name)
        if not wait:
            log.info('Deleted cache cluster {0}.'.format(name))
            return True
        while True:
            config = get_config(name, region, key, keyid, profile)
            if not config:
                return True
            if config['cache_cluster_status'] == 'deleting':
                return True
            time.sleep(2)
        log.info('Deleted cache cluster {0}.'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        msg = 'Failed to delete cache cluster {0}.'.format(name)
        log.error(msg)
        log.debug(e)
        return False


def create_cache_security_group(name, description, region=None, key=None,
                                keyid=None, profile=None):
    '''
    Create a cache security group.

    CLI example::

        salt myminion boto_elasticache.create_cache_security_group myelasticachesg 'My Cache Security Group'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    created = conn.create_cache_security_group(name, description)
    if created:
        log.info('Created cache security group {0}.'.format(name))
        return True
    else:
        msg = 'Failed to create cache security group {0}.'.format(name)
        log.error(msg)
        return False


def delete_cache_security_group(name, region=None, key=None, keyid=None,
                                profile=None):
    '''
    Delete a cache security group.

    CLI example::

        salt myminion boto_elasticache.delete_cache_security_group myelasticachesg 'My Cache Security Group'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    deleted = conn.delete_cache_security_group(name)
    if deleted:
        log.info('Deleted cache security group {0}.'.format(name))
        return True
    else:
        msg = 'Failed to delete cache security group {0}.'.format(name)
        log.error(msg)
        return False


def authorize_cache_security_group_ingress(name, ec2_security_group_name,
                                           ec2_security_group_owner_id,
                                           region=None, key=None, keyid=None,
                                           profile=None):
    '''
    Authorize network ingress from an ec2 security group to a cache security
    group.

    CLI example::

        salt myminion boto_elasticache.authorize_cache_security_group_ingress myelasticachesg myec2sg 879879
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        added = conn.authorize_cache_security_group_ingress(
            name, ec2_security_group_name, ec2_security_group_owner_id)
        if added:
            msg = 'Added {0} to cache security group {1}.'
            msg = msg.format(name, ec2_security_group_name)
            log.info(msg)
            return True
        else:
            msg = 'Failed to add {0} to cache security group {1}.'
            msg = msg.format(name, ec2_security_group_name)
            log.error(msg)
            return False
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = 'Failed to add {0} to cache security group {1}.'
        msg = msg.format(name, ec2_security_group_name)
        log.error(msg)
        return False


def revoke_cache_security_group_ingress(name, ec2_security_group_name,
                                        ec2_security_group_owner_id,
                                        region=None, key=None, keyid=None,
                                        profile=None):
    '''
    Revoke network ingress from an ec2 security group to a cache security
    group.

    CLI example::

        salt myminion boto_elasticache.revoke_cache_security_group_ingress myelasticachesg myec2sg 879879
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        removed = conn.revoke_cache_security_group_ingress(
            name, ec2_security_group_name, ec2_security_group_owner_id)
        if removed:
            msg = 'Removed {0} from cache security group {1}.'
            msg = msg.format(name, ec2_security_group_name)
            log.info(msg)
            return True
        else:
            msg = 'Failed to remove {0} from cache security group {1}.'
            msg = msg.format(name, ec2_security_group_name)
            log.error(msg)
            return False
    except boto.exception.EC2ResponseError as e:
        log.debug(e)
        msg = 'Failed to remove {0} from cache security group {1}.'
        msg = msg.format(name, ec2_security_group_name)
        log.error(msg)
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to ec2.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('elasticache.region'):
        region = __salt__['config.option']('elasticache.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('elasticache.key'):
        key = __salt__['config.option']('elasticache.key')
    if not keyid and __salt__['config.option']('elasticache.keyid'):
        keyid = __salt__['config.option']('elasticache.keyid')

    try:
        conn = boto.elasticache.connect_to_region(region,
                                                  aws_access_key_id=keyid,
                                                  aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make elasticache connection.')
        return None
    return conn
