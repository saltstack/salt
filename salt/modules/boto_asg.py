# -*- coding: utf-8 -*-
'''
Connection module for Amazon Autoscale Groups

.. versionadded:: Helium

:configuration: This module accepts explicit autoscale credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        asg.keyid: GKTADJGHEIQSXMKKRBJ08H
        asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        asg.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''

# Import Python libs
import logging
import json

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2
    import boto.ec2.autoscale as autoscale
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt._compat import string_types
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
    Check to see if an autoscale group exists.

    CLI example::

        salt myminion boto_asg.exists myasg region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.conn.get_all_groups(names=[name])
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the configuration for an autoscale group

    CLI example::

        salt myminion boto_asg.get_config myasg region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return None
    try:
        asg = conn.get_all_groups(names=[name])
        if asg:
            asg = asg[0]
        else:
            return {}
        ret = odict.OrderedDict()
        attrs = ['name', 'availability_zones', 'default_cooldown',
                 'desired_capacity', 'health_check_period',
                 'health_check_type', 'launch_config_name', 'load_balancers',
                 'max_size', 'min_size', 'placement_group',
                 'vpc_zone_identifier', 'tags', 'termination_policies']
        for attr in attrs:
            # Tags are objects, so we need to turn them into dicts.
            if attr == 'tags':
                _tags = []
                for tag in asg.tags:
                    _tag = odict.OrderedDict()
                    _tag['key'] = tag.key
                    _tag['value'] = tag.value
                    _tag['propagate_at_launch'] = tag.propagate_at_launch
                    _tags.append(_tag)
                ret['tags'] = _tags
            else:
                ret[attr] = getattr(asg, attr)
        return ret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return {}


def create(name, launch_config_name, availability_zones, min_size, max_size,
           desired_capacity=None, load_balancers=None, default_cooldown=None,
           health_check_type=None, health_check_period=None,
           placement_group=None, vpc_zone_identifier=None, tags=None,
           termination_policies=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an ELB

    CLI example to create an ELB::

        salt myminion boto_asg.create myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 load_balancers='["myelb", "myelb2"]' tags='[{"key": "Name", value="myasg", "propagate_at_launch": True}]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    if isinstance(load_balancers, string_types):
        load_balancers = json.loads(load_balancers)
    if isinstance(vpc_zone_identifier, string_types):
        vpc_zone_identifier = json.loads(vpc_zone_identifier)
    if isinstance(tags, string_types):
        tags = json.loads(tags)
    # Make a list of tag objects from the dict.
    _tags = []
    for tag in tags:
        try:
            key = tag.get('key')
        except KeyError:
            log.error('Tag missing key.')
            return False
        try:
            value = tag.get('value')
        except KeyError:
            log.error('Tag missing value.')
            return False
        propagate_at_launch = tag.get('propagate_at_launch', False)
        _tag = autoscale.Tag(key=key, value=value, resource_id=name,
                             propagate_at_launch=propagate_at_launch)
        _tags.append(_tag)
    if isinstance(termination_policies, string_types):
        termination_policies = json.loads(termination_policies)
    try:
        _asg = autoscale.AutoScalingGroup(
            name=name, launch_config=launch_config_name,
            availability_zones=availability_zones,
            min_size=min_size, max_size=max_size,
            desired_capacity=desired_capacity, load_balancers=load_balancers,
            default_cooldown=default_cooldown,
            health_check_type=health_check_type,
            health_check_period=health_check_period,
            placement_group=placement_group, tags=_tags,
            vpc_zone_identifier=vpc_zone_identifier,
            termination_policies=termination_policies)
        conn.create_auto_scaling_group(_asg)
        log.info('Created ASG {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create ELB {0}'.format(name)
        log.error(msg)
        return False


def update(name, launch_config_name, availability_zones, min_size, max_size,
           desired_capacity=None, load_balancers=None, default_cooldown=None,
           health_check_type=None, health_check_period=None,
           placement_group=None, vpc_zone_identifier=None, tags=None,
           termination_policies=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Update an ELB

    CLI example::

        salt myminion boto_asg.update myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 load_balancers='["myelb", "myelb2"]' tags='[{"key": "Name", value="myasg", "propagate_at_launch": True}]'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(availability_zones, string_types):
        availability_zones = json.loads(availability_zones)
    if isinstance(load_balancers, string_types):
        load_balancers = json.loads(load_balancers)
    if isinstance(vpc_zone_identifier, string_types):
        vpc_zone_identifier = json.loads(vpc_zone_identifier)
    if isinstance(tags, string_types):
        tags = json.loads(tags)
    # Make a list of tag objects from the dict.
    _tags = []
    for tag in tags:
        try:
            key = tag.get('key')
        except KeyError:
            log.error('Tag missing key.')
            return False
        try:
            value = tag.get('value')
        except KeyError:
            log.error('Tag missing value.')
            return False
        propagate_at_launch = tag.get('propagate_at_launch', False)
        _tag = autoscale.Tag(key=key, value=value, resource_id=name,
                             propagate_at_launch=propagate_at_launch)
        _tags.append(_tag)
    if isinstance(termination_policies, string_types):
        termination_policies = json.loads(termination_policies)
    try:
        _asg = autoscale.AutoScalingGroup(
            connection=conn,
            name=name, launch_config=launch_config_name,
            availability_zones=availability_zones,
            min_size=min_size, max_size=max_size,
            desired_capacity=desired_capacity, load_balancers=load_balancers,
            default_cooldown=default_cooldown,
            health_check_type=health_check_type,
            health_check_period=health_check_period,
            placement_group=placement_group, tags=_tags,
            vpc_zone_identifier=vpc_zone_identifier,
            termination_policies=termination_policies)
        _asg.update()
        # Seems the update call doesn't handle tags, so we'll need to update
        # that separately.
        conn.create_or_update_tags(_tags)
        log.info('Updated ASG {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update ELB {0}'.format(name)
        log.error(msg)
        return False


def delete(name, force=False, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an autoscale group.

    CLI example::

        salt myminion boto_asg.delete myasg region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_auto_scaling_group(name, force)
        msg = 'Deleted autoscale group {0}.'.format(name)
        log.info(msg)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete autoscale group {0}'.format(name)
        log.error(msg)
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to autoscale.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('asg.region'):
        region = __salt__['config.option']('asg.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('asg.key'):
        key = __salt__['config.option']('asg.key')
    if not keyid and __salt__['config.option']('asg.keyid'):
        keyid = __salt__['config.option']('asg.keyid')

    try:
        conn = autoscale.connect_to_region(region, aws_access_key_id=keyid,
                                           aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto autoscale connection.')
        return None
    return conn
