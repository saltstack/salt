# -*- coding: utf-8 -*-
'''
Manage Autoscale Groups with Boto 3
===================================

.. versionadded:: 2014.7.0

Create and destroy autoscale groups. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses boto, which can be installed via package, or pip.

This module accepts explicit autoscale credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More Information available at:

.. code-block:: text

    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

If IAM roles are not used you need to specify them either in a pillar or
in the minion's config file:

.. code-block:: yaml

    asg.keyid: GKTADJGHEIQSXMKKRBJ08H
    asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify key, keyid and region via a profile, either
as a passed in dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    Ensure myasg exists:
      boto3_asg.present:
        - AutoScalingGroupName: myasg
        - LaunchConfigurationName: mylc
        - AvailabilityZones:
          - us-east-1a
          - us-east-1b
        - MinSize: 1
        - MaxSize: 1
        - DesiredCapacity: 1
        - LoadBalancerNames:
          - myelb
        - SuspendedProcesses:
            - AddToLoadBalancer
            - AlarmNotification
        - ScalingPolicies
            - AdjustmentType: ChangeInCapacity
            - AutoScalingGroupName: api-production-iad
            - Cooldown: 1800
            - MinAdjustmentStep: None
            - PolicyName: ScaleDown
            - ScalingAdjustment: -1
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars.
    Ensure myasg exists:
      boto3_asg.present:
        - AutoScalingGroupName: myasg
        - LaunchConfigurationName: mylc
        - AvailabilityZones:
          - us-east-1a
          - us-east-1b
        - MinSize: 1
        - MaxSize: 1
        - DesiredCapacity: 1
        - LoadBalancerNames:
          - myelb
        - profile: myprofile

    # Passing in a profile.
    Ensure myasg exists:
      boto3_asg.present:
        - AutoScalingGroupName: myasg
        - LaunchConfigurationName: mylc
        - AvailabilityZones:
          - us-east-1a
          - us-east-1b
        - MinSize: 1
        - MaxSize: 1
        - DesiredCapacity: 1
        - LoadBalancerNames:
          - myelb
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    # Deleting an autoscale group with running instances.
    Ensure myasg is deleted:
      boto3_asg.absent:
        - name: myasg
        # If instances exist, we must force the deletion of the asg.
        - force: True

It's possible to specify cloudwatch alarms that will be setup along with the
ASG. Note the alarm name will be the name attribute defined, plus the ASG
resource name.

.. code-block:: yaml

    Ensure myasg exists:
      boto3_asg.present:
        - AutoScalingGroupName: myasg
        - LaunchConfigurationName: mylc
        - AvailabilityZones:
          - us-east-1a
          - us-east-1b
        - MinSize: 1
        - MaxSize: 1
        - DesiredCapacity: 1
        - LoadBalancerNames:
          - myelb
        - profile: myprofile
        - alarms:
            CPU:
              name: 'ASG CPU **MANAGED BY SALT**'
              attributes:
                metric: CPUUtilization
                namespace: AWS/EC2
                statistic: Average
                comparison: '>='
                threshold: 65.0
                period: 60
                evaluation_periods: 30
                unit: null
                description: 'ASG CPU'
                alarm_actions: [ 'arn:aws:sns:us-east-1:12345:myalarm' ]
                insufficient_data_actions: []
                ok_actions: [ 'arn:aws:sns:us-east-1:12345:myalarm' ]

You can also use alarms from pillars, and override values from the pillar
alarms by setting overrides on the resource. Note that 'boto3_asg_alarms'
will be used as a default value for all resources, if defined and can be
used to ensure alarms are always set for an ASG resource.

Setting the alarms in a pillar:

.. code-block:: yaml

    my_asg_alarm:
      CPU:
        name: 'ASG CPU **MANAGED BY SALT**'
        attributes:
          metric: CPUUtilization
          namespace: AWS/EC2
          statistic: Average
          comparison: '>='
          threshold: 65.0
          period: 60
          evaluation_periods: 30
          unit: null
          description: 'ASG CPU'
          alarm_actions: [ 'arn:aws:sns:us-east-1:12345:myalarm' ]
          insufficient_data_actions: []
          ok_actions: [ 'arn:aws:sns:us-east-1:12345:myalarm' ]

Overriding the alarm values on the resource:

.. code-block:: yaml

    Ensure myasg exists:
      boto3_asg.present:
        - AutoScalingGroupName: myasg
        - LaunchConfigurationName: mylc
        - AvailabilityZones:
          - us-east-1a
          - us-east-1b
        - MinSize: 1
        - MaxSize: 1
        - DesiredCapacity: 1
        - LoadBalancerNames:
          - myelb
        - profile: myprofile
        - alarms_from_pillar: my_asg_alarm
        # override CPU:attributes:threshold
        - alarms:
            CPU:
              attributes:
                threshold: 50.0
'''

# Import Python libs
from __future__ import absolute_import
import hashlib
import logging
import copy

# Import Salt libs
import salt.utils.dictupdate as dictupdate
import salt.ext.six as six
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto3_asg' if 'boto3_asg.exists' in __salt__ else False


def present(name,
        LaunchConfigurationName,
        AvailabilityZones,
        MinSize,
        MaxSize,
        AutoScalingGroupName=None,
        LaunchConfig=None,
        DesiredCapacity=None,
        LoadBalancerNames=None,
        TargetGroupNames=None,
        DefaultCooldown=None,
        HealthCheckType=None,
        HealthCheckGracePeriod=None,
        PlacementGroup=None,
        VPCZoneIdentifier=None,
        SubnetNames=None,
        Tags=None,
        TerminationPolicies=None,
        TerminationPolicies_from_pillar='boto3_asg_termination_policies',
        SuspendedProcesses=None,
        ScalingPolicies=None,
        ScalingPolicies_from_pillar='boto3_asg_scaling_policies',
        ScheduledUpdateGroupActions=None,
        ScheduledUpdateGroupActions_from_pillar='boto3_asg_scheduled_actions',
        alarms=None,
        alarms_from_pillar='boto3_asg_alarms',
        region=None,
        key=None,
        keyid=None,
        profile=None,
        NotificationARN=None,
        NotificationARN_from_pillar='boto3_asg_notification_arn',
        NotificationTypes=None,
        NotificationTypes_from_pillar='boto3_asg_notification_types'):
    '''
    Ensure the autoscale group exists.

    name
        The name of the state definition.  This will be used as the 'CallerReference' param when
        creating the autoscaling group to help ensure idempotency.

    AutoScalingGroupName
        Name of the autoscale group.

    LaunchConfigurationName
        Name of the launch config to use for the group.  Or, if
        ``LaunchConfig`` is specified, this will be the launch config
        name's prefix.  (see below)

    LaunchConfig
        A dictionary of launch config attributes.  If specified, a
        launch config will be used or created, matching this set
        of attributes, and the autoscale group will be set to use
        that launch config.  The launch config name will be the
        ``launch_config_name`` followed by a hyphen followed by a hash
        of the ``LaunchConfig`` dict contents.
        Example:

        .. code-block:: yaml

            my_asg:
              boto3_asg.present:
              - LaunchConfig:
                - EbsOptimized: false
                - IamInstanceProfile: my_iam_profile
                - KernelId: ''
                - RamdiskId: ''
                - KeyName: my_ssh_key
                - ImageName: aws2015091-hvm
                - InstanceType: c3.xlarge
                - InstanceMonitoring: false
                - SecurityGroups:
                  - my_sec_group_01
                  - my_sec_group_02

    AvailabilityZones
        List of availability zones for the group.

    MinSize
        Minimum size of the group.

    MaxSize
        Maximum size of the group.

    DesiredCapacity
        The desired capacity of the group.

    LoadBalancerNames
        List of load balancers for the group. Once set this can not be
        updated (Amazon restriction).

    TargetGroupNames
        List of target groups for the autoscaling group. Once set this can not
        be updated (Amazon restriction).

    DefaultCooldown
        Number of seconds after a Scaling Activity completes before any further
        scaling activities can start.

    HealthCheckType
        The service you want the health status from, Amazon EC2 or Elastic Load
        Balancer (EC2 or ELB).

    HealthCheckGracePeriod
        Length of time in seconds after a new EC2 instance comes into service
        that Auto Scaling starts checking its health.

    PlacementGroup
        Physical location of your cluster placement group created in Amazon
        EC2. Once set this can not be updated (Amazon restriction).

    VPCZoneIdentifier
        A list of the subnet identifiers of the Virtual Private Cloud.

    SubnetNames
        For VPC, a list of subnet names (NOT subnet IDs) to deploy into.
        Exclusive with VPCZoneIdentifier.

    Tags
        A list of tags. Example:

        .. code-block:: yaml

            - Key: 'Key'
              Value: 'Value'
              PropagateAtLaunch: true

    TerminationPolicies
        A list of termination policies. Valid values are:

        * ``OldestInstance``
        * ``NewestInstance``
        * ``OldestLaunchConfiguration``
        * ``ClosestToNextInstanceHour``
        * ``Default``

        If no value is specified, the ``Default`` value is used.

    TerminationPolicies_from_pillar:
        name of pillar dict that contains termination policy settings.   Termination policies
        defined for this specific state will override those from pillar.

    SuspendedProcesses
        List of processes to be suspended. see
        http://docs.aws.amazon.com/AutoScaling/latest/DeveloperGuide/US_SuspendResume.html

    ScalingPolicies
        List of scaling policies.  Each policy is a dict of key-values described by
        https://boto.readthedocs.io/en/latest/ref/autoscale.html#boto.ec2.autoscale.policy.ScalingPolicy

    ScalingPolicies_from_pillar:
        name of pillar dict that contains scaling policy settings.   Scaling policies defined for
        this specific state will override those from pillar.

    ScheduledUpdateGroupActions:
        a dictionary of scheduled actions. Each key is the name of scheduled action and each value
        is dictionary of options. For example:

        .. code-block:: yaml

            - ScheduledUpdateGroupActions:
                scale_up_at_10:
                    DesiredCapacity: 4
                    MinSize: 3
                    MaxSize: 5
                    Recurrence: "0 9 * * 1-5"
                scale_down_at_7:
                    DesiredCapacity: 1
                    MinSize: 1
                    MaxSize: 1
                    Recurrence: "0 19 * * 1-5"

    ScheduledUpdateGroupActions_from_pillar:
        name of pillar dict that contains scheduled_actions settings. Scheduled actions
        for this specific state will override those from pillar.

    alarms:
        a dictionary of name->boto_cloudwatch_alarm sections to be associated with this ASG.
        All attributes should be specified except for dimension which will be
        automatically set to this ASG.

        See the :mod:`salt.states.boto_cloudwatch_alarm` state for information
        about these attributes.

        If any alarm actions include  ":self:" this will be replaced with the asg name.
        For example, alarm_actions reading "['scaling_policy:self:ScaleUp']" will
        map to the arn for this asg's scaling policy named "ScaleUp".
        In addition, any alarms that have only scaling_policy as actions will be ignored if
        min_size is equal to max_size for this ASG.

    alarms_from_pillar:
        name of pillar dict that contains alarm settings.   Alarms defined for this specific
        state will override those from pillar.

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    NotificationARN
        The AWS arn that notifications will be sent to

    NotificationARN_from_pillar
        name of the pillar dict that contains ``NotificationARN`` settings.  A
        ``notification_arn`` defined for this specific state will override the
        one from pillar.

    NotificationTypes
        A list of event names that will trigger a notification.  The list of valid
        notification types is:

        * ``autoscaling:EC2_INSTANCE_LAUNCH``
        * ``autoscaling:EC2_INSTANCE_LAUNCH_ERROR``
        * ``autoscaling:EC2_INSTANCE_TERMINATE``
        * ``autoscaling:EC2_INSTANCE_TERMINATE_ERROR``
        * ``autoscaling:TEST_NOTIFICATION``

    NotificationTypes_from_pillar
        name of the pillar dict that contains ``NotificationTypes`` settings.
        ``notification_types`` defined for this specific state will override those
        from the pillar.
    '''
    AutoScalingGroupName = AutoScalingGroupName if AutoScalingGroupName else name
    if VPCZoneIdentifier and SubnetNames:
        raise SaltInvocationError('VPCZoneIdentifier and SubnetNames are '
                                  'mutually exclusive options.')
    ret = {'name': AutoScalingGroupName, 'result': True, 'comment': '', 'changes': {}}
    if SubnetNames:
        VPCZoneIdentifier = []
        for i in SubnetNames:
            r = __salt__['boto_vpc.get_resource_id']('subnet', name=i, region=region,
                                                     key=key, keyid=keyid, profile=profile)
            if 'error' in r:
                ret['comment'] = 'Error looking up subnet ids: {0}'.format(r['error'])
                ret['result'] = False
                return ret
            if 'id' not in r:
                ret['comment'] = 'Subnet {0} does not exist.'.format(i)
                ret['result'] = False
                return ret
            VPCZoneIdentifier.append(r['id'])
    if VPCZoneIdentifier:
        vpc_id = __salt__['boto_vpc.get_subnet_association'](
            VPCZoneIdentifier,
            region,
            key,
            keyid,
            profile
        )
        vpc_id = vpc_id.get('vpc_id')
        log.debug('Auto Scaling Group {0} is associated with VPC ID {1}'
                  .format(AutoScalingGroupName, vpc_id))
    else:
        vpc_id = None
        log.debug('Auto Scaling Group {0} has no VPC Association'
                  .format(AutoScalingGroupName))

    if TargetGroupNames:
        TargetGroupARNs = []
        for tg in TargetGroupNames:
            _tg = __salt__['boto_elbv2.describe_target_group'](tg, region, key, keyid, profile)
            _arn = _tg.get('TargetGroupArn')
            if _arn:
                TargetGroupARNs.append(_arn)
    else:
        TargetGroupARNs = None

    # if launch_config is defined, manage the launch config first.
    # hash the launch_config dict to create a unique name suffix and then
    # ensure it is present
    if LaunchConfig:
        LaunchConfigurationName = LaunchConfigurationName + '-' + hashlib.md5(str(LaunchConfig)).hexdigest()
        args = {
            'name': LaunchConfigurationName,
            'region': region,
            'key': key,
            'keyid': keyid,
            'profile': profile
        }

        for index, item in enumerate(LaunchConfig):
            if 'ImageName' in item:
                ImageName = item['ImageName']
                iargs = {'ami_name': ImageName, 'region': region, 'key': key,
                         'keyid': keyid, 'profile': profile}
                image_ids = __salt__['boto_ec2.find_images'](**iargs)
                if len(image_ids):
                    LaunchConfig[index]['ImageId'] = image_ids[0]
                else:
                    LaunchConfig[index]['ImageId'] = ImageName
                del LaunchConfig[index]['ImageName']
                break

        if vpc_id:
            log.debug('Auto Scaling Group {0} is a associated with a vpc')
            # locate the security groups attribute of a launch config
            sg_index = None
            for index, item in enumerate(LaunchConfig):
                if 'SecurityGroups' in item:
                    sg_index = index
                    break
            # if security groups exist within LaunchConfig then convert
            # to group ids
            if sg_index is not None:
                log.debug('security group associations found in launch config')
                _group_ids = __salt__['boto_secgroup.convert_to_group_ids'](
                    LaunchConfig[sg_index]['SecurityGroups'], vpc_id=vpc_id,
                    region=region, key=key, keyid=keyid, profile=profile
                )
                LaunchConfig[sg_index]['SecurityGroups'] = _group_ids

        for d in LaunchConfig:
            args.update(d)
        if not __opts__['test']:
            lc_ret = __states__['boto3_lc.present'](**args)
            if lc_ret['result'] is True and lc_ret['changes']:
                if 'LaunchConfig' not in ret['changes']:
                    ret['changes']['LaunchConfig'] = {}
                ret['changes']['LaunchConfig'] = lc_ret['changes']

    asg = __salt__['boto3_asg.get_config'](AutoScalingGroupName, region, key, keyid, profile)
    TerminationPolicies = _determine_termination_policies(
        TerminationPolicies,
        TerminationPolicies_from_pillar
    )
    ScalingPolicies = _determine_scaling_policies(
        ScalingPolicies,
        ScalingPolicies_from_pillar
    )
    ScheduledUpdateGroupActions = _determine_scheduled_actions(
        ScheduledUpdateGroupActions,
        ScheduledUpdateGroupActions_from_pillar
    )
    if asg is None:
        ret['result'] = False
        ret['comment'] = 'Failed to check autoscale group existence.'
    elif not asg:
        if __opts__['test']:
            msg = 'Autoscale group set to be created.'
            ret['comment'] = msg
            ret['result'] = None
            return ret
        NotificationARN, NotificationTypes = _determine_notification_info(
            NotificationARN,
            NotificationARN_from_pillar,
            NotificationTypes,
            NotificationTypes_from_pillar
        )
        created = __salt__['boto3_asg.create'](AutoScalingGroupName, LaunchConfigurationName,
                                              AvailabilityZones, MinSize, MaxSize, DesiredCapacity,
                                              LoadBalancerNames, TargetGroupARNs, DefaultCooldown,
                                              HealthCheckType, HealthCheckGracePeriod,
                                              PlacementGroup, VPCZoneIdentifier, Tags,
                                              TerminationPolicies, SuspendedProcesses,
                                              ScalingPolicies, ScheduledUpdateGroupActions,
                                              NotificationARN, NotificationTypes,
                                              region, key, keyid, profile)
        if created:
            ret['changes']['old'] = None
            asg = __salt__['boto3_asg.get_config'](name, region, key, keyid,
                                                  profile)
            ret['changes']['new'] = asg
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create autoscale group'
    else:
        need_update = False
        # If any of these attributes can't be modified after creation
        # time, we should remove them from the dict.
        if ScalingPolicies:
            for policy in ScalingPolicies:
                if 'MinAdjustmentStep' not in policy:
                    policy['MinAdjustmentStep'] = None
        if ScheduledUpdateGroupActions:
            for s_name, action in six.iteritems(ScheduledUpdateGroupActions):
                if 'EndTime' not in action:
                    action['EndTime'] = None
        config = {
            'LaunchConfigurationName': LaunchConfigurationName,
            'AvailabilityZones': AvailabilityZones,
            'MinSize': MinSize,
            'MaxSize': MaxSize,
            'DesiredCapacity': DesiredCapacity,
            'DefaultCooldown': DefaultCooldown,
            'HealthCheckType': HealthCheckType,
            'HealthCheckGracePeriod': HealthCheckGracePeriod,
            'VPCZoneIdentifier': VPCZoneIdentifier,
            'LoadBalancerNames': LoadBalancerNames,
            'TargetGroupARNs': TargetGroupARNs,
            'Tags': Tags,
            'TerminationPolicies': TerminationPolicies,
            'SuspendedProcesses': SuspendedProcesses,
            'ScalingPolicies': ScalingPolicies,
            'ScheduledUpdateGroupActions': ScheduledUpdateGroupActions
        }
        #ensure that we reset TerminationPolicies to default if none are specified
        if not TerminationPolicies:
            config['TerminationPolicies'] = ['Default']
        if LoadBalancerNames is None:
            config['LoadBalancerNames'] = []
        if TargetGroupARNs is None:
            config['TargetGroupARNs'] = []
        if SuspendedProcesses is None:
            config['SuspendedProcesses'] = []
        # ensure that we delete ScalingPolicies if none are specified
        if ScalingPolicies is None:
            config['ScalingPolicies'] = []
        # ensure that we delete ScalingPolicies if none are specified
        if ScheduledUpdateGroupActions is None:
            config['ScheduledUpdateGroupActions'] = {}
        # allow defaults on StartTime
        for s_name, action in six.iteritems(ScheduledUpdateGroupActions):
            if 'StartTime' not in action:
                asg_action = asg['ScheduledUpdateGroupActions'].get(s_name, {})
                if 'StartTime' in asg_action:
                    del asg_action['StartTime']
        proposed = {}
        # note: do not loop using "key, value" - this can modify the value of
        # the aws access key
        for asg_property, value in six.iteritems(config):
            # Only modify values being specified; introspection is difficult
            # otherwise since it's hard to track default values, which will
            # always be returned from AWS.
            if value is None:
                continue
            value = _ordered(value)
            if asg_property in asg:
                _value = _ordered(asg[asg_property])
                if not value == _value:
                    log_msg = '{0} asg_property differs from {1}'
                    log.debug(log_msg.format(value, _value))
                    proposed.setdefault('old', {}).update({asg_property: _value})
                    proposed.setdefault('new', {}).update({asg_property: value})
                    need_update = True
        if need_update:
            if __opts__['test']:
                msg = 'Autoscale group set to be updated.'
                ret['comment'] = msg
                ret['result'] = None
                ret['changes'] = proposed
                return ret
            # add in alarms
            NotificationARN, NotificationTypes = _determine_notification_info(
                NotificationARN,
                NotificationARN_from_pillar,
                NotificationTypes,
                NotificationTypes_from_pillar
            )
            updated, msg = __salt__['boto3_asg.update'](
                AutoScalingGroupName,
                LaunchConfigurationName,
                AvailabilityZones,
                MinSize,
                MaxSize,
                DesiredCapacity=DesiredCapacity,
                DefaultCooldown=DefaultCooldown,
                HealthCheckType=HealthCheckType,
                HealthCheckGracePeriod=HealthCheckGracePeriod,
                PlacementGroup=PlacementGroup,
                VPCZoneIdentifier=VPCZoneIdentifier,
                Tags=Tags,
                TerminationPolicies=TerminationPolicies,
                SuspendedProcesses=SuspendedProcesses,
                ScalingPolicies=ScalingPolicies,
                ScheduledUpdateGroupActions=ScheduledUpdateGroupActions,
                NotificationARN=NotificationARN,
                NotificationTypes=NotificationTypes,
                region=region,
                key=key,
                keyid=keyid,
                profile=profile
            )
            if asg['LaunchConfigurationName'] != LaunchConfigurationName:
                # delete the old LaunchConfigurationName
                deleted = __salt__['boto3_asg.delete_launch_configuration'](
                    asg['LaunchConfigurationName'],
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile
                )
                if deleted:
                    if 'LaunchConfig' not in ret['changes']:
                        ret['changes']['LaunchConfig'] = {}
                    ret['changes']['LaunchConfig']['deleted'] = asg['LaunchConfigurationName']
            if asg['LoadBalancerNames'] != config['LoadBalancerNames']:
                attach_lb = [t for t in config['LoadBalancerNames'] if t not in asg['LoadBalancerNames']]
                detach_lb = [t for t in asg['LoadBalancerNames'] if t not in config['LoadBalancerNames']]
                __salt__['boto3_asg.update_asg_load_balancers'](
                    AutoScalingGroupName,
                    attach=attach_lb,
                    detach=detach_lb,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile
                )
            if asg['TargetGroupARNs'] != config['TargetGroupARNs']:
                desired_tg = config['TargetGroupARNs']
                attach_tg = [t for t in desired_tg if t not in asg['TargetGroupARNs']]
                detach_tg = [t for t in desired_tg if t not in config['TargetGroupARNs']]
                __salt__['boto3_asg.update_asg_target_groups'](
                    AutoScalingGroupName,
                    attach=attach_tg,
                    detach=detach_tg,
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile
                )
            if updated:
                ret['changes']['old'] = asg
                asg = __salt__['boto3_asg.get_config'](AutoScalingGroupName, region, key, keyid,
                                                      profile)
                ret['changes']['new'] = asg
                ret['comment'] = 'Updated autoscale group.'
            else:
                ret['result'] = False
                ret['comment'] = msg
        else:
            ret['comment'] = 'Autoscale group present.'
    # add in alarms
    _ret = _alarms_present(
        AutoScalingGroupName, MinSize == MaxSize, alarms, alarms_from_pillar, region, key,
        keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _determine_termination_policies(TerminationPolicies, TerminationPolicies_from_pillar):
    '''
    helper method for present.  ensure that TerminationPolicies are set
    '''
    pillar_termination_policies = copy.deepcopy(
        __salt__['config.option'](TerminationPolicies_from_pillar, [])
    )
    if not TerminationPolicies and len(pillar_termination_policies) > 0:
        TerminationPolicies = pillar_termination_policies
    return TerminationPolicies


def _determine_scaling_policies(ScalingPolicies, ScalingPolicies_from_pillar):
    '''
    helper method for present.  ensure that ScalingPolicies are set
    '''
    pillar_scaling_policies = copy.deepcopy(
        __salt__['config.option'](ScalingPolicies_from_pillar, {})
    )
    if not ScalingPolicies and len(pillar_scaling_policies) > 0:
        ScalingPolicies = pillar_scaling_policies
    return ScalingPolicies


def _determine_scheduled_actions(ScheduledUpdateGroupActions, ScheduledUpdateGroupActions_from_pillar):
    '''
    helper method for present,  ensure scheduled actions are setup
    '''
    tmp = copy.deepcopy(
        __salt__['config.option'](ScheduledUpdateGroupActions_from_pillar, {})
    )
    # merge with data from state
    if ScheduledUpdateGroupActions:
        tmp = dictupdate.update(tmp, ScheduledUpdateGroupActions)
    return tmp


def _determine_notification_info(NotificationARN,
                                 NotificationARN_from_pillar,
                                 NotificationTypes,
                                 NotificationTypes_from_pillar):
    '''
    helper method for present.  ensure that notification_configs are set
    '''
    pillar_arn_list = copy.deepcopy(
        __salt__['config.option'](NotificationARN_from_pillar, {})
    )
    pillar_arn = None
    if len(pillar_arn_list) > 0:
        pillar_arn = pillar_arn_list[0]
    pillar_notification_types = copy.deepcopy(
        __salt__['config.option'](NotificationTypes_from_pillar, {})
    )
    arn = NotificationARN if NotificationARN else pillar_arn
    types = NotificationTypes if NotificationTypes else pillar_notification_types
    return (arn, types)


def _alarms_present(name, min_size_equals_max_size, alarms, alarms_from_pillar, region, key, keyid, profile):
    '''
    helper method for present.  ensure that cloudwatch_alarms are set
    '''
    # load data from alarms_from_pillar
    tmp = copy.deepcopy(__salt__['config.option'](alarms_from_pillar, {}))
    # merge with data from alarms
    if alarms:
        tmp = dictupdate.update(tmp, alarms)
    # set alarms, using boto_cloudwatch_alarm.present
    merged_return_value = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    for _, info in six.iteritems(tmp):
        # add asg to name and description
        info['name'] = name + ' ' + info['name']
        info['attributes']['description'] = name + ' ' + info['attributes']['description']
        # add dimension attribute
        if 'dimensions' not in info['attributes']:
            info['attributes']['dimensions'] = {'AutoScalingGroupName': [name]}
        scaling_policy_actions_only = True
        # replace ":self:" with our name
        for action_type in ['alarm_actions', 'insufficient_data_actions', 'ok_actions']:
            if action_type in info['attributes']:
                new_actions = []
                for action in info['attributes'][action_type]:
                    if 'scaling_policy' not in action:
                        scaling_policy_actions_only = False
                    if ':self:' in action:
                        action = action.replace(':self:', ':{0}:'.format(name))
                    new_actions.append(action)
                info['attributes'][action_type] = new_actions
        # skip alarms that only have actions for scaling policy, if min_size == max_size for this ASG
        if scaling_policy_actions_only and min_size_equals_max_size:
            continue
        # set alarm
        kwargs = {
            'name': info['name'],
            'attributes': info['attributes'],
            'region': region,
            'key': key,
            'keyid': keyid,
            'profile': profile,
        }
        results = __states__['boto_cloudwatch_alarm.present'](**kwargs)
        if not results['result']:
            merged_return_value['result'] = False
        if results.get('changes', {}) != {}:
            merged_return_value['changes'][info['name']] = results['changes']
        if 'comment' in results:
            merged_return_value['comment'] += results['comment']
    return merged_return_value


def _ordered(obj):
    if isinstance(obj, (list, tuple)):
        return sorted(_ordered(x) for x in obj)
    elif isinstance(obj, dict):
        return dict((six.text_type(k) if isinstance(k, six.string_types) else k, _ordered(v)) for k, v in obj.items())
    elif isinstance(obj, six.string_types):
        return six.text_type(obj)
    return obj
