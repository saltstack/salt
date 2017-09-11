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
      boto3_lc.present:
        - LaunchConfigurationName: mylc
        - ImageId: ami-0b9c9f62
        - KeyName: mykey
        - SecurityGroups:
            - mygroup
        - InstanceType: m1.small
        - InstanceMonitoring: true
        - BlockDeviceMappings:
            - '/dev/sda1':
                VolumeSize: 20
                VolumeType: 'io1'
                Iops: 220
                DeleteOnTermination: true
        - CloudInit:
            boothooks:
              'disable-master.sh': |
                #!/bin/bash
                echo "manual" > /etc/init/salt-master.override
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
      boto3_lc.present:
        - LaunchConfigurationName: mylc
        - ImageId: ami-0b9c9f62
        - profile: myprofile

    # Passing in a profile.
    Ensure mylc exists:
      boto3_lc.present:
        - LaunchConfigurationName: mylc
        - ImageId: ami-0b9c9f62
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
    return 'boto3_lc' if 'boto3_asg.exists' in __salt__ else False


def present(name,
        ImageId,
        LaunchConfigurationName=None,
        KeyName=None,
        VpcId=None,
        VpcName=None,
        SecurityGroups=None,
        UserData=None,
        CloudInit=None,
        InstanceType='m1.small',
        KernelId=None,
        RamdiskId=None,
        BlockDeviceMappings=None,
        InstanceMonitoring=False,
        SpotPrice=None,
        IamInstanceProfile=None,
        EbsOptimized=False,
        AssociatePublicIpAddress=False,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the launch configuration exists.

    name
        The name of the state definition.  This will be used as the 'CallerReference' param when
        creating the launch configuration to help ensure idempotency.

    LaunchConfigurationName
        Name of the launch configuration.

    ImageId
        AMI to use for instances. AMI must exist or creation of the launch
        configuration will fail.

    KeyName
        Name of the EC2 key pair to use for instances. Key must exist or
        creation of the launch configuration will fail.

    VpcId
        The VPC id where the security groups are defined. Only necessary when
        using named security groups that exist outside of the default VPC.
        Mutually exclusive with VpcName.

    VpcName
        Name of the VPC where the security groups are defined. Only Necessary
        when using named security groups that exist outside of the default VPC.
        Mutually exclusive with VpcId.

    SecurityGroups
        List of Names or security group id’s of the security groups with which
        to associate the EC2 instances or VPC instances, respectively. Security
        groups must exist, or creation of the launch configuration will fail.

    UserData
        The user data available to launched EC2 instances.

    CloudInit
        A dict of CloudInit configuration. Currently supported values:
        scripts, cloud-config. Mutually exclusive with UserData.

    InstanceType
        The instance type. ex: m1.small.

    KernelId
        The kernel id for the instance.

    RamdiskId
        The RAM disk ID for the instance.

    BlockDeviceMappings
        A dict of block device mappings that contains a dict
        with VolumeType, DeleteOnTermination, Iops, VolumeSize, Encrypted,
        snapshot_id.

        VolumeType
            Indicates what volume type to use. Valid values are standard, io1, gp2.
            Default is standard.

        DeleteOnTermination
            Indicates whether to delete the volume on instance termination (true) or
            not (false).

        Iops
            For Provisioned IOPS (SSD) volumes only. The number of I/O operations per
            second (IOPS) to provision for the volume.

        VolumeSize
            Desired volume size (in GiB).

        Encrypted
            Indicates whether the volume should be encrypted. Encrypted EBS volumes must
            be attached to instances that support Amazon EBS encryption. Volumes that are
            created from encrypted snapshots are automatically encrypted. There is no way
            to create an encrypted volume from an unencrypted snapshot or an unencrypted
            volume from an encrypted snapshot.

    InstanceMonitoring
        Whether instances in group are launched with detailed monitoring.

    SpotPrice
        The spot price you are bidding. Only applies if you are building an
        autoscaling group with spot instances.

    IamInstanceProfile
        The name or the Amazon Resource Name (ARN) of the instance profile
        associated with the IAM role for the instance. Instance profile must
        exist or the creation of the launch configuration will fail.

    EbsOptimized
        Specifies whether the instance is optimized for EBS I/O (true) or not
        (false).

    AssociatePublicIpAddress
        Used for Auto Scaling groups that launch instances into an Amazon
        Virtual Private Cloud. Specifies whether to assign a public IP address
        to each instance launched in a Amazon VPC.

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
    LaunchConfigurationName = LaunchConfigurationName if LaunchConfigurationName else name
    if UserData and CloudInit:
        raise SaltInvocationError('UserData and CloudInit are mutually'
                                  ' exclusive options.')
    ret = {'name': LaunchConfigurationName, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto3_asg.launch_configuration_exists'](LaunchConfigurationName,
                                                              region=region,
                                                              key=key,
                                                              keyid=keyid,
                                                              profile=profile)
    if not exists:
        if __opts__['test']:
            msg = 'Launch configuration set to be created.'
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if CloudInit:
            UserData = __salt__['boto_asg.get_cloud_init_mime'](CloudInit)
        # TODO: Ensure ImageId, KeyName, SecurityGroups and IamInstanceProfile
        # exist, or throw an invocation error.
        created = __salt__['boto3_asg.create_launch_configuration'](
            LaunchConfigurationName,
            ImageId,
            KeyName=KeyName,
            VpcId=VpcId,
            VpcName=VpcName,
            SecurityGroups=SecurityGroups,
            UserData=UserData,
            InstanceType=InstanceType,
            KernelId=KernelId,
            RamdiskId=RamdiskId,
            BlockDeviceMappings=BlockDeviceMappings,
            InstanceMonitoring=InstanceMonitoring,
            SpotPrice=SpotPrice,
            IamInstanceProfile=IamInstanceProfile,
            EbsOptimized=EbsOptimized,
            AssociatePublicIpAddress=AssociatePublicIpAddress,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile)
        if created:
            ret['changes']['old'] = None
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create launch configuration.'
    else:
        ret['comment'] = 'Launch configuration present.'
    return ret


def absent(name,
        LaunchConfigurationName=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the named launch configuration is deleted.

    name
        The name of the state definition.  This will be used as the 'CallerReference' param when
        deleting the launch configuration to help ensure idempotency.

    LaunchConfigurationName
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
    LaunchConfigurationName = LaunchConfigurationName if LaunchConfigurationName else name
    ret = {'name': LaunchConfigurationName, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto3_asg.launch_configuration_exists'](LaunchConfigurationName,
                                                              region=region,
                                                              key=key,
                                                              keyid=keyid,
                                                              profile=profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'Launch configuration set to be deleted.'
            ret['result'] = None
            return ret
        deleted = __salt__['boto3_asg.delete_launch_configuration'](
                                                              LaunchConfigurationName,
                                                              region=region,
                                                              key=key,
                                                              keyid=keyid,
                                                              profile=profile)
        if deleted:
            ret['changes']['old'] = LaunchConfigurationName
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted launch configuration.'
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete launch configuration.'
    else:
        ret['comment'] = 'Launch configuration does not exist.'
    return ret
