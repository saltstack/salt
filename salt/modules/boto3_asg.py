# -*- coding: utf-8 -*-
'''
Execution module for Amazon Autoscaling Group written against Boto 3

.. versionadded:: Nitrogen

:configuration: This module accepts explicit elb credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: yaml

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        asg.keyid: GKTADJGHEIQSXMKKRBJ08H
        asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        asg.region: us-east-1

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
#pylint: disable=E0602,W0106

# Import Python libs
from __future__ import absolute_import
import datetime
import logging
import json

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils.odict as odict
log = logging.getLogger(__name__)  # pylint: disable=W1699

# Import third party libs
import salt.ext.six as six
try:
    #pylint: disable=unused-import
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
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
        return (False, 'The boto3_asg module could not be loaded: boto3 libraries not found')
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'autoscaling')


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an autoscale group exists.

    CLI example::

        salt myminion boto3_asg.exists myasg region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        _asg = conn.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
        asg = _asg['AutoScalingGroups']
        if asg:
            return True
        else:
            msg = 'The autoscale group does not exist in region {0}'.format(region)
            log.debug(msg)
            return False
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        return False


def get_config(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get the configuration for an autoscale group.

    CLI example::

        salt myminion boto3_asg.get_config myasg region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        _asg = conn.describe_auto_scaling_groups(AutoScalingGroupNames=[name])
        asg = _asg['AutoScalingGroups']
        if asg:
            asg = asg[0]
        else:
            return {}
        ret = odict.OrderedDict()
        attrs = ['AutoScalingGroupName', 'AvailabilityZones', 'DefaultCooldown',
                 'DesiredCapacity', 'HealthCheckGracePeriod', 'HealthCheckType',
                 'LaunchConfigurationName', 'LoadBalancerNames', 'TargetGroupARNs',
                 'MaxSize', 'MinSize', 'PlacementGroup', 'VPCZoneIdentifier',
                 'Tags', 'TerminationPolicies', 'SuspendedProcesses']
        for attr in attrs:
            # Tags are objects, so we need to turn them into dicts.
            if attr == 'Tags':
                _tags = []
                for tag in asg[attr]:
                    _tag = odict.OrderedDict()
                    _tag['Key'] = tag['Key']
                    _tag['Value'] = tag['Value']
                    _tag['PropagateAtLaunch'] = tag['PropagateAtLaunch']
                    _tags.append(_tag)
                ret['Tags'] = _tags
            # Boto accepts a string or list as input for VPCZoneIdentifier,
            # but always returns a comma separated list. We require lists in
            # states.
            elif attr == 'VPCZoneIdentifier':
                ret[attr] = asg[attr].split(',')
            # convert SuspendedProcess objects to names
            elif attr == 'SuspendedProcesses':
                suspended_processes = asg[attr]
                ret[attr] = sorted([x['ProcessName'] for x in suspended_processes])
            else:
                #ret[attr] = getattr(asg, attr)
                ret[attr] = asg.get(attr)
        # scaling policies
        policies = conn.describe_policies(AutoScalingGroupName=name)
        ret["ScalingPolicies"] = []
        for policy in policies['ScalingPolicies']:
            del policy['AutoScalingGroupName']
            ret["ScalingPolicies"].append(policy)
        # scheduled actions
        actions = conn.describe_scheduled_actions(AutoScalingGroupName=name)
        ret['ScheduledUpdateGroupActions'] = {}
        for action in actions['ScheduledUpdateGroupActions']:
            end_time = None
            if action['EndTime']:
                end_time = action['EndTime'].isoformat()
            ret['ScheduledUpdateGroupActions'][action['ScheduledActionName']] = dict([
              ("MinSize", action['MinSize']),
              ("MaxSize", action['MaxSize']),
              # AWS bug
              ("DesiredCapacity", int(action['DesiredCapacity'])),
              ("StartTime", action['StartTime'].isoformat()),
              ("EndTime", end_time),
              ("Recurrence", action['Recurrence'])
            ])
        return ret
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        return {}


def create(AutoScalingGroupName, LaunchConfigurationName, AvailabilityZones, MinSize, MaxSize,
           DesiredCapacity=None, LoadBalancerNames=None, TargetGroupARNs=None,
           DefaultCooldown=None, HealthCheckType=None, HealthCheckGracePeriod=None,
           PlacementGroup=None, VPCZoneIdentifier=None, Tags=None,
           TerminationPolicies=None, SuspendedProcesses=None,
           ScalingPolicies=None, ScheduledUpdateGroupActions=None, region=None,
           NotificationARN=None, NotificationTypes=None,
           key=None, keyid=None, profile=None):
    '''
    Create an autoscale group.

    CLI example::

        salt myminion boto3_asg.create myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 LoadBalancerNames='["myelb", "myelb2"]' Tags='[{"Key": "Name", "Value": "myasg", "PropagateAtLaunch": True}]'
    '''
    # Need kwargs at the top to avoid extra variables and boto3 doesnt support None arguments
    kwargs = vars()
    for k in ['region', 'key', 'keyid', 'profile', 'NotificationARN', 'NotificationTypes', 'ScheduledUpdateGroupActions']:
        del kwargs[k]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if isinstance(kwargs['AvailabilityZones'], six.string_types):
        kwargs['AvailabilityZones'] = json.loads(kwargs['AvailabilityZones'])
    if isinstance(kwargs['LoadBalancerNames'], six.string_types):
        kwargs['LoadBalancerNames'] = json.loads(kwargs['LoadBalancerNames'])
    if isinstance(kwargs['TargetGroupARNs'], six.string_types):
        kwargs['TargetGroupARNs'] = json.loads(kwargs['TargetGroupARNs'])
    if isinstance(kwargs['VPCZoneIdentifier'], list):
        kwargs['VPCZoneIdentifier'] = ','.join(kwargs['VPCZoneIdentifier'])
    if isinstance(kwargs['Tags'], six.string_types):
        kwargs['Tags'] = json.loads(kwargs['Tags'])
    # Make a list of tag objects from the dict.
    _tags = []
    if kwargs['Tags']:
        for tag in kwargs['Tags']:
            try:
                Key = tag.get('Key')
            except KeyError:
                log.error('Tag missing key.')
                return False
            try:
                Value = tag.get('Value')
            except KeyError:
                log.error('Tag missing value.')
                return False
            PropagateAtLaunch = tag.get('PropagateAtLaunch', False)
            _tag = {'ResourceId': kwargs['AutoScalingGroupName'], 'Key': Key, 'Value': Value, 'PropagateAtLaunch': PropagateAtLaunch}
            _tags.append(_tag)
    kwargs['Tags'] = _tags
    if isinstance(kwargs['TerminationPolicies'], six.string_types):
        kwargs['TerminationPolicies'] = json.loads(kwargs['TerminationPolicies'])
    if isinstance(kwargs['SuspendedProcesses'], six.string_types):
        kwargs['SuspendedProcesses'] = json.loads(kwargs['SuspendedProcesses'])
    if isinstance(ScheduledUpdateGroupActions, six.string_types):
        ScheduledUpdateGroupActions = json.loads(ScheduledUpdateGroupActions)
    try:
        kwargs = dict((k, v) for k, v in six.iteritems(kwargs) if v is not None)
        conn.create_auto_scaling_group(**kwargs)
        # create suspended process
        _create_suspended_processes(conn, kwargs['AutoScalingGroupName'], kwargs.get('SuspendedProcesses'))
        # create scaling policies
        _create_scaling_policies(conn, kwargs['AutoScalingGroupName'], kwargs.get('ScalingPolicies'))
        # create scheduled actions
        _create_scheduled_actions(conn, kwargs['AutoScalingGroupName'], ScheduledUpdateGroupActions)
        # create notifications
        if NotificationARN and NotificationTypes:
            conn.put_notification_configuration(AutoScalingGroupName=kwargs['AutoScalingGroupName'], TopicARN=NotificationARN, NotificationTypes=NotificationTypes)
        log.info('Created ASG {0}'.format(kwargs['AutoScalingGroupName']))
        return True
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            msg = 'Failed to create ASG {}: {}'.format(kwargs['AutoScalingGroupName'], e.response.get('Error', {}).get('Message'))
            log.error(msg)
        return {}


def update(AutoScalingGroupName, LaunchConfigurationName=None, AvailabilityZones=None,
           MinSize=None, MaxSize=None, DesiredCapacity=None, DefaultCooldown=None,
           HealthCheckType=None, HealthCheckGracePeriod=None, PlacementGroup=None,
           VPCZoneIdentifier=None, Tags=None, TerminationPolicies=None,
           SuspendedProcesses=None, ScalingPolicies=None, ScheduledUpdateGroupActions=None,
           NotificationARN=None, NotificationTypes=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Update an autoscale group.

    CLI example::

        salt myminion boto3_asg.update myasg mylc '["us-east-1a", "us-east-1e"]' 1 10 LoadBalancerNames='["myelb", "myelb2"]' Tags='[{"Key": "Name", Value="myasg", "PropagateAtLaunch": True}]'
    '''

    kwargs = vars()
    for k in ['NotificationTypes', 'ScalingPolicies', 'ScheduledUpdateGroupActions', 'region', 'key', 'keyid', 'profile']:
        del kwargs[k]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False, "failed to connect to AWS"
    if isinstance(kwargs['AvailabilityZones'], six.string_types):
        kwargs['AvailabilityZones'] = json.loads(kwargs['AvailabilityZones'])
    if isinstance(kwargs['VPCZoneIdentifier'], list):
        kwargs['VPCZoneIdentifier'] = ','.join(kwargs['VPCZoneIdentifier'])
    if isinstance(kwargs['Tags'], six.string_types):
        kwargs['Tags'] = json.loads(kwargs['Tags'])
    if isinstance(kwargs['TerminationPolicies'], six.string_types):
        kwargs['TerminationPolicies'] = json.loads(kwargs['TerminationPolicies'])
    if isinstance(kwargs['SuspendedProcesses'], six.string_types):
        kwargs['SuspendedProcesses'] = json.loads(kwargs['SuspendedProcesses'])
    if isinstance(ScheduledUpdateGroupActions, six.string_types):
        ScheduledUpdateGroupActions = json.loads(ScheduledUpdateGroupActions)

    # Massage our tagset into  add / remove lists
    # Use a boto3 call here b/c the boto2 call doeesn't implement filters
    current_tags = conn.describe_tags(Filters=[{'Name': 'auto-scaling-group',
                                      'Values': [kwargs['AutoScalingGroupName']]}]).get('Tags', [])
    current_tags = [{'Key': t['Key'],
                     'Value': t['Value'],
                     'ResourceId': t['ResourceId'],
                     'ResourceType': t['ResourceType'],
                     'PropagateAtLaunch': t.get('PropagateAtLaunch', False)}
                          for t in current_tags]
    add_tags = []
    desired_tags = []
    delete_tags = []
    if kwargs['Tags']:
        for tag in kwargs['Tags']:
            try:
                Key = tag.get('Key')
            except KeyError:
                log.error('Tag missing key.')
                return False
            try:
                Value = tag.get('Value')
            except KeyError:
                log.error('Tag missing value.')
                return False
            ResourceType = tag.get('ResourceType', 'auto-scaling-group')
            PropagateAtLaunch = tag.get('PropagateAtLaunch', False)
            _tag = {'ResourceId': kwargs['AutoScalingGroupName'], 'Key': Key, 'Value': Value, 'ResourceType': ResourceType, 'PropagateAtLaunch': PropagateAtLaunch}
            if _tag not in current_tags:
                add_tags.append(_tag)
            desired_tags.append(_tag)
        delete_tags = [t for t in current_tags if t not in desired_tags]
    del kwargs['Tags']

    try:
        kwargs = dict((k, v) for k, v in six.iteritems(kwargs) if v is not None)
        conn.update_auto_scaling_group(**kwargs)
        if NotificationARN and NotificationTypes:
            conn.put_notification_configuration(AutoScalingGroupName=kwargs['AutoScalingGroupName'], TopicARN=NotificationARN, NotificationTypes=NotificationTypes)
        if add_tags:
            log.debug('Adding/updating tags from ASG: {}'.format(add_tags))
            conn.create_or_update_tags(Tags=add_tags)
        if delete_tags:
            log.debug('Deleting tags from ASG: {}'.format(delete_tags))
            conn.delete_tags(Tags=delete_tags)
        # update doesn't handle suspended_processes either
        # Resume all processes
        conn.resume_processes(AutoScalingGroupName=kwargs['AutoScalingGroupName'])
        # suspend any that are specified.  Note that the boto default of empty
        # list suspends all; don't do that.
        _create_suspended_processes(conn, kwargs['AutoScalingGroupName'], kwargs.get('SuspendedProcesses'))
        log.info('Updated ASG {0}'.format(kwargs['AutoScalingGroupName']))
        # ### scaling policies
        # delete all policies, then recreate them
        policies = conn.describe_policies(AutoScalingGroupName=kwargs['AutoScalingGroupName'])
        if policies['ScalingPolicies']:
            for policy in policies['ScalingPolicies']:
                conn.delete_policy(AutoScalingGroupName=kwargs['AutoScalingGroupName'], PolicyName=policy['PolicyName'])
        _create_scaling_policies(conn, kwargs['AutoScalingGroupName'], ScalingPolicies)
        # ### scheduled actions
        # delete all scheduled actions, then recreate them
        scheduled_actions = conn.describe_scheduled_actions(AutoScalingGroupName=kwargs['AutoScalingGroupName'])
        if scheduled_actions['ScheduledUpdateGroupActions']:
            for scheduled_action in scheduled_actions['ScheduledUpdateGroupActions']:
                conn.delete_scheduled_action(AutoScalingGroupName=kwargs['AutoScalingGroupName'], ScheduledActionName=scheduled_action['ScheduledActionName'])
        _create_scheduled_actions(conn, kwargs['AutoScalingGroupName'], ScheduledUpdateGroupActions)
        return True, ''
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            msg = 'Failed to update ASG {}: {}'.format(kwargs['AutoScalingGroupName'], e.response.get('Error', {}).get('Message'))
            log.error(msg)
        return False, str(e)


def _create_scaling_policies(conn, as_name, ScalingPolicies):
    'helper function to create scaling policies'
    if ScalingPolicies:
        for policy in ScalingPolicies:
            policy.update({'AutoScalingGroupName': as_name})
            policy = dict((k, v) for k, v in six.iteritems(policy) if v is not None)
            conn.put_scaling_policy(**policy)


def _create_scheduled_actions(conn, as_name, ScheduledUpdateGroupActions):
    '''
    Helper function to create scheduled actions
    '''
    if ScheduledUpdateGroupActions:
        for name, action in six.iteritems(ScheduledUpdateGroupActions):
            if 'StartTime' in action and isinstance(action['StartTime'], six.string_types):
                action['StartTime'] = datetime.datetime.strptime(
                    action['StartTime'], DATE_FORMAT
                )
            if 'EndTime' in action and isinstance(action['EndTime'], six.string_types):
                action['EndTime'] = datetime.datetime.strptime(
                    action['EndTime'], DATE_FORMAT
                )
            conn.put_scheduled_update_group_action(
                AutoScalingGroupName=as_name,
                ScheduledActionName=name,
                DesiredCapacity=action.get('DesiredCapacity'),
                MinSize=action.get('MinSize'),
                MaxSize=action.get('MaxSize'),
                StartTime=action.get('StartTime'),
                EndTime=action.get('EndTime'),
                Recurrence=action.get('Recurrence')
            )


def _create_suspended_processes(conn, as_name, SuspendedProcesses):
    'helper function to create suspended processes'
    if SuspendedProcesses is not None and len(SuspendedProcesses) > 0:
        conn.suspend_processes(AutoScalingGroupName=name, ScalingProcesses=ScalingProcesses)


def delete(AutoScalingGroupName, force=False, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an autoscale group.

    CLI example::

        salt myminion boto3_asg.delete myasg region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.delete_auto_scaling_group(AutoScalingGroupName=AutoScalingGroupName, ForceDelete=force)
        msg = 'Deleted autoscale group {0}.'.format(AutoScalingGroupName)
        log.info(msg)
        return True
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            msg = 'Failed to delete ASG {}: {}'.format(AutoScalingGroupName, e.response.get('Error', {}).get('Message'))
            log.error(msg)
        return False


def launch_configuration_exists(name, region=None, key=None, keyid=None,
                                profile=None):
    '''
    Check for a launch configuration's existence.

    CLI example::

        salt myminion boto3_asg.launch_configuration_exists mylc
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        _lc = conn.describe_launch_configurations(LaunchConfigurationNames=[name])
        lc = _lc['LaunchConfigurations']
        if lc:
            return True
        else:
            msg = 'The launch configuration does not exist in region {0}'.format(region)
            log.debug(msg)
            return False
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        return False


def get_all_launch_configurations(region=None, key=None, keyid=None,
                                  profile=None):
    '''
    Fetch and return all Launch Configuration with details.

    CLI example::

        salt myminion boto3_asg.get_all_launch_configurations
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        lc = conn.describe_launch_configurations()
        return lc['LaunchConfigurations']
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        return []


def describe_launch_configuration(name, region=None, key=None, keyid=None,
                                  profile=None):
    '''
    Dump details of a given launch configuration.

    CLI example::

        salt myminion boto3_asg.describe_launch_configuration mylc
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        _lc = conn.describe_launch_configurations(LaunchConfigurationNames=[name])
        lc = _lc['LaunchConfigurations']
        if lc:
            return lc[0]
        else:
            msg = 'The launch configuration does not exist in region {0}'.format(region)
            log.debug(msg)
            return None
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        return None


def create_launch_configuration(LaunchConfigurationName, ImageId, KeyName=None,
                                VpcId=None, VpcName=None,
                                SecurityGroups=None, UserData=None,
                                InstanceType='m1.small', KernelId=None,
                                RamdiskId=None, BlockDeviceMappings=None,
                                InstanceMonitoring=False, SpotPrice=None,
                                IamInstanceProfile=None,
                                EbsOptimized=False,
                                AssociatePublicIpAddress=False,
                                region=None, key=None, keyid=None,
                                profile=None):
    '''
    Create a launch configuration.

    CLI example::

        salt myminion boto3_asg.create_launch_configuration mylc ImageId=ami-0b9c9f62 KeyName='mykey' SecurityGroups='["mygroup"]' InstanceType='c3.2xlarge'
    '''
    # Need kwargs at the top to avoid extra variables and boto3 doesnt support None arguments
    kwargs = vars()
    for k in ['region', 'key', 'keyid', 'profile']:
        del kwargs[k]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if isinstance(kwargs['SecurityGroups'], six.string_types):
        kwargs['SecurityGroups'] = json.loads(kwargs['SecurityGroups'])
    if isinstance(kwargs['BlockDeviceMappings'], six.string_types):
        kwargs['BlockDeviceMappings'] = json.loads(kwargs['BlockDeviceMappings'])
    if kwargs['SpotPrice']:
        kwargs['SpotPrice'] = str(kwargs['SpotPrice'])
    _bdms = []
    if kwargs['BlockDeviceMappings']:
        # Boto requires objects for the mappings and the devices.
        for block_device_dict in kwargs['BlockDeviceMappings']:
            for block_device, attributes in six.iteritems(block_device_dict):
                _block_device_map = {'DeviceName': block_device, 'Ebs': {}}
                for attribute, value in six.iteritems(attributes):
                    _block_device_map['Ebs'][attribute] = value
            _bdms.append(_block_device_map)
    kwargs['BlockDeviceMappings'] = _bdms

    # If a VPC is specified, then determine the secgroup id's within that VPC, not
    # within the default VPC. If a security group id is already part of the list,
    # convert_to_group_ids leaves that entry without attempting a lookup on it.
    if kwargs['SecurityGroups'] and (VpcId or VpcName):
        kwargs['SecurityGroups'] = __salt__['boto_secgroup.convert_to_group_ids'](
                               kwargs['SecurityGroups'],
                               vpc_id=VpcId, vpc_name=VpcName,
                               region=region, key=key, keyid=keyid,
                               profile=profile
                           )
    kwargs['InstanceMonitoring'] = {'Enabled': InstanceMonitoring}
    try:
        kwargs = dict((k, v) for k, v in six.iteritems(kwargs) if v is not None)
        conn.create_launch_configuration(**kwargs)
        log.info('Created LC {0}'.format(kwargs['LaunchConfigurationName']))
        return True
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            msg = 'Failed to create LC {}: {}'.format(kwargs['LaunchConfigurationName'], e.response.get('Error', {}).get('Message'))
            log.error(msg)
        return False


def delete_launch_configuration(name, region=None, key=None, keyid=None,
                                profile=None):
    '''
    Delete a launch configuration.

    CLI example::

        salt myminion boto3_asg.delete_launch_configuration mylc
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.delete_launch_configuration(LaunchConfigurationName=name)
        log.info('Deleted LC {0}'.format(name))
        return True
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            msg = 'Failed to delete LC {0}'.format(name)
            log.error(msg)
        return False


def get_scaling_policy_arn(as_group, PolicyName, region=None,
                           key=None, keyid=None, profile=None):
    '''
    Return the arn for a scaling policy in a specific autoscale group or None
    if not found. Mainly used as a helper method for boto_cloudwatch_alarm, for
    linking alarms to scaling policies.

    CLI Example::

        salt '*' boto3_asg.get_scaling_policy_arn mygroup mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    policies = conn.describe_policies(AutoScalingGroupName=as_group)
    for policy in policies['ScalingPolicies']:
        if policy['PolicyName'] == PolicyName:
            return policy['PolicyARN']
    log.error('Could not convert: {0}'.format(as_group))
    return None


def get_all_groups(region=None, key=None, keyid=None, profile=None):
    '''
    Return all AutoScale Groups visible in the account
    (as a list of boto.ec2.autoscale.group.AutoScalingGroup).

    .. versionadded:: 2016.11.0

    CLI example:

    .. code-block:: bash

        salt-call boto3_asg.get_all_groups region=us-east-1 --output yaml

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        _asg = conn.describe_auto_scaling_groups()
        return _asg['AutoScalingGroups']
    except ClientError as e:
        logging.debug(e.__dict__)
        if e.response.get('Error', {}).get('Code') in ['Throttling']:
            log.debug('Throttled by AWS API')
        else:
            log.error(e)
        return []


def list_groups(region=None, key=None, keyid=None, profile=None):
    '''
    Return all AutoScale Groups visible in the account
    (as a list of names).

    .. versionadded:: 2016.11.0

    CLI example:

    .. code-block:: bash

        salt-call boto3_asg.list_groups region=us-east-1

    '''
    return [a['AutoScalingGroupName'] for a in get_all_groups(region=region, key=key, keyid=keyid, profile=profile)]


def update_asg_load_balancers(AutoScalingGroupName, attach=None, detach=None, region=None, key=None, keyid=None, profile=None):
    '''
    Updates the autoscaling group classic load balancers
    (as a list of names).

    .. versionadded:: 2016.11.0

    CLI example:

    .. code-block:: bash

        salt-call boto3_asg.update_asg_load_balancers mygroup attach='["my-load-balancer"]' region=us-east-1
        salt-call boto3_asg.update_asg_load_balancers mygroup detach='["my-load-balancer"]' region=us-east-1

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if attach:
        conn.attach_load_balancers(AutoScalingGroupName=AutoScalingGroupName, LoadBalancerNames=attach)
    elif detach:
        conn.detach_load_balancers(AutoScalingGroupName=AutoScalingGroupName, LoadBalancerNames=detach)
        return True
    return False


def update_asg_target_groups(AutoScalingGroupName, attach=None, detach=None, region=None, key=None, keyid=None, profile=None):
    '''
    Updates the autoscaling group target groups
    (as a list of names).

    .. versionadded:: 2016.11.0

    CLI example:

    .. code-block:: bash

        salt-call boto3_asg.update_asg_target_groups mygroup attach='["arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163"]' region=us-east-1
        salt-call boto3_asg.update_asg_target_groups mygroup detach='["arn:aws:elasticloadbalancing:us-west-2:644138682826:targetgroup/learn1give1-api/414788a16b5cf163"]' region=us-east-1

    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if attach:
        conn.attach_load_balancer_target_groups(AutoScalingGroupName=AutoScalingGroupName, TargetGroupARNs=attach)
    elif detach:
        conn.detach_load_balancer_target_groups(AutoScalingGroupName=AutoScalingGroupName, TargetGroupARNs=detach)
        return True
    return False
