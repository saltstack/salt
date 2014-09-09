# -*- coding: utf-8 -*-
'''
Connection module for Amazon Autoscale Groups

.. versionadded:: 2014.7.0

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
import yaml
import email.mime.multipart

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.ec2
    import boto.ec2.blockdevicemapping as blockdevicemapping
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
        conn.get_all_groups(names=[name])
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False


def get_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the configuration for an autoscale group.

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
                 'vpc_zone_identifier', 'tags', 'termination_policies',
                 'suspended_processes']
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
            # Boto accepts a string or list as input for vpc_zone_identifier,
            # but always returns a comma separated list. We require lists in
            # states.
            elif attr == 'vpc_zone_identifier':
                ret[attr] = getattr(asg, attr).split(',')
            # convert SuspendedProcess objects to names
            elif attr == 'suspended_processes':
                suspended_processes = getattr(asg, attr)
                ret[attr] = sorted([x.process_name for x in suspended_processes])
            else:
                ret[attr] = getattr(asg, attr)
        # scaling policies
        policies = conn.get_all_policies(as_group=name)
        ret["scaling_policies"] = []
        for policy in policies:
            ret["scaling_policies"].append(
                dict([
                    ("name", policy.name),
                    ("adjustment_type", policy.adjustment_type),
                    ("scaling_adjustment", policy.scaling_adjustment),
                    ("min_adjustment_step", policy.min_adjustment_step),
                    ("cooldown", policy.cooldown)
                ])
            )
        return ret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return {}


def create(name, launch_config_name, availability_zones, min_size, max_size,
           desired_capacity=None, load_balancers=None, default_cooldown=None,
           health_check_type=None, health_check_period=None,
           placement_group=None, vpc_zone_identifier=None, tags=None,
           termination_policies=None, suspended_processes=None,
           scaling_policies=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Create an autoscale group.

    CLI example::

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
    if tags:
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
    if isinstance(suspended_processes, string_types):
        suspended_processes = json.loads(suspended_processes)
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
            termination_policies=termination_policies,
            suspended_processes=suspended_processes)
        conn.create_auto_scaling_group(_asg)
        # create scaling policies
        _create_scaling_policies(conn, name, scaling_policies)
        log.info('Created ASG {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create ASG {0}'.format(name)
        log.error(msg)
        return False


def update(name, launch_config_name, availability_zones, min_size, max_size,
           desired_capacity=None, load_balancers=None, default_cooldown=None,
           health_check_type=None, health_check_period=None,
           placement_group=None, vpc_zone_identifier=None, tags=None,
           termination_policies=None, suspended_processes=None,
           scaling_policies=None,
           region=None, key=None, keyid=None,
           profile=None):
    '''
    Update an autoscale group.

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
    if tags:
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
    if isinstance(suspended_processes, string_types):
        suspended_processes = json.loads(suspended_processes)
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
        if _tags:
            conn.create_or_update_tags(_tags)
        # update doesn't handle suspended_processes either
        # Resume all processes
        _asg.resume_processes()
        # suspend any that are specified. Note that the boto default of empty
        # list suspends all; don't do that.
        if suspended_processes is not None and len(suspended_processes) > 0:
            _asg.suspend_processes(suspended_processes)
        log.info('Updated ASG {0}'.format(name))
        #### scaling policies
        # delete all policies, then recreate them
        for policy in conn.get_all_policies(as_group=name):
            conn.delete_policy(policy.name, autoscale_group=name)
        _create_scaling_policies(conn, name, scaling_policies)
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update ASG {0}'.format(name)
        log.error(msg)
        return False


def _create_scaling_policies(conn, as_name, scaling_policies):
    'helper function to create scaling policies'
    if scaling_policies:
        for policy in scaling_policies:
            policy = autoscale.policy.ScalingPolicy(
                name=policy["name"],
                as_name=as_name,
                adjustment_type=policy["adjustment_type"],
                scaling_adjustment=policy["scaling_adjustment"],
                min_adjustment_step=policy.get("min_adjustment_step", None),
                cooldown=policy["cooldown"])
            conn.create_scaling_policy(policy)


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


def get_cloud_init_mime(cloud_init):
    '''
    Get a mime multipart encoded string from a cloud-init dict. Currently
    supports scripts and cloud-config.

    CLI Example:

    .. code-block:: bash

        salt myminion boto.get_cloud_init_mime <cloud init>
    '''
    if isinstance(cloud_init, string_types):
        cloud_init = json.loads(cloud_init)
    _cloud_init = email.mime.multipart.MIMEMultipart()
    if 'scripts' in cloud_init:
        for script_name, script in cloud_init['scripts'].iteritems():
            _script = email.mime.text.MIMEText(script, 'x-shellscript')
            _cloud_init.attach(_script)
    if 'cloud-config' in cloud_init:
        cloud_config = cloud_init['cloud-config']
        _cloud_config = email.mime.text.MIMEText(yaml.dump(cloud_config),
                                                 'cloud-config')
        _cloud_init.attach(_cloud_config)
    return _cloud_init.as_string()


def launch_configuration_exists(name, region=None, key=None, keyid=None,
                                profile=None):
    '''
    Check for a launch configuration's existence.

    CLI example::

        salt myminion boto_asg.launch_configuration_exists mylc
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    lc = conn.get_all_launch_configurations(names=[name])
    if lc:
        return True
    else:
        return False


def create_launch_configuration(name, image_id, key_name=None,
                                security_groups=None, user_data=None,
                                instance_type='m1.small', kernel_id=None,
                                ramdisk_id=None, block_device_mappings=None,
                                instance_monitoring=False, spot_price=None,
                                instance_profile_name=None,
                                ebs_optimized=False,
                                associate_public_ip_address=None,
                                volume_type=None, delete_on_termination=True,
                                iops=None, use_block_device_types=False,
                                region=None, key=None, keyid=None,
                                profile=None):
    '''
    Create a launch configuration.

    CLI example::

        salt myminion boto_asg.create_launch_configuration mylc image_id=ami-0b9c9f62 key_name='mykey' security_groups='["mygroup"]' instance_type='c3.2xlarge'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if isinstance(security_groups, string_types):
        security_groups = json.loads(security_groups)
    if isinstance(block_device_mappings, string_types):
        block_device_mappings = json.loads(block_device_mappings)
    _bdms = []
    if block_device_mappings:
        # Boto requires objects for the mappings and the devices.
        _block_device_map = blockdevicemapping.BlockDeviceMapping()
        for block_device_dict in block_device_mappings:
            for block_device, attributes in block_device_dict.iteritems():
                _block_device = blockdevicemapping.EBSBlockDeviceType()
                for attribute, value in attributes.iteritems():
                    setattr(_block_device, attribute, value)
                _block_device_map[block_device] = _block_device
        _bdms = [_block_device_map]
    lc = autoscale.LaunchConfiguration(
        name=name, image_id=image_id, key_name=key_name,
        security_groups=security_groups, user_data=user_data,
        instance_type=instance_type, kernel_id=kernel_id,
        ramdisk_id=ramdisk_id, block_device_mappings=_bdms,
        instance_monitoring=instance_monitoring, spot_price=spot_price,
        instance_profile_name=instance_profile_name,
        ebs_optimized=ebs_optimized,
        associate_public_ip_address=associate_public_ip_address,
        volume_type=volume_type, delete_on_termination=delete_on_termination,
        iops=iops, use_block_device_types=use_block_device_types)
    try:
        conn.create_launch_configuration(lc)
        log.info('Created LC {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create LC {0}'.format(name)
        log.error(msg)
        return False


def delete_launch_configuration(name, region=None, key=None, keyid=None,
                                profile=None):
    '''
    Delete a launch configuration.

    CLI example::

        salt myminion boto_asg.delete_launch_configuration mylc
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.delete_launch_configuration(name)
        log.info('Deleted LC {0}'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete LC {0}'.format(name)
        log.error(msg)
        return False


def get_scaling_policy_arn(as_group, scaling_policy_name, region=None,
                           key=None, keyid=None, profile=None):
    '''
    Return the arn for a scaling policy in a specific autoscale group or None
    if not found. Mainly used as a helper method for boto_cloudwatch_alarm, for
    linking alarms to scaling policies.

    CLI Example::

        salt '*' boto_asg.get_scaling_policy_arn mygroup mypolicy
    '''
    conn = _get_conn(region, key, keyid, profile)
    policies = conn.get_all_policies(as_group=as_group)
    for policy in policies:
        if policy.name == scaling_policy_name:
            return policy.policy_arn
    log.error('Could not convert: {0}'.format(as_group))
    return None


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
