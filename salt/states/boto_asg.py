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
configuration is necessary. More Information available at::

   http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

If IAM roles are not used you need to specify them either in a pillar or
in the minion's config file::

    asg.keyid: GKTADJGHEIQSXMKKRBJ08H
    asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify key, keyid and region via a profile, either
as a passed in dict, or as a string to pull from pillars or minion config:

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
            ----------
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
'''

# Import Python libs
import hashlib
import logging
import re

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
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the autoscale group exists.

    name
        Name of the autoscale group.

    launch_config_name
    Name of the launch config to use for the group.  Or, if
    launch_config is specified, this will be the launch config
    name's prefix.  (see below)

    launch_config
    A dictionary of launch config attributes.  If specified, a
    launch config will be used or created, matching this set
    of attributes, and the autoscale group will be set to use
    that launch config.  The launch config name will be the
    launch_config_name followed by a hyphen followed by a hash
    of the launch_config dict contents.

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
            - key: 'key'
              value: 'value'
              propagate_at_launch: true

    termination_policies
        A list of termination policies. Valid values are: “OldestInstance”,
        “NewestInstance”, “OldestLaunchConfiguration”,
        “ClosestToNextInstanceHour”, “Default”. If no value is specified, the
        “Default” value is used.

    suspended_processes
        List of processes to be suspended. see
        http://docs.aws.amazon.com/AutoScaling/latest/DeveloperGuide/US_SuspendResume.html

    scaling_policies
        List of scaling policies.  Each policy is a dict of key-values described by
        http://boto.readthedocs.org/en/latest/ref/autoscale.html#boto.ec2.autoscale.policy.ScalingPolicy

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
    if vpc_zone_identifier:
        vpc_id = __salt__['boto_vpc.get_subnet_association'](vpc_zone_identifier, region, key, keyid, profile)
        log.debug('Auto Scaling Group {0} is associated with VPC ID {1}'
                  .format(name, vpc_id))
    else:
        vpc_id = None
        log.debug('Auto Scaling Group {0} has no VPC Association'
                  .format(name))
    # if launch_config is defined, manage the launch config first.
    # hash the launch_config dict to create a unique name suffix and then
    # ensure it is present
    if launch_config and not __opts__['test']:
        launch_config_name = launch_config_name + "-" + hashlib.md5(str(launch_config)).hexdigest()
        args = {
            'name':  launch_config_name,
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
                launch_config[sg_index]['security_groups'] = _convert_to_group_ids(launch_config[sg_index]['security_groups'], vpc_id, region, key, keyid, profile)

        for d in launch_config:
            args.update(d)
        lc_ret = __salt__["state.single"]('boto_lc.present', **args)
        lc_ret = lc_ret.values()[0]
        if lc_ret["result"] is True:
            if "launch_config" not in ret["changes"]:
                ret["changes"]["launch_config"] = {}
            ret["changes"]["launch_config"] = lc_ret["changes"]

    asg = __salt__['boto_asg.get_config'](name, region, key, keyid, profile)
    if asg is None:
        ret['result'] = False
        ret['comment'] = 'Failed to check autoscale group existence.'
    elif not asg:
        if __opts__['test']:
            msg = 'Autoscale group set to be created.'
            ret['comment'] = msg
            ret['result'] = None
            return ret
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
                                              scaling_policies, region,
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
                if "min_adjustment_step" not in policy:
                    policy["min_adjustment_step"] = None
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
            "scaling_policies": scaling_policies,
        }
        if suspended_processes is None:
            config["suspended_processes"] = []
        # ensure that we delete scaling_policies if none are specified
        if scaling_policies is None:
            config["scaling_policies"] = []
        # note: do not loop using "key, value" - this can modify the value of
        # the aws access key
        for asg_property, value in config.iteritems():
            # Only modify values being specified; introspection is difficult
            # otherwise since it's hard to track default values, which will
            # always be returned from AWS.
            if value is None:
                continue
            if asg_property in asg:
                _value = asg[asg_property]
                if not _recursive_compare(value, _value):
                    need_update = True
                    break
        if need_update:
            if __opts__['test']:
                msg = 'Autoscale group set to be updated.'
                ret['comment'] = msg
                ret['result'] = None
                return ret
            updated = __salt__['boto_asg.update'](name, launch_config_name,
                                                  availability_zones, min_size,
                                                  max_size, desired_capacity,
                                                  load_balancers,
                                                  default_cooldown,
                                                  health_check_type,
                                                  health_check_period,
                                                  placement_group,
                                                  vpc_zone_identifier, tags,
                                                  termination_policies,
                                                  suspended_processes,
                                                  scaling_policies, region,
                                                  key, keyid, profile)
            if asg["launch_config_name"] != launch_config_name:
                # delete the old launch_config_name
                deleted = __salt__['boto_asg.delete_launch_configuration'](asg["launch_config_name"], region, key, keyid, profile)
                if deleted:
                    if "launch_config" not in ret["changes"]:
                        ret["changes"]["launch_config"] = {}
                    ret["changes"]["launch_config"]["deleted"] = asg["launch_config_name"]
            if updated:
                ret['changes']['old'] = asg
                asg = __salt__['boto_asg.get_config'](name, region, key, keyid,
                                                      profile)
                ret['changes']['new'] = asg
                ret['comment'] = 'Updated autoscale group.'
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to update autoscale group.'
        else:
            ret['comment'] = 'Autoscale group present.'
    return ret


def _convert_to_group_ids(groups, vpc_id, region, key, keyid, profile):
    '''
    given a list of security groups _convert_to_group_ids will convert all
    list items in the given list to security group ids
    '''
    log.debug('security group contents {0} pre-conversion'.format(groups))
    group_ids = []
    for group in groups:
        if re.match('sg-.*', group):
            log.debug('group {0} is a group id. get_group_id not called.'
                      .format(group))
            group_ids.append(group)
        else:
            log.debug('calling boto_secgroup.get_group_id for'
                      ' group name {0}'.format(group))
            group_id = __salt__['boto_secgroup.get_group_id'](group, vpc_id, region, key, keyid, profile)
            log.debug('group name {0} has group id {1}'.format(group, group_id))
            group_ids.append(str(group_id))
    log.debug('security group contents {0} post-conversion'.format(group_ids))
    return group_ids


def _recursive_compare(v1, v2):
    "return v1 == v2.  compares list, dict, OrderedDict, recursively"
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
        if sorted(v1.keys()) != sorted(v2.keys()):
            return False
        for k in v1.keys():
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
        profile=None):
    '''
    Ensure the named autoscale group is deleted.

    name
        Name of the autoscale group.

    force
        Force deletion of autoscale group.

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
            return ret
        deleted = __salt__['boto_asg.delete'](name, force, region, key, keyid,
                                              profile)
        if deleted:
            ret['changes']['old'] = asg
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted autoscale group.'
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete autoscale group.'
    else:
        ret['comment'] = 'Autoscale group does not exist.'
    return ret
