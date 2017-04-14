# -*- coding: utf-8 -*-
'''
Manage EC2

.. versionadded:: 2015.8.0

This module provides an interface to the Elastic Compute Cloud (EC2) service
from AWS.

The below code creates a key pair:

.. code-block:: yaml

    create-key-pair:
      boto_ec2.key_present:
        - name: mykeypair
        - save_private: /root/
        - region: eu-west-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

.. code-block:: yaml

    import-key-pair:
       boto_ec2.key_present:
        - name: mykeypair
        - upload_public: 'ssh-rsa AAAA'
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

You can also use salt:// in order to define the public key.

.. code-block:: yaml

    import-key-pair:
       boto_ec2.key_present:
        - name: mykeypair
        - upload_public: salt://mybase/public_key.pub
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

The below code deletes a key pair:

.. code-block:: yaml

    delete-key-pair:
      boto_ec2.key_absent:
        - name: mykeypair
        - region: eu-west-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''

# Import Python Libs
from __future__ import absolute_import
import logging
from time import time, sleep

# Import salt libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.utils
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError, CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    if 'boto_ec2.get_key' in __salt__:
        return 'boto_ec2'
    else:
        return False


def key_present(name, save_private=None, upload_public=None, region=None,
                key=None, keyid=None, profile=None):
    '''
    Ensure key pair is present.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_ec2.get_key'](name, region, key, keyid, profile)
    log.debug('exists is {0}'.format(exists))
    if upload_public is not None and 'salt://' in upload_public:
        try:
            upload_public = __salt__['cp.get_file_str'](upload_public)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(upload_public)
            ret['result'] = False
            return ret
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        if save_private and not upload_public:
            created = __salt__['boto_ec2.create_key'](
                name, save_private, region, key, keyid, profile
            )
            if created:
                ret['result'] = True
                ret['comment'] = 'The key {0} is created.'.format(name)
                ret['changes']['new'] = created
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create key {0} '.format(name)
        elif not save_private and upload_public:
            imported = __salt__['boto_ec2.import_key'](name, upload_public,
                                                       region, key, keyid,
                                                       profile)
            if imported:
                ret['result'] = True
                ret['comment'] = 'The key {0} is created.'.format(name)
                ret['changes']['old'] = None
                ret['changes']['new'] = imported
            else:
                ret['result'] = False
                ret['comment'] = 'Could not create key {0} '.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'You can either upload or download a private key '
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} already exists'.format(name)
    return ret


def key_absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a key pair
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    exists = __salt__['boto_ec2.get_key'](name, region, key, keyid, profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'The key {0} is set to be deleted.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_ec2.delete_key'](name, region,
                                                  key, keyid,
                                                  profile)
        log.debug('exists is {0}'.format(deleted))
        if deleted:
            ret['result'] = True
            ret['comment'] = 'The key {0} is deleted.'.format(name)
            ret['changes']['old'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Could not delete key {0} '.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'The key name {0} does not exist'.format(name)
    return ret


def eni_present(
        name,
        subnet_id=None,
        subnet_name=None,
        private_ip_address=None,
        description=None,
        groups=None,
        source_dest_check=True,
        allocate_eip=None,
        arecords=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the EC2 ENI exists.

    .. versionadded:: 2016.3.0

    name
        Name tag associated with the ENI.

    subnet_id
        The VPC subnet ID the ENI will exist within.

    subnet_name
        The VPC subnet name the ENI will exist within.

    private_ip_address
        The private ip address to use for this ENI. If this is not specified
        AWS will automatically assign a private IP address to the ENI. Must be
        specified at creation time; will be ignored afterward.

    description
        Description of the key.

    groups
        A list of security groups to apply to the ENI.

    source_dest_check
        Boolean specifying whether source/destination checking is enabled on
        the ENI.

    allocate_eip
        allocate and associate an EIP to the ENI. Could be 'standard' to
        allocate Elastic IP to EC2 region or 'vpc' to get it for a
        particular VPC

        .. versionchanged:: 2016.11.0

    arecords
        A list of arecord dicts with attributes needed for the DNS add_record state.
        By default the boto_route53.add_record state will be used, which requires: name, zone, ttl, and identifier.
        See the boto_route53 state for information about these attributes.
        Other DNS modules can be called by specifying the provider keyword.
        By default, the private ENI IP address will be used, set 'public: True' in the arecord dict to use the ENI's public IP address

        .. versionadded:: 2016.3.0

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    if not salt.utils.exactly_one((subnet_id, subnet_name)):
        raise SaltInvocationError('One (but not both) of subnet_id or '
                                  'subnet_name must be provided.')
    if not groups:
        raise SaltInvocationError('groups is a required argument.')
    if not isinstance(groups, list):
        raise SaltInvocationError('groups must be a list.')
    if not isinstance(source_dest_check, bool):
        raise SaltInvocationError('source_dest_check must be a bool.')
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    r = __salt__['boto_ec2.get_network_interface'](
        name=name, region=region, key=key, keyid=keyid, profile=profile
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Error when attempting to find eni: {0}.'.format(
            r['error']['message']
        )
        return ret
    if not r['result']:
        if __opts__['test']:
            ret['comment'] = 'ENI is set to be created.'
            if allocate_eip:
                ret['comment'] = ' '.join([ret['comment'], 'An EIP is set to be allocated/assocaited to the ENI.'])
            if arecords:
                ret['comment'] = ' '.join([ret['comment'], 'A records are set to be created.'])
            ret['result'] = None
            return ret
        result_create = __salt__['boto_ec2.create_network_interface'](
            name, subnet_id=subnet_id, subnet_name=subnet_name, private_ip_address=private_ip_address,
            description=description, groups=groups, region=region, key=key,
            keyid=keyid, profile=profile
        )
        if 'error' in result_create:
            ret['result'] = False
            ret['comment'] = 'Failed to create ENI: {0}'.format(
                result_create['error']['message']
            )
            return ret
        r['result'] = result_create['result']
        ret['comment'] = 'Created ENI {0}'.format(name)
        ret['changes']['id'] = r['result']['id']
    else:
        _ret = _eni_attribute(
            r['result'], 'description', description, region, key, keyid,
            profile
        )
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = _ret['comment']
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _eni_groups(
            r['result'], groups, region, key, keyid, profile
        )
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    # Actions that need to occur whether creating or updating
    _ret = _eni_attribute(
        r['result'], 'source_dest_check', source_dest_check, region, key,
        keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        return ret
    if allocate_eip:
        if 'allocationId' not in r['result']:
            if __opts__['test']:
                ret['comment'] = ' '.join([ret['comment'], 'An EIP is set to be allocated and assocaited to the ENI.'])
            else:
                domain = 'vpc' if allocate_eip == 'vpc' else None
                eip_alloc = __salt__['boto_ec2.allocate_eip_address'](domain=domain,
                                                                      region=region,
                                                                      key=key,
                                                                      keyid=keyid,
                                                                      profile=profile)
                if eip_alloc:
                    _ret = __salt__['boto_ec2.associate_eip_address'](instance_id=None,
                                                                      instance_name=None,
                                                                      public_ip=None,
                                                                      allocation_id=eip_alloc['allocation_id'],
                                                                      network_interface_id=r['result']['id'],
                                                                      private_ip_address=None,
                                                                      allow_reassociation=False,
                                                                      region=region,
                                                                      key=key,
                                                                      keyid=keyid,
                                                                      profile=profile)
                    if not _ret:
                        _ret = __salt__['boto_ec2.release_eip_address'](public_ip=None,
                                                                        allocation_id=eip_alloc['allocation_id'],
                                                                        region=region,
                                                                        key=key,
                                                                        keyid=keyid,
                                                                        profile=profile)
                        ret['result'] = False
                        msg = 'Failed to assocaite the allocated EIP address with the ENI.  The EIP {0}'.format('was successfully released.' if _ret else 'was NOT RELEASED.')
                        ret['comment'] = ' '.join([ret['comment'], msg])
                        return ret
                else:
                    ret['result'] = False
                    ret['comment'] = ' '.join([ret['comment'], 'Failed to allocate an EIP address'])
                    return ret
        else:
            ret['comment'] = ' '.join([ret['comment'], 'An EIP is already allocated/assocaited to the ENI'])
    if arecords:
        for arecord in arecords:
            if 'name' not in arecord:
                msg = 'The arecord must contain a "name" property.'
                raise SaltInvocationError(msg)
            log.debug('processing arecord {0}'.format(arecord))
            _ret = None
            dns_provider = 'boto_route53'
            arecord['record_type'] = 'A'
            public_ip_arecord = False
            if 'public' in arecord:
                public_ip_arecord = arecord.pop('public')
            if public_ip_arecord:
                if 'publicIp' in r['result']:
                    arecord['value'] = r['result']['publicIp']
                elif 'public_ip' in eip_alloc:
                    arecord['value'] = eip_alloc['public_ip']
                else:
                    msg = 'Unable to add an A record for the public IP address, a public IP address does not seem to be allocated to this ENI.'
                    raise CommandExecutionError(msg)
            else:
                arecord['value'] = r['result']['private_ip_address']
            if 'provider' in arecord:
                dns_provider = arecord.pop('provider')
            if dns_provider == 'boto_route53':
                if 'profile' not in arecord:
                    arecord['profile'] = profile
                if 'key' not in arecord:
                    arecord['key'] = key
                if 'keyid' not in arecord:
                    arecord['keyid'] = keyid
                if 'region' not in arecord:
                    arecord['region'] = region
            _ret = __states__['.'.join([dns_provider, 'present'])](**arecord)
            log.debug('ret from dns_provider.present = {0}'.format(_ret))
            ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
            ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
            if not _ret['result']:
                ret['result'] = _ret['result']
                if ret['result'] is False:
                    return ret
    return ret


def _eni_attribute(metadata, attr, value, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if metadata[attr] == value:
        return ret
    if __opts__['test']:
        ret['comment'] = 'ENI set to have {0} updated.'.format(attr)
        ret['result'] = None
        return ret
    result_update = __salt__['boto_ec2.modify_network_interface_attribute'](
        network_interface_id=metadata['id'], attr=attr,
        value=value, region=region, key=key, keyid=keyid, profile=profile
    )
    if 'error' in result_update:
        msg = 'Failed to update ENI {0}: {1}.'
        ret['result'] = False
        ret['comment'] = msg.format(attr, result_update['error']['message'])
    else:
        ret['comment'] = 'Updated ENI {0}.'.format(attr)
        ret['changes'][attr] = {
            'old': metadata[attr],
            'new': value
        }
    return ret


def _eni_groups(metadata, groups, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    group_ids = [g['id'] for g in metadata['groups']]
    group_ids.sort()
    _groups = __salt__['boto_secgroup.convert_to_group_ids'](
        groups, vpc_id=metadata['vpc_id'], region=region, key=key, keyid=keyid,
        profile=profile
    )
    if not _groups:
        ret['comment'] = 'Could not find secgroup ids for provided groups.'
        ret['result'] = False
    _groups.sort()
    if group_ids == _groups:
        return ret
    if __opts__['test']:
        ret['comment'] = 'ENI set to have groups updated.'
        ret['result'] = None
        return ret
    result_update = __salt__['boto_ec2.modify_network_interface_attribute'](
        network_interface_id=metadata['id'], attr='groups',
        value=_groups, region=region, key=key, keyid=keyid, profile=profile
    )
    if 'error' in result_update:
        msg = 'Failed to update ENI groups: {1}.'
        ret['result'] = False
        ret['comment'] = msg.format(result_update['error']['message'])
    else:
        ret['comment'] = 'Updated ENI groups.'
        ret['changes']['groups'] = {
            'old': group_ids,
            'new': _groups
        }
    return ret


def eni_absent(
        name,
        release_eip=False,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the EC2 ENI is absent.

    .. versionadded:: 2016.3.0

    name
        Name tag associated with the ENI.

    release_eip
        True/False - release any EIP associated with the ENI

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    r = __salt__['boto_ec2.get_network_interface'](
        name=name, region=region, key=key, keyid=keyid, profile=profile
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Error when attempting to find eni: {0}.'.format(
            r['error']['message']
        )
        return ret
    if not r['result']:
        if __opts__['test']:
            ret['comment'] = 'ENI is set to be deleted.'
            ret['result'] = None
            return ret
    else:
        if __opts__['test']:
            ret['comment'] = 'ENI is set to be deleted.'
            if release_eip and 'allocationId' in r['result']:
                ret['comment'] = ' '.join([ret['comment'], 'Allocated/associated EIP is set to be released'])
            ret['result'] = None
            return ret
        if 'id' in r['result']['attachment']:
            result_detach = __salt__['boto_ec2.detach_network_interface'](
                name=name, force=True, region=region, key=key,
                keyid=keyid, profile=profile
            )
            if 'error' in result_detach:
                ret['result'] = False
                ret['comment'] = 'Failed to detach ENI: {0}'.format(
                    result_detach['error']['message']
                )
                return ret
            # TODO: Ensure the detach occurs before continuing
        result_delete = __salt__['boto_ec2.delete_network_interface'](
            name=name, region=region, key=key,
            keyid=keyid, profile=profile
        )
        if 'error' in result_delete:
            ret['result'] = False
            ret['comment'] = 'Failed to delete ENI: {0}'.format(
                result_delete['error']['message']
            )
            return ret
        ret['comment'] = 'Deleted ENI {0}'.format(name)
        ret['changes']['id'] = None
        if release_eip and 'allocationId' in r['result']:
            _ret = __salt__['boto_ec2.release_eip_address'](public_ip=None,
                                                            allocation_id=r['result']['allocationId'],
                                                            region=region,
                                                            key=key,
                                                            keyid=keyid,
                                                            profile=profile)
            if not _ret:
                ret['comment'] = ' '.join([ret['comment'], 'Failed to release EIP allocated to the ENI.'])
                ret['result'] = False
                return ret
            else:
                ret['comment'] = ' '.join([ret['comment'], 'EIP released.'])
                ret['changes']['eip released'] = True
    return ret


def snapshot_created(name, ami_name, instance_name, wait_until_available=True, wait_timeout_seconds=300, **kwargs):
    '''
    Create a snapshot from the given instance

    .. versionadded:: 2016.3.0
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if not __salt__['boto_ec2.create_image'](ami_name=ami_name, instance_name=instance_name, **kwargs):
        ret['comment'] = 'Failed to create new AMI {ami_name}'.format(ami_name=ami_name)
        ret['result'] = False
        return ret

    ret['comment'] = 'Created new AMI {ami_name}'.format(ami_name=ami_name)
    ret['changes']['new'] = {ami_name: ami_name}
    if not wait_until_available:
        return ret

    starttime = time()
    while True:
        images = __salt__['boto_ec2.find_images'](ami_name=ami_name, return_objs=True, **kwargs)
        if images and images[0].state == 'available':
            break
        if time() - starttime > wait_timeout_seconds:
            if images:
                ret['comment'] = 'AMI still in state {state} after timeout'.format(state=images[0].state)
            else:
                ret['comment'] = 'AMI with name {ami_name} not found after timeout.'.format(ami_name=ami_name)
            ret['result'] = False
            return ret
        sleep(5)

    return ret


def instance_present(name, instance_name=None, instance_id=None, image_id=None,
                     image_name=None, tags=None, key_name=None,
                     security_groups=None, user_data=None, instance_type=None,
                     placement=None, kernel_id=None, ramdisk_id=None,
                     vpc_id=None, vpc_name=None, monitoring_enabled=None,
                     subnet_id=None, subnet_name=None, private_ip_address=None,
                     block_device_map=None, disable_api_termination=None,
                     instance_initiated_shutdown_behavior=None,
                     placement_group=None, client_token=None,
                     security_group_ids=None, security_group_names=None,
                     additional_info=None, tenancy=None,
                     instance_profile_arn=None, instance_profile_name=None,
                     ebs_optimized=None, network_interfaces=None,
                     network_interface_name=None,
                     network_interface_id=None,
                     attributes=None, target_state=None, public_ip=None,
                     allocation_id=None, allocate_eip=False, region=None,
                     key=None, keyid=None, profile=None):
    ### TODO - implement 'target_state={running, stopped}'
    '''
    Ensure an EC2 instance is running with the given attributes and state.

    name
        (string) - The name of the state definition.  Recommended that this
        match the instance_name attribute (generally the FQDN of the instance).
    instance_name
        (string) - The name of the instance, generally its FQDN.  Exclusive with
        'instance_id'.
    instance_id
        (string) - The ID of the instance (if known).  Exclusive with
        'instance_name'.
    image_id
        (string) – The ID of the AMI image to run.
    image_name
        (string) – The name of the AMI image to run.
    tags
        (dict) - Tags to apply to the instance.
    key_name
        (string) – The name of the key pair with which to launch instances.
    security_groups
        (list of strings) – The names of the EC2 classic security groups with
        which to associate instances
    user_data
        (string) – The Base64-encoded MIME user data to be made available to the
        instance(s) in this reservation.
    instance_type
        (string) – The EC2 instance size/type.  Note that only certain types are
        compatible with HVM based AMIs.
    placement
        (string) – The Availability Zone to launch the instance into.
    kernel_id
        (string) – The ID of the kernel with which to launch the instances.
    ramdisk_id
        (string) – The ID of the RAM disk with which to launch the instances.
    vpc_id
        (string) - The ID of a VPC to attach the instance to.
    vpc_name
        (string) - The name of a VPC to attach the instance to.
    monitoring_enabled
        (bool) – Enable detailed CloudWatch monitoring on the instance.
    subnet_id
        (string) – The ID of the subnet within which to launch the instances for
        VPC.
    subnet_name
        (string) – The name of the subnet within which to launch the instances
        for VPC.
    private_ip_address
        (string) – If you’re using VPC, you can optionally use this parameter to
        assign the instance a specific available IP address from the subnet
        (e.g., 10.0.0.25).
    block_device_map
        (boto.ec2.blockdevicemapping.BlockDeviceMapping) – A BlockDeviceMapping
        data structure describing the EBS volumes associated with the Image.
    disable_api_termination
        (bool) – If True, the instances will be locked and will not be able to
        be terminated via the API.
    instance_initiated_shutdown_behavior
        (string) – Specifies whether the instance stops or terminates on
        instance-initiated shutdown. Valid values are:
            - 'stop'
            - 'terminate'
    placement_group
        (string) – If specified, this is the name of the placement group in
        which the instance(s) will be launched.
    client_token
        (string) – Unique, case-sensitive identifier you provide to ensure
        idempotency of the request. Maximum 64 ASCII characters.
    security_group_ids
        (list of strings) – The IDs of the VPC security groups with which to
        associate instances.
    security_group_names
        (list of strings) – The names of the VPC security groups with which to
        associate instances.
    additional_info
        (string) – Specifies additional information to make available to the
        instance(s).
    tenancy
        (string) – The tenancy of the instance you want to launch. An instance
        with a tenancy of ‘dedicated’ runs on single-tenant hardware and can
        only be launched into a VPC. Valid values are:”default” or “dedicated”.
        NOTE: To use dedicated tenancy you MUST specify a VPC subnet-ID as well.
    instance_profile_arn
        (string) – The Amazon resource name (ARN) of the IAM Instance Profile
        (IIP) to associate with the instances.
    instance_profile_name
        (string) – The name of the IAM Instance Profile (IIP) to associate with
        the instances.
    ebs_optimized
        (bool) – Whether the instance is optimized for EBS I/O. This
        optimization provides dedicated throughput to Amazon EBS and a tuned
        configuration stack to provide optimal EBS I/O performance. This
        optimization isn’t available with all instance types.
    network_interfaces
        (boto.ec2.networkinterface.NetworkInterfaceCollection) – A
        NetworkInterfaceCollection data structure containing the ENI
        specifications for the instance.
    network_interface_name
         (string) - The name of Elastic Network Interface to attach

        .. versionadded:: 2016.11.0

    network_interface_id
         (string) - The id of Elastic Network Interface to attach

        .. versionadded:: 2016.11.0

    attributes
        (dict) - Instance attributes and value to be applied to the instance.
        Available options are:
            - instanceType - A valid instance type (m1.small)
            - kernel - Kernel ID (None)
            - ramdisk - Ramdisk ID (None)
            - userData - Base64 encoded String (None)
            - disableApiTermination - Boolean (true)
            - instanceInitiatedShutdownBehavior - stop|terminate
            - blockDeviceMapping - List of strings - ie: [‘/dev/sda=false’]
            - sourceDestCheck - Boolean (true)
            - groupSet - Set of Security Groups or IDs
            - ebsOptimized - Boolean (false)
            - sriovNetSupport - String - ie: ‘simple’
    target_state
        (string) - The desired target state of the instance.  Available options
        are:
            - running
            - stopped
        Note that this option is currently UNIMPLEMENTED.
    public_ip:
        (string) - The IP of a previously allocated EIP address, which will be
        attached to the instance.  EC2 Classic instances ONLY - for VCP pass in
        an allocation_id instead.
    allocation_id:
        (string) - The ID of a previously allocated EIP address, which will be
        attached to the instance.  VPC instances ONLY - for Classic pass in
        a public_ip instead.
    allocate_eip:
        (bool) - Allocate and attach an EIP on-the-fly for this instance.  Note
        you'll want to releaase this address when terminating the instance,
        either manually or via the 'release_eip' flag to 'instance_absent'.
    region
        (string) - Region to connect to.
    key
        (string) - Secret key to be used.
    keyid
        (string) - Access key to be used.
    profile
        (variable) - A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    .. versionadded:: 2016.3.0
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
          }
    _create = False
    running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')
    changed_attrs = {}

    if not salt.utils.exactly_one((image_id, image_name)):
        raise SaltInvocationError('Exactly one of image_id OR '
                                  'image_name must be provided.')
    if (public_ip or allocation_id or allocate_eip) and not salt.utils.exactly_one((public_ip, allocation_id, allocate_eip)):
        raise SaltInvocationError('At most one of public_ip, allocation_id OR '
                                  'allocate_eip may be provided.')

    if instance_id:
        exists = __salt__['boto_ec2.exists'](instance_id=instance_id, region=region, key=key,
                                             keyid=keyid, profile=profile, in_states=running_states)
        if not exists:
            _create = True
    else:
        instances = __salt__['boto_ec2.find_instances'](name=instance_name if instance_name else name,
                                                        region=region, key=key, keyid=keyid, profile=profile,
                                                        in_states=running_states)
        if not len(instances):
            _create = True

    if _create:
        if __opts__['test']:
            ret['comment'] = 'The instance {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        if image_name:
            args = {'ami_name': image_name, 'region': region, 'key': key,
                    'keyid': keyid, 'profile': profile}
            image_ids = __salt__['boto_ec2.find_images'](**args)
            if len(image_ids):
                image_id = image_ids[0]
            else:
                image_id = image_name
        r = __salt__['boto_ec2.run'](image_id, instance_name if instance_name else name,
                                     tags=tags, key_name=key_name,
                                     security_groups=security_groups, user_data=user_data,
                                     instance_type=instance_type, placement=placement,
                                     kernel_id=kernel_id, ramdisk_id=ramdisk_id, vpc_id=vpc_id,
                                     vpc_name=vpc_name, monitoring_enabled=monitoring_enabled,
                                     subnet_id=subnet_id, subnet_name=subnet_name,
                                     private_ip_address=private_ip_address,
                                     block_device_map=block_device_map,
                                     disable_api_termination=disable_api_termination,
                                     instance_initiated_shutdown_behavior=instance_initiated_shutdown_behavior,
                                     placement_group=placement_group, client_token=client_token,
                                     security_group_ids=security_group_ids,
                                     security_group_names=security_group_names,
                                     additional_info=additional_info, tenancy=tenancy,
                                     instance_profile_arn=instance_profile_arn,
                                     instance_profile_name=instance_profile_name,
                                     ebs_optimized=ebs_optimized, network_interfaces=network_interfaces,
                                     network_interface_name=network_interface_name,
                                     network_interface_id=network_interface_id,
                                     region=region, key=key, keyid=keyid, profile=profile)
        if not r or 'instance_id' not in r:
            ret['result'] = False
            ret['comment'] = 'Failed to create instance {0}.'.format(instance_name if instance_name else name)
            return ret

        instance_id = r['instance_id']
        ret['changes'] = {'old': {}, 'new': {}}
        ret['changes']['old']['instance_id'] = None
        ret['changes']['new']['instance_id'] = instance_id

        # To avoid issues we only allocate new EIPs at instance creation.
        # This might miss situations where an instance is initially created
        # created without and one is added later, but the alternative is the
        # risk of EIPs allocated at every state run.
        if allocate_eip:
            if __opts__['test']:
                ret['comment'] = 'New EIP would be allocated.'
                ret['result'] = None
                return ret
            domain = 'vpc' if vpc_id or vpc_name else None
            r = __salt__['boto_ec2.allocate_eip_address'](
                    domain=domain, region=region, key=key, keyid=keyid,
                    profile=profile)
            if not r:
                ret['result'] = False
                ret['comment'] = 'Failed to allocate new EIP.'
                return ret
            allocation_id = r['allocation_id']
            log.info("New EIP with address {0} allocated.".format(r['public_ip']))
        else:
            log.info("EIP not requested.")

    if public_ip or allocation_id:
        # This can take a bit to show up, give it a chance to...
        tries = 10
        secs = 3
        for t in range(tries):
            r = __salt__['boto_ec2.get_eip_address_info'](
                    addresses=public_ip, allocation_ids=allocation_id,
                    region=region, key=key, keyid=keyid, profile=profile)
            if r:
                break
            else:
                log.info("Waiting up to {0} secs for new EIP {1} to become available".format(
                        tries * secs, public_ip or allocation_id))
                time.sleep(secs)
        if not r:
            ret['result'] = False
            ret['comment'] = 'Failed to lookup EIP {0}.'.format(public_ip or allocation_id)
            return ret
        ip = r[0]['public_ip']
        if r[0].get('instance_id'):
            if r[0]['instance_id'] != instance_id:
                ret['result'] = False
                ret['comment'] = ('EIP {0} is already associated with instance '
                                  '{1}.'.format(public_ip if public_ip else
                                  allocation_id, r[0]['instance_id']))
                return ret
        else:
            if __opts__['test']:
                ret['comment'] = 'Instance {0} to be updated.'.format(name)
                ret['result'] = None
                return ret
            r = __salt__['boto_ec2.associate_eip_address'](
                    instance_id=instance_id, public_ip=public_ip,
                    allocation_id=allocation_id, region=region, key=key,
                    keyid=keyid, profile=profile)
            if r:
                ret['changes']['new']['public_ip'] = ip
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to attach EIP to instance {0}.'.format(
                        instance_name if instance_name else name)
                return ret

    if attributes:
        for k, v in six.iteritems(attributes):
            curr = __salt__['boto_ec2.get_attribute'](k, instance_id=instance_id, region=region, key=key,
                                                      keyid=keyid, profile=profile)
            if not isinstance(curr, dict):
                curr = {}
            if curr.get(k) == v:
                continue
            else:
                if __opts__['test']:
                    changed_attrs[k] = 'The instance attribute {0} is set to be changed from \'{1}\' to \'{2}\'.'.format(
                                       k, curr.get(k), v)
                    continue
                try:
                    r = __salt__['boto_ec2.set_attribute'](attribute=k, attribute_value=v,
                                                           instance_id=instance_id, region=region,
                                                           key=key, keyid=keyid, profile=profile)
                except SaltInvocationError as e:
                    ret['result'] = False
                    ret['comment'] = 'Failed to set attribute {0} to {1} on instance {2}.'.format(k, v, instance_name)
                    return ret
                ret['changes'] = ret['changes'] if ret['changes'] else {'old': {}, 'new': {}}
                ret['changes']['old'][k] = curr.get(k)
                ret['changes']['new'][k] = v

    if __opts__['test']:
        if changed_attrs:
            ret['changes']['new'] = changed_attrs
            ret['result'] = None
        else:
            ret['comment'] = 'Instance {0} is in the correct state'.format(instance_name if instance_name else name)
            ret['result'] = True

    return ret


def instance_absent(name, instance_name=None, instance_id=None,
                    release_eip=False, region=None, key=None, keyid=None,
                    profile=None, filters=None):
    '''
    Ensure an EC2 instance does not exist (is stopped and removed).

    .. versionupdated:: 2016.11.0

    name
        (string) - The name of the state definition.
    instance_name
        (string) - The name of the instance.
    instance_id
        (string) - The ID of the instance.
    release_eip
        (bool)   - Release any associated EIPs during termination.
    region
        (string) - Region to connect to.
    key
        (string) - Secret key to be used.
    keyid
        (string) - Access key to be used.
    profile
        (variable) - A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    filters
        (dict) - A dict of additional filters to use in matching the instance to
        delete.

    YAML example fragment:

    .. code-block:: yaml
        - filters:
            vpc-id: vpc-abcdef12

    '''
    ### TODO - Implement 'force' option??  Would automagically turn off
    ###        'disableApiTermination', as needed, before trying to delete.
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
          }
    running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')

    if not instance_id:
        try:
            instance_id = __salt__['boto_ec2.get_id'](name=instance_name if instance_name else name,
                                                      region=region, key=key, keyid=keyid,
                                                      profile=profile, in_states=running_states,
                                                      filters=filters)
        except CommandExecutionError as e:
            ret['result'] = None
            ret['comment'] = ("Couldn't determine current status of instance "
                              "{0}.".format(instance_name or name))
            return ret

    instances = __salt__['boto_ec2.find_instances'](instance_id=instance_id, region=region,
                                                    key=key, keyid=keyid, profile=profile,
                                                    return_objs=True, filters=filters)
    if not len(instances):
        ret['result'] = True
        ret['comment'] = 'Instance {0} is already gone.'.format(instance_id)
        return ret
    instance = instances[0]

    ### Honor 'disableApiTermination' - if you want to override it, first use set_attribute() to turn it off
    no_can_do = __salt__['boto_ec2.get_attribute']('disableApiTermination', instance_id=instance_id,
                                                   region=region, key=key, keyid=keyid, profile=profile)
    if no_can_do.get('disableApiTermination') is True:
        ret['result'] = False
        ret['comment'] = 'Termination of instance {0} via the API is disabled.'.format(instance_id)
        return ret

    if __opts__['test']:
        ret['comment'] = 'The instance {0} is set to be deleted.'.format(name)
        ret['result'] = None
        return ret

    r = __salt__['boto_ec2.terminate'](instance_id=instance_id, name=instance_name, region=region,
                                       key=key, keyid=keyid, profile=profile)
    if not r:
        ret['result'] = False
        ret['comment'] = 'Failed to terminate instance {0}.'.format(instance_id)
        return ret

    ret['changes']['old'] = {'instance_id': instance_id}
    ret['changes']['new'] = None

    if release_eip:
        ip = getattr(instance, 'ip_address', None)
        if ip:
            base_args = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
            public_ip = None
            alloc_id = None
            assoc_id = None
            if getattr(instance, 'vpc_id', None):
                r = __salt__['boto_ec2.get_eip_address_info'](addresses=ip, **base_args)
                if len(r) and 'allocation_id' in r[0]:
                    alloc_id = r[0]['allocation_id']
                    assoc_id = r[0].get('association_id')
                else:
                    # I /believe/ this situation is impossible but let's hedge our bets...
                    ret['result'] = False
                    ret['comment'] = "Can't determine AllocationId for address {0}.".format(ip)
                    return ret
            else:
                public_ip = instance.ip_address

            if assoc_id:
                # Race here - sometimes the terminate above will already have dropped this
                if not __salt__['boto_ec2.disassociate_eip_address'](association_id=assoc_id,
                                                                     **base_args):
                    log.warning("Failed to disassociate EIP {0}.".format(ip))

            if __salt__['boto_ec2.release_eip_address'](allocation_id=alloc_id, public_ip=public_ip,
                                                        **base_args):
                log.info("Released EIP address {0}".format(public_ip or r[0]['public_ip']))
                ret['changes']['old']['public_ip'] = public_ip or r[0]['public_ip']
            else:
                ret['result'] = False
                ret['comment'] = "Failed to release EIP {0}.".format(ip)
                return ret

    return ret


def volume_absent(name, volume_name=None, volume_id=None, instance_name=None,
                  instance_id=None, device=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the EC2 volume is detached and absent.

    .. versionadded:: 2016.11.0

    name
        State definition name.

    volume_name
        Name tag associated with the volume.  For safety, if this matches more than
        one volume, the state will refuse to apply.

    volume_id
        Resource ID of the volume.

    instance_name
        Only remove volume if it is attached to instance with this Name tag.
        Exclusive with 'instance_id'.  Requires 'device'.

    instance_id
        Only remove volume if it is attached to this instance.
        Exclusive with 'instance_name'.  Requires 'device'.

    device
        Match by device rather than ID.  Requires one of 'instance_name' or
        'instance_id'.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    '''

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
          }
    filters = {}
    running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')

    if not salt.utils.exactly_one((volume_name, volume_id, instance_name, instance_id)):
        raise SaltInvocationError("Exactly one of 'volume_name', 'volume_id', "
                                  "'instance_name', or 'instance_id' must be provided.")
    if (instance_name or instance_id) and not device:
        raise SaltInvocationError("Parameter 'device' is required when either "
                                  "'instance_name' or 'instance_id' is specified.")
    if volume_id:
        filters.update({'volume-id': volume_id})
    if volume_name:
        filters.update({'tag:Name': volume_name})
    if instance_name:
        instance_id = __salt__['boto_ec2.get_id'](
                name=instance_name, region=region, key=key, keyid=keyid,
                profile=profile, in_states=running_states)
        if not instance_id:
            ret['comment'] = ('Instance with Name {0} not found.  Assuming '
                              'associated volumes gone.'.format(instance_name))
            return ret
    if instance_id:
        filters.update({'attachment.instance-id': instance_id})
    if device:
        filters.update({'attachment.device': device})

    args = {'region': region, 'key': key, 'keyid': keyid, 'profile': profile}

    vols = __salt__['boto_ec2.get_all_volumes'](filters=filters, **args)
    if len(vols) < 1:
        ret['comment'] = 'Volume matching criteria not found, assuming already absent'
        return ret
    if len(vols) > 1:
        msg = "More than one volume matched criteria, can't continue in state {0}".format(name)
        log.error(msg)
        ret['comment'] = msg
        ret['result'] = False
        return ret
    vol = vols[0]
    log.info('Matched Volume ID {0}'.format(vol))

    if __opts__['test']:
        ret['comment'] = 'The volume {0} is set to be deleted.'.format(vol)
        ret['result'] = None
        return ret
    if __salt__['boto_ec2.delete_volume'](volume_id=vol, force=True, **args):
        ret['comment'] = 'Volume {0} deleted.'.format(vol)
        ret['changes'] = {'old': {'volume_id': vol}, 'new': {'volume_id': None}}
    else:
        ret['comment'] = 'Error deleting volume {0}.'.format(vol)
        ret['result'] = False
    return ret


def volumes_tagged(name, tag_maps, authoritative=False, region=None, key=None,
                   keyid=None, profile=None):
    '''
    Ensure EC2 volume(s) matching the given filters have the defined tags.

    .. versionadded:: 2016.11.0

    name
        State definition name.

    tag_maps
        List of dicts of filters and tags, where 'filters' is a dict suitable for passing
        to the 'filters' argument of boto_ec2.get_all_volumes(), and 'tags' is a dict of
        tags to be set on volumes as matched by the given filters.  The filter syntax is
        extended to permit passing either a list of volume_ids or an instance_name (with
        instance_name being the Name tag of the instance to which the desired volumes are
        mapped).  Each mapping in the list is applied separately, so multiple sets of
        volumes can be all tagged differently with one call to this function.

    YAML example fragment:

    .. code-block:: yaml
        - filters:
            attachment.instance_id: i-abcdef12
          tags:
            Name: dev-int-abcdef12.aws-foo.com
        - filters:
            attachment.device: /dev/sdf
          tags:
            ManagedSnapshots: true
            BillingGroup: bubba.hotep@aws-foo.com
        - filters:
            instance_name: prd-foo-01.aws-foo.com
          tags:
            Name: prd-foo-01.aws-foo.com
            BillingGroup: infra-team@aws-foo.com
        - filters:
            volume_ids: [ vol-12345689, vol-abcdef12 ]
          tags:
            BillingGroup: infra-team@aws-foo.com

    authoritative
        Should un-declared tags currently set on matched volumes be deleted?  Boolean.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    '''

    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
          }
    args = {'tag_maps': tag_maps, 'authoritative': authoritative,
            'region': region, 'key': key, 'keyid': keyid, 'profile': profile}

    if __opts__['test']:
        args['dry_run'] = True
        r = __salt__['boto_ec2.set_volumes_tags'](**args)
        if r.get('changes'):
            ret['comment'] = 'The following changes would be applied: {0}'.format(r)
        return ret
    r = __salt__['boto_ec2.set_volumes_tags'](**args)
    if r['success'] is True:
        ret['comment'] = 'Tags applied.'
        ret['changes'] = r['changes']
    else:
        ret['comment'] = 'Error updating requested volume tags.'
        ret['result'] = False
    return ret


def private_ips_present(name, network_interface_name=None, network_interface_id=None,
                        private_ip_addresses=None, allow_reassignment=False, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Ensure an ENI has secondary private ip addresses associated with it

    name
        (String) - State definition name
    network_interface_id
        (String) - The EC2 network interface id, example eni-123456789
    private_ip_addresses
        (List or String) - The secondary private ip address(es) that should be present on the ENI.
    allow_reassignment
        (Boolean) - If true, will reassign a secondary private ip address associated with another
        ENI. If false, state will fail if the secondary private ip address is associated with
        another ENI.
    region
        (string) - Region to connect to.
    key
        (string) - Secret key to be used.
    keyid
        (string) - Access key to be used.
    profile
        (variable) - A dict with region, key and keyid, or a pillar key (string) that contains a
        dict with region, key and keyid.
    '''

    if not salt.utils.exactly_one((network_interface_name, network_interface_id)):
        raise SaltInvocationError("Exactly one of 'network_interface_name', "
                                  "'network_interface_id' must be provided")

    if not private_ip_addresses:
        raise SaltInvocationError("You must provide the private_ip_addresses to associate with the "
                                  "ENI")

    ret = {
       'name': name,
       'result': True,
       'comment': '',
       'changes': {'old': [], 'new': []}
    }

    get_eni_args = {
        'name': network_interface_name,
        'network_interface_id': network_interface_id,
        'region': region,
        'key': key,
        'keyid': keyid,
        'profile': profile
    }

    eni = __salt__['boto_ec2.get_network_interface'](**get_eni_args)

    # Check if there are any new secondary private ips to add to the eni
    if eni and eni.get('result', {}).get('private_ip_addresses'):
        for eni_pip in eni['result']['private_ip_addresses']:
            ret['changes']['old'].append(eni_pip['private_ip_address'])

    ips_to_add = []
    for private_ip in private_ip_addresses:
        if private_ip not in ret['changes']['old']:
            ips_to_add.append(private_ip)

    if ips_to_add:
        # Assign secondary private ips to ENI
        assign_ips_args = {
            'network_interface_id': network_interface_id,
            'private_ip_addresses': ips_to_add,
            'allow_reassignment': allow_reassignment,
            'region': region,
            'key': key,
            'keyid': keyid,
            'profile': profile
        }

        __salt__['boto_ec2.assign_private_ip_addresses'](**assign_ips_args)

        # Verify secondary private ips were properly assigned to ENI
        eni = __salt__['boto_ec2.get_network_interface'](**get_eni_args)
        if eni and eni.get('result', {}).get('private_ip_addresses', None):
            for eni_pip in eni['result']['private_ip_addresses']:
                ret['changes']['new'].append(eni_pip['private_ip_address'])

        ips_not_added = []
        for private_ip in private_ip_addresses:
            if private_ip not in ret['changes']['new']:
                ips_not_added.append(private_ip)

        # Display results
        if ips_not_added:
            ret['result'] = False
            ret['comment'] = ('ips on eni: {0}\n'
                              'attempted to add: {1}\n'
                              'could not add the following ips: {2}\n'.format(
                                '\n\t- ' + '\n\t- '.join(ret['changes']['new']),
                                '\n\t- ' + '\n\t- '.join(ips_to_add),
                                '\n\t- ' + '\n\t- '.join(ips_not_added)))
        else:
            ret['comment'] = "added ips: {0}".format(
                '\n\t- ' + '\n\t- '.join(ips_to_add))

        # Verify there were changes
        if ret['changes']['old'] == ret['changes']['new']:
            ret['changes'] = {}

    else:
        ret['comment'] = 'ips on network interface: {0}'.format(
            '\n\t- ' + '\n\t- '.join(ret['changes']['old']))

        # there were no changes since we did not attempt to remove ips
        ret['changes'] = {}

    return ret


def private_ips_absent(name, network_interface_name=None, network_interface_id=None,
                       private_ip_addresses=None, region=None, key=None, keyid=None, profile=None):

    '''
    Ensure an ENI does not have secondary private ip addresses associated with it

    name
        (String) - State definition name
    network_interface_id
        (String) - The EC2 network interface id, example eni-123456789
    private_ip_addresses
        (List or String) - The secondary private ip address(es) that should be absent on the ENI.
    region
        (string) - Region to connect to.
    key
        (string) - Secret key to be used.
    keyid
        (string) - Access key to be used.
    profile
        (variable) - A dict with region, key and keyid, or a pillar key (string) that contains a
        dict with region, key and keyid.
    '''

    if not salt.utils.exactly_one((network_interface_name, network_interface_id)):
        raise SaltInvocationError("Exactly one of 'network_interface_name', "
                                  "'network_interface_id' must be provided")

    if not private_ip_addresses:
        raise SaltInvocationError("You must provide the private_ip_addresses to unassociate with "
                                  "the ENI")
    if not isinstance(private_ip_addresses, list):
        private_ip_addresses = [private_ip_addresses]

    ret = {
        'name': name,
        'result': True,
        'comment': '',
        'changes': {'new': [], 'old': []}
    }

    get_eni_args = {
        'name': network_interface_name,
        'network_interface_id': network_interface_id,
        'region': region,
        'key': key,
        'keyid': keyid,
        'profile': profile
    }

    eni = __salt__['boto_ec2.get_network_interface'](**get_eni_args)

    # Check if there are any old private ips to remove from the eni
    if eni and eni.get('result', {}).get('private_ip_addresses'):
        for eni_pip in eni['result']['private_ip_addresses']:
            ret['changes']['old'].append(eni_pip['private_ip_address'])

    ips_to_remove = []
    for private_ip in private_ip_addresses:
        if private_ip in ret['changes']['old']:
            ips_to_remove.append(private_ip)

    if ips_to_remove:
        # Unassign secondary private ips to ENI
        assign_ips_args = {
            'network_interface_id': network_interface_id,
            'private_ip_addresses': ips_to_remove,
            'region': region,
            'key': key,
            'keyid': keyid,
            'profile': profile
        }

        __salt__['boto_ec2.unassign_private_ip_addresses'](**assign_ips_args)

        # Verify secondary private ips were properly unassigned from ENI
        eni = __salt__['boto_ec2.get_network_interface'](**get_eni_args)
        if eni and eni.get('result', {}).get('private_ip_addresses', None):
            for eni_pip in eni['result']['private_ip_addresses']:
                ret['changes']['new'].append(eni_pip['private_ip_address'])
        ips_not_removed = []
        for private_ip in private_ip_addresses:
            if private_ip in ret['changes']['new']:
                ips_not_removed.append(private_ip)

        if ips_not_removed:
            ret['result'] = False
            ret['comment'] = ('ips on eni: {0}\n'
                              'attempted to remove: {1}\n'
                              'could not remove the following ips: {2}\n'.format(
                                '\n\t- ' + '\n\t- '.join(ret['changes']['new']),
                                '\n\t- ' + '\n\t- '.join(ips_to_remove),
                                '\n\t- ' + '\n\t- '.join(ips_not_removed)))
        else:
            ret['comment'] = "removed ips: {0}".format('\n\t- ' + '\n\t- '.join(ips_to_remove))

        # Verify there were changes
        if ret['changes']['old'] == ret['changes']['new']:
            ret['changes'] = {}

    else:
        ret['comment'] = 'ips on network interface: {0}'.format(
            '\n\t- ' + '\n\t- '.join(ret['changes']['old']))

        # there were no changes since we did not attempt to remove ips
        ret['changes'] = {}

    return ret
