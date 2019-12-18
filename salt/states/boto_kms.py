# -*- coding: utf-8 -*-
'''
Manage KMS keys, key policies and grants.

.. versionadded:: 2015.8.0

Be aware that this interacts with Amazon's services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit kms credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    elb.keyid: GKTADJGHEIQSXMKKRBJ08H
    elb.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    Ensure mykey key exists:
      boto_kms.key_present:
        - name: mykey
        - region: us-east-1

    # Using a profile from pillars
    Ensure mykey key exists:
      boto_kms.key_present:
        - name: mykey
        - region: us-east-1
        - profile: myprofile

    # Passing in a profile
    Ensure mykey key exists:
      boto_key.key_present:
        - name: mykey
        - region: us-east-1
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.dictupdate as dictupdate
from salt.exceptions import SaltInvocationError


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_kms' if 'boto_kms.describe_key' in __salt__ else False


def key_present(
        name,
        policy,
        description=None,
        key_usage=None,
        grants=None,
        manage_grants=False,
        key_rotation=False,
        enabled=True,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the KMS key exists. KMS keys can not be deleted, so this function
    must be used to ensure the key is enabled or disabled.

    name
        Name of the key.

    policy
        Key usage policy.

    description
        Description of the key.

    key_usage
        Specifies the intended use of the key. Can only be set on creation,
        defaults to ENCRYPT_DECRYPT, which is also the only supported option.

    grants
        A list of grants to apply to the key. Not currently implemented.

    manage_grants
        Whether or not to manage grants. False by default, which will not
        manage any grants.

    key_rotation
        Whether or not key rotation is enabled for the key. False by default.

    enabled
        Whether or not the key is enabled. True by default.

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
    if not policy:
        raise SaltInvocationError('policy is a required argument.')
    if grants and not isinstance(grants, list):
        raise SaltInvocationError('manage_grants must be a list.')
    if not isinstance(manage_grants, bool):
        raise SaltInvocationError('manage_grants must be true or false.')
    if not isinstance(key_rotation, bool):
        raise SaltInvocationError('key_rotation must be true or false.')
    if not isinstance(enabled, bool):
        raise SaltInvocationError('enabled must be true or false.')
    # TODO: support grant from pillars.
    # TODO: support key policy from pillars.
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    _ret = _key_present(
        name, policy, description, key_usage, key_rotation, enabled, region,
        key, keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    # TODO: add grants_present function
    return ret


def _key_present(
        name,
        policy,
        description,
        key_usage,
        key_rotation,
        enabled,
        region,
        key,
        keyid,
        profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    alias = 'alias/{0}'.format(name)
    r = __salt__['boto_kms.key_exists'](alias, region, key, keyid, profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Error when attempting to find key: {0}.'.format(
            r['error']['message']
        )
        return ret
    if not r['result']:
        if __opts__['test']:
            ret['comment'] = 'Key is set to be created.'
            ret['result'] = None
            return ret
        rc = __salt__['boto_kms.create_key'](
            policy, description, key_usage, region, key, keyid, profile
        )
        if 'error' in rc:
            ret['result'] = False
            ret['comment'] = 'Failed to create key: {0}'.format(
                rc['error']['message']
            )
            return ret
        key_metadata = rc['key_metadata']
        kms_key_id = key_metadata['KeyId']
        rn = __salt__['boto_kms.create_alias'](
            alias, kms_key_id, region, key, keyid, profile
        )
        if 'error' in rn:
            # We can't recover from this. KMS only exposes enable/disable
            # and disable is not necessarily a great action here. AWS sucks
            # for not including alias in the create_key call.
            ret['result'] = False
            ret['comment'] = (
                'Failed to create key alias for key_id {0}. This resource '
                'will be left dangling. Please clean manually. '
                'Error: {1}'.format(kms_key_id, rn['error']['message'])
            )
            return ret
        ret['changes']['old'] = {'key': None}
        ret['changes']['new'] = {'key': name}
        ret['comment'] = 'Key {0} created.'.format(name)
    else:
        rd = __salt__['boto_kms.describe_key'](
            alias, region, key, keyid, profile
        )
        if 'error' in rd:
            ret['result'] = False
            ret['comment'] = 'Failed to update key: {0}.'.format(
                rd['error']['message']
            )
            return ret
        key_metadata = rd['key_metadata']
        _ret = _key_description(
            key_metadata, description, region, key, keyid, profile
        )
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _key_policy(
            key_metadata, policy, region, key, keyid, profile
        )
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    # Actions that need to occur whether creating or updating
    _ret = _key_enabled(
        key_metadata, enabled, region, key, keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _key_rotation(
        key_metadata, key_rotation, region, key, keyid, profile
    )
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _key_enabled(key_metadata, enabled, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    kms_key_id = key_metadata['KeyId']
    if key_metadata['Enabled'] == enabled:
        return ret
    if __opts__['test']:
        ret['comment'] = 'Key set to have enabled status updated.'
        ret['result'] = None
        return ret
    if enabled:
        re = __salt__['boto_kms.enable_key'](
            kms_key_id, region, key, keyid, profile
        )
        event = 'Enabled'
    else:
        re = __salt__['boto_kms.disable_key'](
            kms_key_id, region, key, keyid, profile
        )
        event = 'Disabled'
    if 'error' in re:
        ret['result'] = False
        ret['comment'] = 'Failed to update key enabled status: {0}.'.format(re['error']['message'])
    else:
        ret['comment'] = '{0} key.'.format(event)
    return ret


def _key_description(key_metadata, description, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    if key_metadata['Description'] == description:
        return ret
    if __opts__['test']:
        ret['comment'] = 'Key set to have description updated.'
        ret['result'] = None
        return ret
    rdu = __salt__['boto_kms.update_key_description'](
        key_metadata['KeyId'], description, region, key, keyid, profile
    )
    if 'error' in rdu:
        ret['result'] = False
        ret['comment'] = 'Failed to update key description: {0}.'.format(rdu['error']['message'])
    else:
        ret['comment'] = 'Updated key description.'
    return ret


def _key_rotation(key_metadata, key_rotation, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    kms_key_id = key_metadata['KeyId']
    rke = __salt__['boto_kms.get_key_rotation_status'](
        kms_key_id, region, key, keyid, profile
    )
    if rke['result'] == key_rotation:
        return ret
    if __opts__['test']:
        ret['comment'] = 'Key set to have key rotation policy updated.'
        ret['result'] = None
        return ret
    if not key_metadata['Enabled']:
        ret['comment'] = 'Key is disabled, not changing key rotation policy.'
        ret['result'] = None
        return ret
    if key_rotation:
        rk = __salt__['boto_kms.enable_key_rotation'](
            kms_key_id, region, key, keyid, profile
        )
    else:
        rk = __salt__['boto_kms.enable_key_rotation'](
            kms_key_id, region, key, keyid, profile
        )
    if 'error' in rk:
        # Just checking for the key being disabled isn't enough, since key
        # disabling is very eventually consistent, so we have a long race
        # condition to handle. We check the error message to see if the failure
        # was due to a key being disabled.
        if 'is disabled' in rk['error']['message']:
            msg = 'Key is disabled, not changing key rotation policy.'
            ret['result'] = None
            ret['comment'] = msg
            return ret
        ret['result'] = False
        ret['comment'] = 'Failed to set key rotation: {0}.'.format(rk['error']['message'])
    else:
        ret['changes'] = {'old': {'key_rotation': not key_rotation},
                          'new': {'key_rotation': key_rotation}}
        ret['comment'] = 'Set key rotation policy to {0}.'.format(key_rotation)
    return ret


def _key_policy(key_metadata, policy, region, key, keyid, profile):
    ret = {'result': True, 'comment': '', 'changes': {}}
    kms_key_id = key_metadata['KeyId']
    rkp = __salt__['boto_kms.get_key_policy'](
        kms_key_id, 'default', region, key, keyid, profile
    )
    if rkp['key_policy'] == policy:
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} Key set to have key policy updated.'.format(ret['comment'])
        ret['result'] = None
        return ret
    rpkp = __salt__['boto_kms.put_key_policy'](
        kms_key_id, 'default', policy, region, key, keyid, profile
    )
    if 'error' in rpkp:
        ret['result'] = False
        ret['comment'] = '{0} Failed to update key policy: {1}'.format(ret['comment'], rpkp['error']['message'])
    else:
        ret['comment'] = 'Updated key policy.'
    return ret
