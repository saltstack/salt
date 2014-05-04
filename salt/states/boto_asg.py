# -*- coding: utf-8 -*-
'''
Manage Autoscale Groups
=======================

.. versionadded:: Helium

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
        desired_capacity=None,
        load_balancers=None,
        default_cooldown=None,
        health_check_type=None,
        health_check_period=None,
        placement_group=None,
        vpc_zone_identifier=None,
        tags=None,
        termination_policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the autoscale group exists.

    name
        Name of the autoscale group.

    launch_config_name
        Name of the launch config to use for the group.

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
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    asg = __salt__['boto_asg.get_config'](name, region, key, keyid, profile)
    if asg is not None and not asg:
        if __opts__['test']:
            msg = 'Autoscale group set to be created.'
            ret['comment'] = msg
            return ret
        created = __salt__['boto_asg.create'](name, launch_config_name,
                                              availability_zones, min_size,
                                              max_size, desired_capacity,
                                              load_balancers, default_cooldown,
                                              health_check_type,
                                              health_check_period,
                                              placement_group,
                                              vpc_zone_identifier, tags,
                                              termination_policies, region,
                                              key, keyid, profile)
        if created:
            ret['result'] = True
            ret['changes']['old'] = None
            asg = __salt__['boto_asg.get_config'](name, region, key, keyid,
                                                  profile)
            ret['changes']['new'] = asg
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create autoscale group'
    elif asg:
        need_update = False
        # If any of these attributes can't be modified after creation
        # time, we should remove them from the dict.
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
            'termination_policies': termination_policies
        }
        for key, value in config.iteritems():
            if not value:
                continue
            if key in asg:
                _value = asg[key]
                if isinstance(value, list):
                    _value.sort()
                    value.sort()
                if _value != value:
                    need_update = True
        if need_update:
            if __opts__['test']:
                msg = 'Autoscale group set to be updated.'
                ret['comment'] = msg
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
                                                  termination_policies, region,
                                                  key, keyid, profile)
            if updated:
                ret['result'] = True
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
    elif asg is None:
        ret['result'] = False
        ret['comment'] = 'Failed to check autoscale group existence.'
    return ret


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
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    asg = __salt__['boto_asg.get_config'](name, region, key, keyid, profile)
    if asg is not None and asg:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Autoscale group set to be deleted.'
            return ret
        deleted = __salt__['boto_asg.delete'](name, force, region, key, keyid,
                                              profile)
        if deleted:
            ret['result'] = True
            ret['changes']['old'] = asg
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted autoscale group.'
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete autoscale group.'
    elif asg is None:
        ret['result'] = False
        ret['comment'] = 'Failed to check autoscale group existence.'
    else:
        ret['comment'] = 'Autoscale group does not exist.'
    return ret
