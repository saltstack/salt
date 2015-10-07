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
        subnet_id,
        private_ip_address=None,
        description=None,
        groups=None,
        source_dest_check=True,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the EC2 ENI exists.

    .. versionadded:: Boron

    name
        Name tag associated with the ENI.

    subnet_id
        The VPC subnet the ENI will exist within.

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
    if not subnet_id:
        raise SaltInvocationError('subnet_id is a required argument.')
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
            ret['result'] = None
            return ret
        result_create = __salt__['boto_ec2.create_network_interface'](
            name, subnet_id, private_ip_address=private_ip_address,
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
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the EC2 ENI is absent.

    .. versionadded:: Boron

    name
        Name tag associated with the ENI.

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
    return ret


def snapshot_created(name, ami_name, instance_name, wait_until_available=True, wait_timeout_seconds=300, **kwargs):
    '''
    Create a snapshot from the given instance

    .. versionadded:: Boron
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
        images = __salt__['boto_ec2.find_images'](ami_name=ami_name, return_objs=True)
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
                     attributes=None, target_state=None, region=None, key=None,
                     keyid=None, profile=None):
    ### TODO - implement 'target_state={running, stopped}'
    ### TODO - Describe all the above params :-(
    '''
    Ensure an EC2 instance is running with the given attributes and state.
    .. versionadded:: Boron
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
          }
    _create = False
    running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')
    changed_attrs = {}

    if not instance_id:
        try:
            instance_id = __salt__['boto_ec2.get_id'](name=instance_name if instance_name else name,
                                                      tags=tags, region=region, key=key, keyid=keyid,
                                                      profile=profile, in_states=running_states)
        except CommandExecutionError as e:
            ret['result'] = None
            ret['comment'] = 'Couldn\'t determine current status of instance {0}.'.format(instance_name)
            return ret

    exists = __salt__['boto_ec2.exists'](instance_id=instance_id, region=region,
                                         key=key, keyid=keyid, profile=profile)
    if not exists:
        _create = True
    else:
        instances = __salt__['boto_ec2.find_instances'](instance_id=instance_id, region=region,
                                                        key=key, keyid=keyid, profile=profile,
                                                        return_objs=True, in_states=running_states)
        if not len(instances):
            _create = True

    if _create:
        if __opts__['test']:
            ret['comment'] = 'The instance {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
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
                                     region=region, key=key, keyid=keyid, profile=profile)
        if not r or 'instance_id' not in r:
            ret['result'] = False
            ret['comment'] = 'Failed to create instance {0}.'.format(instance_name if instance_name else name)
            return ret

        instance_id = r['instance_id']
        ret['changes'] = {'old': {}, 'new': {}}
        ret['changes']['old']['instance_id'] = None
        ret['changes']['new']['instance_id'] = instance_id

    for k, v in attributes.iteritems():
        curr = __salt__['boto_ec2.get_attribute'](k, instance_id=instance_id, region=region, key=key,
                                                  keyid=keyid, profile=profile)
        if type(curr) != type({}):
            curr = {}
        if curr and curr.get(k) == v:
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

    return ret


def instance_absent(name, instance_name=None, instance_id=None,
                     region=None, key=None, keyid=None, profile=None):
    '''
    Ensure an EC2 instance does not exist (is stopped and removed).

    .. versionadded:: Boron
    '''
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
                                                      profile=profile, in_states=running_states)
        except CommandExecutionError as e:
            ret['result'] = None
            ret['comment'] = 'Couldn\'t determine current status of instance {0}.'.format(instance_name)
            return ret

    exists = __salt__['boto_ec2.exists'](instance_id=instance_id, region=region,
                                         key=key, keyid=keyid, profile=profile)
    if not exists:
        ret['result'] = True
        ret['comment'] = 'Instance {0} is already gone.'.format(instance_id)
        return ret

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
    return ret
