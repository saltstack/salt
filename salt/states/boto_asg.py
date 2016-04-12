# -*- coding: utf-8 -*-
'''
Manage Autoscale Groups
=======================

.. versionadded:: 2014.7.0

Create and destroy autoscale groups. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses boto, which can be installed via package, or pip.

This module accepts explicit autoscale credentials but can also utilize
IAM roles assigned to the instance trough Instance Profiles. Dynamic
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
      boto_asg.present:
        - name: myasg
        - launch_config_name: mylc
        - availability_zones:
          - us-east-1a
          - us-east-1b
        - min_size: 1
        - max_size: 1
        - desired_capacity: 1
        - load_balancers:
          - myelb
        - suspended_processes:
            - AddToLoadBalancer
            - AlarmNotification
        - scaling_policies
            - adjustment_type: ChangeInCapacity
            - as_name: api-production-iad
            - cooldown: 1800
            - min_adjustment_step: None
            - name: ScaleDown
            - scaling_adjustment: -1
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars.
    Ensure myasg exists:
      boto_asg.present:
        - name: myasg
        - launch_config_name: mylc
        - availability_zones:
          - us-east-1a
          - us-east-1b
        - min_size: 1
        - max_size: 1
        - desired_capacity: 1
        - load_balancers:
          - myelb
        - profile: myprofile

    # Passing in a profile.
    Ensure myasg exists:
      boto_asg.present:
        - name: myasg
        - launch_config_name: mylc
        - availability_zones:
          - us-east-1a
          - us-east-1b
        - min_size: 1
        - max_size: 1
        - desired_capacity: 1
        - load_balancers:
          - myelb
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    # Deleting an autoscale group with running instances.
    Ensure myasg is deleted:
      boto_asg.absent:
        - name: myasg
        # If instances exist, we must force the deletion of the asg.
        - force: True

It's possible to specify cloudwatch alarms that will be setup along with the
ASG. Note the alarm name will be the name attribute defined, plus the ASG
resource name.

.. code-block:: yaml

    Ensure myasg exists:
      boto_asg.present:
        - name: myasg
        - launch_config_name: mylc
        - availability_zones:
          - us-east-1a
          - us-east-1b
        - min_size: 1
        - max_size: 1
        - desired_capacity: 1
        - load_balancers:
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
alarms by setting overrides on the resource. Note that 'boto_asg_alarms'
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
      boto_asg.present:
        - name: myasg
        - launch_config_name: mylc
        - availability_zones:
          - us-east-1a
          - us-east-1b
        - min_size: 1
        - max_size: 1
        - desired_capacity: 1
        - load_balancers:
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

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_asg' if 'boto_asg.exists' in __salt__ else False


def present(
        name,
        launch_config_name,
        availability_zones,
        min_size,
        max_size,
        launch_config=None,
        desired_capacity=None,
        load_balancers=None,
        default_cooldown=None,
        health_check_type=None,
        health_check_period=None,
        placement_group=None,
        vpc_zone_identifier=None,
        tags=None,
        termination_policies=None,
        suspended_processes=None,
        scaling_policies=None,
        scaling_policies_from_pillar='boto_asg_scaling_policies',
        scheduled_actions=None,
        scheduled_actions_from_pillar='boto_asg_scheduled_actions',
        alarms=None,
        alarms_from_pillar='boto_asg_alarms',
        region=None,
        key=None,
        keyid=None,
        profile=None,
        notification_arn=None,
        notification_arn_from_pillar='boto_asg_notification_arn',
        notification_types=None,
        notification_types_from_pillar='boto_asg_notification_types'):
    '''
    Ensure the autoscale group exists.

    name
        Name of the autoscale group.

    launch_config_name
        Name of the launch config to use for the group.  Or, if
        ``launch_config`` is specified, this will be the launch config
        name's prefix.  (see below)

    launch_config
        A dictionary of launch config attributes.  If specified, a
        launch config will be used or created, matching this set
        of attributes, and the autoscale group will be set to use
        that launch config.  The launch config name will be the
        ``launch_config_name`` followed by a hyphen followed by a hash
        of the ``launch_config`` dict contents.

    availability_zones
        List of availability zones for the group.

    min_size
        Minimum size of the group.

    max_size
        Maximum size of the group.

    desired_capacity
        The desired capacity of the group.

    load_balancers
        List of load balancers for the group. Once set this can not be
        updated (Amazon restriction).

    default_cooldown
        Number of seconds after a Scaling Activity completes before any further
        scaling activities can start.

    health_check_type
        The service you want the health status from, Amazon EC2 or Elastic Load
        Balancer (EC2 or ELB).

    health_check_period
        Length of time in seconds after a new EC2 instance comes into service
        that Auto Scaling starts checking its health.

    placement_group
        Physical location of your cluster placement group created in Amazon
        EC2. Once set this can not be updated (Amazon restriction).

    vpc_zone_identifier
        A list of the subnet identifiers of the Virtual Private Cloud.

    tags
        A list of tags. Example:

        .. code-block:: yaml

            - key: 'key'
              value: 'value'
              propagate_at_launch: true

    termination_policies
        A list of termination policies. Valid values are:

        * ``OldestInstance``
        * ``NewestInstance``
        * ``OldestLaunchConfiguration``
        * ``ClosestToNextInstanceHour``
        * ``Default``

        If no value is specified, the ``Default`` value is used.

    suspended_processes
        List of processes to be suspended. see
        http://docs.aws.amazon.com/AutoScaling/latest/DeveloperGuide/US_SuspendResume.html

    scaling_policies
        List of scaling policies.  Each policy is a dict of key-values described by
        http://boto.readthedocs.org/en/latest/ref/autoscale.html#boto.ec2.autoscale.policy.ScalingPolicy

    scaling_policies_from_pillar:
        name of pillar dict that contains scaling policy settings.   Scaling policies defined for
        this specific state will override those from pillar.

    scheduled_actions:
        a dictionary of scheduled actions. Each key is the name of scheduled action and each value
        is dictionary of options. For example:

        .. code-block:: yaml

            - scheduled_actions:
                scale_up_at_10:
                    desired_capacity: 4
                    min_size: 3
                    max_size: 5
                    recurrence: "0 9 * * 1-5"
                scale_down_at_7:
                    desired_capacity: 1
                    min_size: 1
                    max_size: 1
                    recurrence: "0 19 * * 1-5"

    scheduled_actions_from_pillar:
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

    notification_arn
        The AWS arn that notifications will be sent to

    notification_arn_from_pillar
        name of the pillar dict that contains ``notifcation_arn`` settings.  A
        ``notification_arn`` defined for this specific state will override the
        one from pillar.

    notification_types
        A list of event names that will trigger a notification.  The list of valid
        notification types is:

        * ``autoscaling:EC2_INSTANCE_LAUNCH``
        * ``autoscaling:EC2_INSTANCE_LAUNCH_ERROR``
        * ``autoscaling:EC2_INSTANCE_TERMINATE``
        * ``autoscaling:EC2_INSTANCE_TERMINATE_ERROR``
        * ``autoscaling:TEST_NOTIFICATION``

    notification_types_from_pillar
        name of the pillar dict that contains ``notifcation_types`` settings.
        ``notification_types`` defined for this specific state will override those
        from the pillar.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if vpc_zone_identifier:
        vpc_id = __salt__['boto_vpc.get_subnet_association'](
            vpc_zone_identifier,
            region,
            key,
            keyid,
            profile
        )
        vpc_id = vpc_id.get('vpc_id')
        log.debug('Auto Scaling Group {0} is associated with VPC ID {1}'
                  .format(name, vpc_id))
    else:
        vpc_id = None
        log.debug('Auto Scaling Group {0} has no VPC Association'
                  .format(name))
    # if launch_config is defined, manage the launch config first.
    # hash the launch_config dict to create a unique name suffix and then
    # ensure it is present
    if launch_config:
        launch_config_name = launch_config_name + '-' + hashlib.md5(str(launch_config)).hexdigest()
        args = {
            'name': launch_config_name,
            'region': region,
            'key': key,
            'keyid': keyid,
            'profile': profile
        }

        if vpc_id:
            log.debug('Auto Scaling Group {0} is a associated with a vpc')
            # locate the security groups attribute of a launch config
            sg_index = None
            for index, item in enumerate(launch_config):
                if 'security_groups' in item:
                    sg_index = index
                    break
            # if security groups exist within launch_config then convert
            # to group ids
            if sg_index:
                log.debug('security group associations found in launch config')
                _group_ids = __salt__['boto_secgroup.convert_to_group_ids'](
                    launch_config[sg_index]['security_groups'], vpc_id=vpc_id,
                    region=region, key=key, keyid=keyid, profile=profile
                )
                launch_config[sg_index]['security_groups'] = _group_ids

        for d in launch_config:
            args.update(d)
        if not __opts__['test']:
            lc_ret = __states__['boto_lc.present'](**args)
            if lc_ret['result'] is True and lc_ret['changes']:
                if 'launch_config' not in ret['changes']:
                    ret['changes']['launch_config'] = {}
                ret['changes']['launch_config'] = lc_ret['changes']

    asg = __salt__['boto_asg.get_config'](name, region, key, keyid, profile)
    scaling_policies = _determine_scaling_policies(
        scaling_policies,
        scaling_policies_from_pillar
    )
    scheduled_actions = _determine_scheduled_actions(
        scheduled_actions,
        scheduled_actions_from_pillar
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
        notification_arn, notification_types = _determine_notification_info(
            notification_arn,
            notification_arn_from_pillar,
            notification_types,
            notification_types_from_pillar
        )
        created = __salt__['boto_asg.create'](name, launch_config_name,
                                              availability_zones, min_size,
                                              max_size, desired_capacity,
                                              load_balancers, default_cooldown,
                                              health_check_type,
                                              health_check_period,
                                              placement_group,
                                              vpc_zone_identifier, tags,
                                              termination_policies,
                                              suspended_processes,
                                              scaling_policies, scheduled_actions,
                                              region, notification_arn,
                                              notification_types,
                                              key, keyid, profile)
        if created:
            ret['changes']['old'] = None
            asg = __salt__['boto_asg.get_config'](name, region, key, keyid,
                                                  profile)
            ret['changes']['new'] = asg
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create autoscale group'
    else:
        need_update = False
        # If any of these attributes can't be modified after creation
        # time, we should remove them from the dict.
        if scaling_policies:
            for policy in scaling_policies:
                if 'min_adjustment_step' not in policy:
                    policy['min_adjustment_step'] = None
        if scheduled_actions:
            for s_name, action in scheduled_actions.iteritems():
                if 'end_time' not in action:
                    action['end_time'] = None
        config = {
            'launch_config_name': launch_config_name,
            'availability_zones': availability_zones,
            'min_size': min_size,
            'max_size': max_size,
            'desired_capacity': desired_capacity,
            'default_cooldown': default_cooldown,
            'health_check_type': health_check_type,
            'health_check_period': health_check_period,
            'vpc_zone_identifier': vpc_zone_identifier,
            'tags': tags,
            'termination_policies': termination_policies,
            'suspended_processes': suspended_processes,
            'scaling_policies': scaling_policies,
            'scheduled_actions': scheduled_actions
        }
        if suspended_processes is None:
            config['suspended_processes'] = []
        # ensure that we delete scaling_policies if none are specified
        if scaling_policies is None:
            config['scaling_policies'] = []
        # ensure that we delete scheduled_actions if none are specified
        if scheduled_actions is None:
            config['scheduled_actions'] = {}
        # allow defaults on start_time
        for s_name, action in scheduled_actions.iteritems():
            if 'start_time' not in action:
                asg_action = asg['scheduled_actions'].get(s_name, {})
                if 'start_time' in asg_action:
                    del asg_action['start_time']
        # note: do not loop using "key, value" - this can modify the value of
        # the aws access key
        for asg_property, value in six.iteritems(config):
            # Only modify values being specified; introspection is difficult
            # otherwise since it's hard to track default values, which will
            # always be returned from AWS.
            if value is None:
                continue
            if asg_property in asg:
                _value = asg[asg_property]
                if not _recursive_compare(value, _value):
                    log_msg = '{0} asg_property differs from {1}'
                    log.debug(log_msg.format(value, _value))
                    need_update = True
                    break
        if need_update:
            if __opts__['test']:
                msg = 'Autoscale group set to be updated.'
                ret['comment'] = msg
                ret['result'] = None
                return ret
            # add in alarms
            notification_arn, notification_types = _determine_notification_info(
                notification_arn,
                notification_arn_from_pillar,
                notification_types,
                notification_types_from_pillar
            )
            updated, msg = __salt__['boto_asg.update'](
                name,
                launch_config_name,
                availability_zones,
                min_size,
                max_size,
                desired_capacity=desired_capacity,
                load_balancers=load_balancers,
                default_cooldown=default_cooldown,
                health_check_type=health_check_type,
                health_check_period=health_check_period,
                placement_group=placement_group,
                vpc_zone_identifier=vpc_zone_identifier,
                tags=tags,
                termination_policies=termination_policies,
                suspended_processes=suspended_processes,
                scaling_policies=scaling_policies,
                scheduled_actions=scheduled_actions,
                region=region,
                notification_arn=notification_arn,
                notification_types=notification_types,
                key=key,
                keyid=keyid,
                profile=profile
            )
            if asg['launch_config_name'] != launch_config_name:
                # delete the old launch_config_name
                deleted = __salt__['boto_asg.delete_launch_configuration'](
                    asg['launch_config_name'],
                    region=region,
                    key=key,
                    keyid=keyid,
                    profile=profile
                )
                if deleted:
                    if 'launch_config' not in ret['changes']:
                        ret['changes']['launch_config'] = {}
                    ret['changes']['launch_config']['deleted'] = asg['launch_config_name']
            if updated:
                ret['changes']['old'] = asg
                asg = __salt__['boto_asg.get_config'](name, region, key, keyid,
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
        name, min_size == max_size, alarms, alarms_from_pillar, region, key,
        keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _determine_scaling_policies(scaling_policies, scaling_policies_from_pillar):
    '''
    helper method for present.  ensure that scaling_policies are set
    '''
    pillar_scaling_policies = copy.deepcopy(
        __salt__['config.option'](scaling_policies_from_pillar, {})
    )
    if not scaling_policies and len(pillar_scaling_policies) > 0:
        scaling_policies = pillar_scaling_policies
    return scaling_policies


def _determine_scheduled_actions(scheduled_actions, scheduled_actions_from_pillar):
    '''
    helper method for present,  ensure scheduled actions are setup
    '''
    tmp = copy.deepcopy(
        __salt__['config.option'](scheduled_actions_from_pillar, {})
    )
    # merge with data from state
    if scheduled_actions:
        tmp = dictupdate.update(tmp, scheduled_actions)
    return tmp


def _determine_notification_info(notification_arn,
                                 notification_arn_from_pillar,
                                 notification_types,
                                 notification_types_from_pillar):
    '''
    helper method for present.  ensure that notification_configs are set
    '''
    pillar_arn_list = copy.deepcopy(
        __salt__['config.option'](notification_arn_from_pillar, {})
    )
    pillar_arn = None
    if len(pillar_arn_list) > 0:
        pillar_arn = pillar_arn_list[0]
    pillar_notification_types = copy.deepcopy(
        __salt__['config.option'](notification_types_from_pillar, {})
    )
    arn = notification_arn if notification_arn else pillar_arn
    types = notification_types if notification_types else pillar_notification_types
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


def _recursive_compare(v1, v2):
    '''
    return v1 == v2.  compares list, dict, OrderedDict, recursively
    '''
    if isinstance(v1, list):
        if len(v1) != len(v2):
            return False
        v1.sort()
        v2.sort()
        for x, y in zip(v1, v2):
            if not _recursive_compare(x, y):
                return False
        return True
    elif isinstance(v1, dict):
        v1 = dict(v1)
        v2 = dict(v2)
        if sorted(v1) != sorted(v2):
            return False
        for k in v1:
            if not _recursive_compare(v1[k], v2[k]):
                return False
        return True
    else:
        return v1 == v2


def absent(
        name,
        force=False,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        remove_lc=False):
    '''
    Ensure the named autoscale group is deleted.

    name
        Name of the autoscale group.

    force
        Force deletion of autoscale group.

    remove_lc
        Delete the launch config as well.

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    asg = __salt__['boto_asg.get_config'](name, region, key, keyid, profile)
    if asg is None:
        ret['result'] = False
        ret['comment'] = 'Failed to check autoscale group existence.'
    elif asg:
        if __opts__['test']:
            ret['comment'] = 'Autoscale group set to be deleted.'
            ret['result'] = None
            if remove_lc:
                msg = 'Launch configuration {0} is set to be deleted.'.format(asg['launch_config_name'])
                ret['comment'] = ' '.join([ret['comment'], msg])
            return ret
        deleted = __salt__['boto_asg.delete'](name, force, region, key, keyid,
                                              profile)
        if deleted:
            if remove_lc:
                lc_deleted = __salt__['boto_asg.delete_launch_configuration'](asg['launch_config_name'],
                                                                              region,
                                                                              key,
                                                                              keyid,
                                                                              profile)
                if lc_deleted:
                    if 'launch_config' not in ret['changes']:
                        ret['changes']['launch_config'] = {}
                    ret['changes']['launch_config']['deleted'] = asg['launch_config_name']
                else:
                    ret['result'] = False
                    ret['comment'] = ' '.join([ret['comment'], 'Failed to delete launch configuration.'])
            ret['changes']['old'] = asg
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted autoscale group.'
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete autoscale group.'
    else:
        ret['comment'] = 'Autoscale group does not exist.'
    return ret
