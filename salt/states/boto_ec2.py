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
from salt.exceptions import SaltInvocationError

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
        image, = __salt__['boto_ec2.find_images'](ami_name=ami_name, return_objs=True)
        if image.state == 'available':
            break
        if time() - starttime > wait_timeout_seconds:
            ret['comment'] = 'AMI still in state {state} after timeout'.format(state=image.state)
            ret['result'] = False
            return ret
        sleep(5)

    return ret
