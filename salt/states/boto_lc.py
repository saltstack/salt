# -*- coding: utf-8 -*-
'''
Manage Launch Configurations

.. versionadded:: 2014.7.0

Create and destroy Launch Configurations. Be aware that this interacts with
Amazon's services, and so may incur charges.

A limitation of this module is that you can not modify launch configurations
once they have been created. If a launch configuration with the specified name
exists, this module will always report success, even if the specified
configuration doesn't match. This is due to a limitation in Amazon's launch
configuration API, as it only allows launch configurations to be created and
deleted.

Also note that a launch configuration that's in use by an autoscale group can
not be deleted until the autoscale group is no longer using it. This may affect
the way in which you want to order your states.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit autoscale credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    asg.keyid: GKTADJGHEIQSXMKKRBJ08H
    asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

Credential information is shared with autoscale groups as launch configurations
and autoscale groups are completely dependent on each other.

.. code-block:: yaml

    Ensure mylc exists:
      boto_lc.present:
        - name: mylc
        - image_id: ami-0b9c9f62
        - key_name: mykey
        - security_groups:
            - mygroup
        - instance_type: m1.small
        - instance_monitoring: true
        - block_device_mappings:
            - '/dev/sda1':
                size: 20
        - cloud_init:
            scripts:
              'run_salt.sh': |
                #!/bin/bash

                add-apt-repository -y ppa:saltstack/salt
                apt-get update
                apt-get install -y salt-minion
                salt-call state.highstate
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars.
    Ensure mylc exists:
      boto_lc.present:
        - name: mylc
        - image_id: ami-0b9c9f62
        - profile: myprofile

    # Passing in a profile.
    Ensure mylc exists:
      boto_lc.present:
        - name: mylc
        - image_id: ami-0b9c9f62
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1
'''
from __future__ import absolute_import
from salt.exceptions import SaltInvocationError


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_lc' if 'boto_asg.exists' in __salt__ else False


def present(
        name,
        image_id,
        key_name=None,
        security_groups=None,
        user_data=None,
        cloud_init=None,
        instance_type='m1.small',
        kernel_id=None,
        ramdisk_id=None,
        block_device_mappings=None,
        instance_monitoring=False,
        spot_price=None,
        instance_profile_name=None,
        ebs_optimized=False,
        associate_public_ip_address=None,
        volume_type=None,
        delete_on_termination=True,
        iops=None,
        use_block_device_types=False,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the launch configuration exists.

    name
        Name of the launch configuration.

    image_id
        AMI to use for instances. AMI must exist or creation of the launch
        configuration will fail.

    key_name
        Name of the EC2 key pair to use for instances. Key must exist or
        creation of the launch configuration will fail.

    security_groups
        List of Names or security group id’s of the security groups with which
        to associate the EC2 instances or VPC instances, respectively. Security
        groups must exist, or creation of the launch configuration will fail.

    user_data
        The user data available to launched EC2 instances.

    cloud_init
        A dict of cloud_init configuration. Currently supported values:
        scripts, cloud-config. Mutually exclusive with user_data.

    instance_type
        The instance type. ex: m1.small.

    kernel_id
        The kernel id for the instance.

    ramdisk_id
        The RAM disk ID for the instance.

    block_device_mappings
        A dict of block device mappings.

    instance_monitoring
        Whether instances in group are launched with detailed monitoring.

    spot_price
        The spot price you are bidding. Only applies if you are building an
        autoscaling group with spot instances.

    instance_profile_name
        The name or the Amazon Resource Name (ARN) of the instance profile
        associated with the IAM role for the instance. Instance profile must
        exist or the creation of the launch configuration will fail.

    ebs_optimized
        Specifies whether the instance is optimized for EBS I/O (true) or not
        (false).

    associate_public_ip_address
        Used for Auto Scaling groups that launch instances into an Amazon
        Virtual Private Cloud. Specifies whether to assign a public IP address
        to each instance launched in a Amazon VPC.

    volume_type
        Undocumented in boto.

    delete_on_termination
        Undocumented in boto.

    iops
        Undocumented in boto.

    use_block_device_types
        Undocumented in boto.

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
    if user_data and cloud_init:
        raise SaltInvocationError('user_data and cloud_init are mutually'
                                  ' exclusive options.')
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_asg.launch_configuration_exists'](name, region,
                                                              key, keyid,
                                                              profile)
    if not exists:
        if __opts__['test']:
            msg = 'Launch configuration set to be created.'
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if cloud_init:
            user_data = __salt__['boto_asg.get_cloud_init_mime'](cloud_init)
        # TODO: Ensure image_id, key_name, security_groups and instance_profile
        # exist, or throw an invocation error.
        created = __salt__['boto_asg.create_launch_configuration'](
            name, image_id, key_name, security_groups, user_data,
            instance_type, kernel_id, ramdisk_id, block_device_mappings,
            instance_monitoring, spot_price, instance_profile_name,
            ebs_optimized, associate_public_ip_address, volume_type,
            delete_on_termination, iops, use_block_device_types, region, key,
            keyid, profile)
        if created:
            ret['changes']['old'] = None
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create launch configuration.'
    else:
        ret['comment'] = 'Launch configuration present.'
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the named launch configuration is deleted.

    name
        Name of the launch configuration.

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
    exists = __salt__['boto_asg.launch_configuration_exists'](name, region,
                                                              key, keyid,
                                                              profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'Launch configuration set to be deleted.'
            ret['result'] = None
            return ret
        deleted = __salt__['boto_asg.delete_launch_configuration'](
            name, region, key, keyid, profile)
        if deleted:
            ret['changes']['old'] = name
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted launch configuration.'
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete launch configuration.'
    else:
        ret['comment'] = 'Launch configuration does not exist.'
    return ret
