# -*- coding: utf-8 -*-
'''
Manage IAM roles
================

.. versionadded:: 2014.7.0

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit IAM credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    iam.keyid: GKTADJGHEIQSXMKKRBJ08H
    iam.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

Creating a role will automatically create an instance profile and associate it
with the role. This is the default behavior of the AWS console.

.. code-block:: yaml

    myrole:
        boto_iam_role.present:
            - region: us-east-1
            - key: GKTADJGHEIQSXMKKRBJ08H
            - keyid: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            - policies_from_pillars:
                - shared_iam_bootstrap_policy
            - policies:
                MySQSPolicy:
                    Statement:
                      - Action:
                            - sqs:*
                        Effect: Allow
                        Resource:
                            - arn:aws:sqs:*:*:*
                        Sid: MyPolicySQS1
                MyS3Policy:
                    Statement:
                      - Action:
                            - s3:GetObject
                        Effect: Allow
                        Resource:
                            - arn:aws:s3:*:*:mybucket/*

    # Using a credentials profile from pillars
    myrole:
        boto_iam_role.present:
            - profile: myiamprofile

    # Passing in a credentials profile
    myrole:
        boto_iam_role.present:
            - profile:
                key: GKTADJGHEIQSXMKKRBJ08H
                keyid: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
                region: us-east-1

If ``delete_policies: False`` is specified, existing policies that are not in
the given list of policies will not be deleted. This allows manual modifications
on the IAM role to be persistent. This functionality was added in 2015.8.0.

.. note::

    When using the ``profile`` parameter and ``region`` is set outside of
    the profile group, region is ignored and a default region will be used.

    If ``region`` is missing from the ``profile`` data set, ``us-east-1``
    will be used as the default region.

'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import salt.utils.dictupdate as dictupdate
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_iam_role' if 'boto_iam.role_exists' in __salt__ else False


def present(
        name,
        policy_document=None,
        policy_document_from_pillars=None,
        path=None,
        policies=None,
        policies_from_pillars=None,
        managed_policies=None,
        create_instance_profile=True,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        delete_policies=True):
    '''
    Ensure the IAM role exists.

    name
        Name of the IAM role.

    policy_document
        The policy that grants an entity permission to assume the role. (See https://boto.readthedocs.io/en/latest/ref/iam.html#boto.iam.connection.IAMConnection.create_role)

    policy_document_from_pillars
        A pillar key that contains a role policy document. The statements
        defined here will be appended with the policy document statements
        defined in the policy_document argument.

        .. versionadded:: 2017.7.0

    path
        The path to the role/instance profile. (See https://boto.readthedocs.io/en/latest/ref/iam.html#boto.iam.connection.IAMConnection.create_role)

    policies
        A dict of IAM role policies.

    policies_from_pillars
        A list of pillars that contain role policy dicts. Policies in the
        pillars will be merged in the order defined in the list and key
        conflicts will be handled by later defined keys overriding earlier
        defined keys. The policies defined here will be merged with the
        policies defined in the policies argument. If keys conflict, the keys
        in the policies argument will override the keys defined in
        policies_from_pillars.

    managed_policies
        A list of (AWS or Customer) managed policies to be attached to the role.

    create_instance_profile
        A boolean of whether or not to create an instance profile and associate
        it with this role.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    delete_policies
        Deletes existing policies that are not in the given list of policies. Default
        value is ``True``. If ``False`` is specified, existing policies will not be deleted
        allowing manual modifications on the IAM role to be persistent.

        .. versionadded:: 2015.8.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    # Build up _policy_document
    _policy_document = {}
    if policy_document_from_pillars:
        from_pillars = __salt__['pillar.get'](policy_document_from_pillars)
        if from_pillars:
            _policy_document['Version'] = from_pillars['Version']
            _policy_document.setdefault('Statement', [])
            _policy_document['Statement'].extend(from_pillars['Statement'])
    if policy_document:
        _policy_document['Version'] = policy_document['Version']
        _policy_document.setdefault('Statement', [])
        _policy_document['Statement'].extend(policy_document['Statement'])
    _ret = _role_present(name, _policy_document, path, region, key, keyid,
                         profile)

    # Build up _policies
    if not policies:
        policies = {}
    if not policies_from_pillars:
        policies_from_pillars = []
    if not managed_policies:
        managed_policies = []
    _policies = {}
    for policy in policies_from_pillars:
        _policy = __salt__['pillar.get'](policy)
        _policies.update(_policy)
    _policies.update(policies)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    if create_instance_profile:
        _ret = _instance_profile_present(name, region, key, keyid, profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
        _ret = _instance_profile_associated(name, region, key, keyid, profile)
        ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
        ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
        if not _ret['result']:
            ret['result'] = _ret['result']
            if ret['result'] is False:
                return ret
    _ret = _policies_present(name, _policies, region, key, keyid, profile,
                             delete_policies)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    _ret = _policies_attached(name, managed_policies, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _role_present(
        name,
        policy_document=None,
        path=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    role = __salt__['boto_iam.describe_role'](name, region, key, keyid,
                                              profile)
    if not role:
        if __opts__['test']:
            ret['comment'] = 'IAM role {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_role'](name, policy_document,
                                                   path, region, key,
                                                   keyid, profile)
        if created:
            ret['changes']['old'] = {'role': None}
            ret['changes']['new'] = {'role': name}
            ret['comment'] = 'IAM role {0} created.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} IAM role.'.format(name)
    else:
        ret['comment'] = '{0} role present.'.format(name)
        update_needed = False
        _policy_document = None
        if not policy_document:
            policy = __salt__['boto_iam.build_policy'](region, key, keyid,
                                                       profile)
            if _sort_policy(role['assume_role_policy_document']) != _sort_policy(policy):
                update_needed = True
                _policy_document = policy
        else:
            if _sort_policy(role['assume_role_policy_document']) != _sort_policy(policy_document):
                update_needed = True
                _policy_document = policy_document
        if update_needed:
            if __opts__['test']:
                msg = 'Assume role policy document to be updated.'
                ret['comment'] = '{0} {1}'.format(ret['comment'], msg)
                ret['result'] = None
                return ret
            updated = __salt__['boto_iam.update_assume_role_policy'](
                name, _policy_document, region, key, keyid, profile
            )
            if updated:
                msg = 'Assume role policy document updated.'
                ret['comment'] = '{0} {1}'.format(ret['comment'], msg)
                ret['changes']['old'] = {'policy_document': role['assume_role_policy_document']}
                ret['changes']['new'] = {'policy_document': _policy_document}
            else:
                ret['result'] = False
                msg = 'Failed to update assume role policy.'
                ret['comment'] = '{0} {1}'.format(ret['comment'], msg)
    return ret


def _instance_profile_present(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.instance_profile_exists'](name, region, key,
                                                          keyid, profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Instance profile {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_instance_profile'](name, region,
                                                               key, keyid,
                                                               profile)
        if created:
            ret['changes']['old'] = {'instance_profile': None}
            ret['changes']['new'] = {'instance_profile': name}
            ret['comment'] = 'Instance profile {0} created.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} instance profile.'.format(name)
    return ret


def _instance_profile_associated(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    is_associated = __salt__['boto_iam.profile_associated'](name, name, region,
                                                            key, keyid,
                                                            profile)
    if not is_associated:
        if __opts__['test']:
            ret['comment'] = 'Instance profile {0} is set to be associated.'.format(name)
            ret['result'] = None
            return ret
        associated = __salt__['boto_iam.associate_profile_to_role'](name, name,
                                                                    region,
                                                                    key, keyid,
                                                                    profile)
        if associated:
            ret['changes']['old'] = {'profile_associated': None}
            ret['changes']['new'] = {'profile_associated': True}
            ret['comment'] = 'Instance profile {0} associated.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to associate {0} instance profile with {0} role.'.format(name)
    return ret


def _sort_policy(doc):
    # List-type sub-items in policies don't happen to be order-sensitive, but
    # compare operations will render them unequal, leading to non-idempotent
    # state runs.  We'll sort any list-type subitems before comparison to reduce
    # the likelihood of false negatives.
    if isinstance(doc, list):
        return sorted([_sort_policy(i) for i in doc])
    elif isinstance(doc, dict):
        return dict([(k, _sort_policy(v)) for k, v in doc.items()])
    else:
        return doc


def _policies_present(
        name,
        policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        delete_policies=True):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_create = {}
    policies_to_delete = []
    for policy_name, policy in six.iteritems(policies):
        _policy = __salt__['boto_iam.get_role_policy'](name, policy_name,
                                                       region, key, keyid,
                                                       profile)
        if _policy != policy:
            policies_to_create[policy_name] = policy
    _list = __salt__['boto_iam.list_role_policies'](name, region, key, keyid,
                                                    profile)
    for policy_name in _list:
        if delete_policies and policy_name not in policies:
            policies_to_delete.append(policy_name)
    if policies_to_create or policies_to_delete:
        _to_modify = list(policies_to_delete)
        _to_modify.extend(policies_to_create)
        if __opts__['test']:
            ret['comment'] = '{0} policies to be modified on role {1}.'.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'policies': _list}
        for policy_name, policy in six.iteritems(policies_to_create):
            policy_set = __salt__['boto_iam.create_role_policy'](name,
                                                                 policy_name,
                                                                 policy,
                                                                 region, key,
                                                                 keyid,
                                                                 profile)
            if not policy_set:
                _list = __salt__['boto_iam.list_role_policies'](name, region,
                                                                key, keyid,
                                                                profile)
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                ret['comment'] = 'Failed to add policy {0} to role {1}'.format(policy_name, name)
                return ret
        for policy_name in policies_to_delete:
            policy_unset = __salt__['boto_iam.delete_role_policy'](name,
                                                                   policy_name,
                                                                   region, key,
                                                                   keyid,
                                                                   profile)
            if not policy_unset:
                _list = __salt__['boto_iam.list_role_policies'](name, region,
                                                                key, keyid,
                                                                profile)
                ret['changes']['new'] = {'policies': _list}
                ret['result'] = False
                ret['comment'] = 'Failed to remove policy {0} from role {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.list_role_policies'](name, region, key,
                                                        keyid, profile)
        ret['changes']['new'] = {'policies': _list}
        ret['comment'] = '{0} policies modified on role {1}.'.format(', '.join(_list), name)
    return ret


def _policies_attached(
        name,
        managed_policies=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    policies_to_attach = []
    policies_to_detach = []
    for policy in managed_policies or []:
        entities = __salt__['boto_iam.list_entities_for_policy'](policy,
                                       entity_filter='Role',
                                       region=region, key=key, keyid=keyid,
                                       profile=profile)
        found = False
        for roledict in entities.get('policy_roles', []):
            if name == roledict.get('role_name'):
                found = True
                break
        if not found:
            policies_to_attach.append(policy)
    _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region, key=key, keyid=keyid,
                                                    profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    for policy_data in _list:
        if policy_data.get('policy_name') not in managed_policies \
                  and policy_data.get('policy_arn') not in managed_policies:
            policies_to_detach.append(policy_data.get('policy_arn'))
    if policies_to_attach or policies_to_detach:
        _to_modify = list(policies_to_detach)
        _to_modify.extend(policies_to_attach)
        if __opts__['test']:
            ret['comment'] = '{0} policies to be modified on role {1}.'.format(', '.join(_to_modify), name)
            ret['result'] = None
            return ret
        ret['changes']['old'] = {'managed_policies': oldpolicies}
        for policy_name in policies_to_attach:
            policy_set = __salt__['boto_iam.attach_role_policy'](policy_name,
                                                                 role_name=name,
                                                                 region=region,
                                                                 key=key,
                                                                 keyid=keyid,
                                                                 profile=profile)
            if not policy_set:
                _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region,
                                                                key=key,
                                                                keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to add policy {0} to role {1}'.format(policy_name, name)
                return ret
        for policy_name in policies_to_detach:
            policy_unset = __salt__['boto_iam.detach_role_policy'](policy_name,
                                                                   role_name=name,
                                                                   region=region,
                                                                   key=key,
                                                                   keyid=keyid,
                                                                   profile=profile)
            if not policy_unset:
                _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region,
                                                                key=key,
                                                                keyid=keyid,
                                                                profile=profile)
                newpolicies = [x.get('policy_arn') for x in _list]
                ret['changes']['new'] = {'managed_policies': newpolicies}
                ret['result'] = False
                ret['comment'] = 'Failed to remove policy {0} from role {1}'.format(policy_name, name)
                return ret
        _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region, key=key,
                                                        keyid=keyid,
                                                        profile=profile)
        newpolicies = [x.get('policy_arn') for x in _list]
        log.debug(newpolicies)
        ret['changes']['new'] = {'managed_policies': newpolicies}
        ret['comment'] = '{0} policies modified on role {1}.'.format(', '.join(newpolicies), name)
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the IAM role is deleted.

    name
        Name of the IAM role.

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
    _ret = _policies_absent(name, region, key, keyid, profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _policies_detached(name, region, key, keyid, profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _instance_profile_disassociated(name, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _instance_profile_absent(name, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _role_absent(name, region, key, keyid, profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
    return ret


def _role_absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}

    exists = __salt__['boto_iam.role_exists'](name, region, key, keyid,
                                              profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'IAM role {0} is set to be removed.'.format(
                name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_iam.delete_role'](name, region, key, keyid,
                                                   profile)
        if deleted:
            ret['changes']['old'] = {'role': name}
            ret['changes']['new'] = {'role': None}
            ret['comment'] = 'IAM role {0} removed.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} iam role.'.format(name)
    else:
        ret['comment'] = '{0} role does not exist.'.format(name)
    return ret


def _instance_profile_absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}

    exists = __salt__['boto_iam.instance_profile_exists'](name, region, key,
                                                          keyid, profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'Instance profile {0} is set to be removed.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_iam.delete_instance_profile'](name, region,
                                                               key, keyid,
                                                               profile)
        if deleted:
            ret['changes']['old'] = {'instance_profile': name}
            ret['changes']['new'] = {'instance_profile': None}
            ret['comment'] = 'Instance profile {0} removed.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} instance profile.'.format(name)
    else:
        ret['comment'] = '{0} instance profile does not exist.'.format(name)
    return ret


def _policies_absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    _list = __salt__['boto_iam.list_role_policies'](name, region, key, keyid,
                                                    profile)
    if not _list:
        ret['comment'] = 'No policies in role {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be removed from role {1}.'.format(', '.join(_list), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'policies': _list}
    for policy_name in _list:
        policy_unset = __salt__['boto_iam.delete_role_policy'](name,
                                                               policy_name,
                                                               region, key,
                                                               keyid,
                                                               profile)
        if not policy_unset:
            _list = __salt__['boto_iam.list_role_policies'](name, region,
                                                            key, keyid,
                                                            profile)
            ret['changes']['new'] = {'policies': _list}
            ret['result'] = False
            ret['comment'] = 'Failed to add policy {0} to role {1}'.format(policy_name, name)
            return ret
    _list = __salt__['boto_iam.list_role_policies'](name, region, key,
                                                    keyid, profile)
    ret['changes']['new'] = {'policies': _list}
    ret['comment'] = '{0} policies removed from role {1}.'.format(', '.join(_list), name)
    return ret


def _policies_detached(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    _list = __salt__['boto_iam.list_attached_role_policies'](role_name=name,
                        region=region, key=key, keyid=keyid, profile=profile)
    oldpolicies = [x.get('policy_arn') for x in _list]
    if not _list:
        ret['comment'] = 'No attached policies in role {0}.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = '{0} policies to be detached from role {1}.'.format(', '.join(oldpolicies), name)
        ret['result'] = None
        return ret
    ret['changes']['old'] = {'managed_policies': oldpolicies}
    for policy_arn in oldpolicies:
        policy_unset = __salt__['boto_iam.detach_role_policy'](policy_arn,
                                                               name,
                                                               region=region,
                                                               key=key,
                                                               keyid=keyid,
                                                               profile=profile)
        if not policy_unset:
            _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region,
                                                            key=key, keyid=keyid,
                                                            profile=profile)
            newpolicies = [x.get('policy_arn') for x in _list]
            ret['changes']['new'] = {'managed_policies': newpolicies}
            ret['result'] = False
            ret['comment'] = 'Failed to detach {0} from role {1}'.format(policy_arn, name)
            return ret
    _list = __salt__['boto_iam.list_attached_role_policies'](name, region=region, key=key,
                                                    keyid=keyid, profile=profile)
    newpolicies = [x.get('policy_arn') for x in _list]
    ret['changes']['new'] = {'managed_policies': newpolicies}
    ret['comment'] = '{0} policies detached from role {1}.'.format(', '.join(newpolicies), name)
    return ret


def _instance_profile_disassociated(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    ret = {'result': True, 'comment': '', 'changes': {}}
    is_associated = __salt__['boto_iam.profile_associated'](name, name, region,
                                                            key, keyid,
                                                            profile)
    if is_associated:
        if __opts__['test']:
            ret['comment'] = 'Instance profile {0} is set to be disassociated.'.format(name)
            ret['result'] = None
            return ret
        associated = __salt__['boto_iam.disassociate_profile_from_role'](name, name, region, key, keyid, profile)
        if associated:
            ret['changes']['old'] = {'profile_associated': True}
            ret['changes']['new'] = {'profile_associated': False}
            ret['comment'] = 'Instance profile {0} disassociated.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to disassociate {0} instance profile from {0} role.'.format(name)
    return ret
