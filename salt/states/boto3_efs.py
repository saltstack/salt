#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
This module provides access to the Elastic File System (EFS) service from AWS.

::codeauthor: Florian Benscheidt <florian.benscheidt@ogd.nl>
::codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
'''

from __future__ import absolute_import, unicode_literals
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Checks if all the required Salt functions are present.
    '''
    for requirement in ['boto_efs.get_file_systems',
                        'boto_efs.create_file_system',
                        'boto_vpc.describe_subnet',
                        'boto_secgroup.convert_to_group_ids',
                        'boto_efs.get_mount_targets',
                        'boto_efs.create_mount_target',
                        'boto_efs.delete_file_system',
                        'boto_efs.delete_mount_target']:
        if requirement not in __salt__:
            return False, 'Salt function "{}" not found'.format(requirement)
    return True


def efs_present(
        name,
        performance_mode=None,
        keyid=None,
        key=None,
        profile=None,
        region=None):
    '''
    Ensures an Elastic FileSystem is present.

    :param str name: Name of the EFS.
    :param str performance_mode: The performance mode of the file system.
        Accepted values:
        - generalPurpose
        - maxIO

    Example usage:

    .. code-block:: yaml

    create_efs:
      efs.efs_present:
      - name: my_filesystem
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    fs_opts = {}
    if performance_mode is not None:
        fs_opts.update({'performance_mode': performance_mode})

    res = __salt__['boto_efs.get_file_systems'](
        keyid=keyid,
        key=key,
        profile=profile,
        region=region
    )
    current_efs_names = [fs_['Name'] for fs_ in res]
    if name not in current_efs_names:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'EFS with name "{}" would have been created.'.format(name)
            ret['pchanges'] = {'old': None,
                               'new': 'EFS named "{}"'.format(name)}
        else:
            new_efs = __salt__['boto_efs.create_file_system'](
                name,
                keyid=keyid,
                key=key,
                profile=profile,
                region=region,
                **fs_opts
                )
            if not new_efs:
                ret['comment'] = 'Error creating new EFS "{}"'.format(name)
            else:
                ret['result'] = True
                ret['comment'] = 'Created EFS "{}"'.format(name)
                ret['changes'] = {'old': None,
                                  'new': new_efs['FileSystemId']}
    else:
        ret['result'] = True
        ret['comment'] = 'EFS with name "{}" already exists.'.format(name)
    return ret


def mount_target_present(
        name,
        subnet_name,
        security_groups=None,
        keyid=None,
        key=None,
        profile=None,
        region=None):
    '''
    Ensures a mount target is present for the specified EFS in the specified
    subnet.

    :param str name: The name of the EFS to create the mount target for.
    :param str subnet_name: The name of the subnet to create the mount target in.
    :param list security_groups: List of names of security groups to associate
        with the mount target. These security groups must be in the same VPC as
        the subnet specified.
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    subnet_info = __salt__['boto_vpc.describe_subnet'](
        region=region,
        subnet_name=subnet_name
        ).get('subnet', {})

    mnt_opts = {}
    if security_groups is not None:
        security_group_ids = __salt__['boto_secgroup.convert_to_group_ids'](
            security_groups,
            vpc_id=subnet_info['vpc_id'],
            keyid=keyid,
            key=key,
            profile=profile,
            region=region
        )
        mnt_opts.update({'securitygroups': security_group_ids})

    efs_res = __salt__['boto_efs.get_file_systems'](
            keyid=keyid,
            key=key,
            profile=profile,
            region=region
            )
    current_efs = {fs_['Name']: fs_ for fs_ in efs_res}
    if name not in current_efs:
        ret['comment'] = ('The specified EFS "{}" does not exist, can not create'
                          ' mountpoint'.format(name))
        return ret
    fs_id = current_efs[name]['FileSystemId']
    get_mount_targets = __salt__['boto_efs.get_mount_targets'](
            filesystemid=fs_id
            )
    current_mount_targets = {mt_['SubnetId']: mt_ for mt_ in get_mount_targets}
    if subnet_info['id'] not in current_mount_targets:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Mount target for EFS "{}" would have been created.'
                              ''.format(name))
            ret['pchanges'] = {'old': None,
                               'new': 'Mount target for "{}" in subnet "{}"'
                                      ''.format(name, subnet_name)}
        else:
            mnt_tgt = __salt__['boto_efs.create_mount_target'](
                filesystemid=fs_id,
                subnetid=subnet_info['id'],
                keyid=keyid,
                key=key,
                profile=profile,
                region=region,
                **mnt_opts
                )
            if mnt_tgt:
                ret['comment'] = 'Mount target "{}" created.'.format(mnt_tgt['MountTargetId'])
                ret['result'] = True
                ret['changes'] = {'old': None, 'new': mnt_tgt['MountTargetId']}
            else:
                ret['comment'] = 'Failed to create mount target for "{}".'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = ('Mount target for EFS "{}" already '
                          'exists in subnet "{}".'.format(name, subnet_name))
    return ret


def efs_absent(
        name,
        keyid=None,
        key=None,
        profile=None,
        region=None
        ):
    '''
    Ensure the Elastic FileSystem specified is absent.

    :param str name: The name of the Elastic FileSystem.
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    efs_res = __salt__['boto_efs.get_file_systems'](
                keyid=keyid,
                key=key,
                profile=profile,
                region=region
                )
    current_efs = {fs_['Name']: fs_ for fs_ in efs_res}
    if name in current_efs:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'The EFS "{}" would have been deleted.'.format(name)
            ret['pchanges'] = {'old': name, 'new': None}
        else:
            res = __salt__['boto_efs.delete_file_system'](
                    filesystemid=current_efs[name]['FileSystemId'],
                    keyid=keyid,
                    key=key,
                    profile=profile,
                    region=region
                    )
            if res:
                ret['result'] = True
                ret['comment'] = 'EFS "{}" deleted.'.format(name)
            else:
                ret['comment'] = 'Failed to delete EFS "{}"'.format(name)
    else:
        ret['comment'] = 'EFS "{}" already absent.'.format(name)
        ret['result'] = True
    return ret


def mount_target_absent(
        name,
        subnet_name,
        keyid=None,
        key=None,
        profile=None,
        region=None
        ):
    '''
    Ensures the Mount Target for the specified EFS in the specified subnet is absent.

    :param str name: The name of the Elastic FileSystem.
    :param str subnet_name: The name of the subnet the mount target is in.
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}

    subnet_info = __salt__['boto_vpc.describe_subnet'](
            region=region,
            subnet_name=subnet_name
            ).get('subnet', {})
    efs_res = __salt__['boto_efs.get_file_systems'](
            keyid=keyid,
            key=key,
            profile=profile,
            region=region
            )
    current_efs = {fs_['Name']: fs_ for fs_ in efs_res}
    if name not in current_efs:
        ret['result'] = True
        ret['comment'] = ('The specified EFS "{}" does not exist, '
                          'mount targets already absent'.format(name))
        return ret
    fs_id = current_efs[name]['FileSystemId']
    get_mount_targets = __salt__['boto_efs.get_mount_targets'](
            filesystemid=fs_id
            )
    current_mount_targets = {mt_['SubnetId']: mt_ for mt_ in get_mount_targets}
    if subnet_info['id'] in current_mount_targets:
        mount_target_id = current_mount_targets[subnet_info['id']]['MountTargetId']
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Mount target for EFS "{}" in subnet "{}" '
                              'would have been deleted'.format(name, subnet_name))
            ret['pchanges'] = {'old': mount_target_id, 'new': None}
        else:
            res = __salt__['boto_efs.delete_mount_target'](
                mount_target_id,
                keyid=keyid,
                key=key,
                profile=profile,
                region=region
                )
            if res:
                ret['comment'] = 'Mount target "{}" deleted.'.format(mount_target_id)
                ret['result'] = True
                ret['changes'] = {'new': None, 'old': mount_target_id}
            else:
                ret['comment'] = 'Failed to delete mount target for "{}".'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = ('Mount target for EFS "{}" already absent '
                          'in subnet "{}".'.format(name, subnet_name))
    return ret
