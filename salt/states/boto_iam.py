# -*- coding: utf-8 -*-
'''
Manage IAM roles.
=================

.. versionadded:: TBD

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit IAM credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    create-user:
      boto_iam.user_present:
        - name: myuser
        - password: NewPassword$$1
        - group: mygroup
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'

.. code-block:: yaml

    create-group:
      boto_iam.group_present:
        - name: mygroup
        - users:
          - myuser
          - myuser1
        - policy_name: test1
        - policy: '{ "Version": "2012-10-17", "Statement": [ { "Effect": "Allow", "Action": "*", "Resource": "*" }]}'
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'safsdfsal;fdkjsafkljsASSADFalkfj'

.. code-block:: yaml

    change-policy:
      boto_iam.account_policy:
        - change_password: True
'''

import logging
import json
import salt.utils.odict as odict
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_iam' if 'boto_iam.get_user' in __salt__ else False


def user_present(name, password=None, path=None, group=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_user'](name, region, key, keyid, profile)
    log.debug('getuser is {0}'.format(exists))
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'IAM user {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_user'](name, path, region, key, keyid, profile)
        if created:
            ret['changes']['user'] = created
            ret['comment'] = '\n'.join([ret['comment'], 'User {0} has been created.'.format(name)])
            if password:
                ret = _case_password(ret, name, password, region, key, keyid, profile)
            if group:
                ret = _case_group(ret, name, group, region, key, keyid, profile)
    else:
        ret['comment'] = '\n'.join([ret['comment'], 'User {0} is present.'.format(name)])
        if password:
            ret = _case_password(ret, name, password, region, key, keyid, profile)
        if group:
            ret = _case_group(ret, name, group, region, key, keyid, profile)
    return ret


def _case_password(ret, name, password, region=None, key=None, keyid=None, profile=None):
    if __opts__['test']:
        ret['comment'] = 'Login policy for {0} is set to be changed.'.format(name)
        ret['result'] = None
        return ret
    login = __salt__['boto_iam.create_login_profile'](name, password, region, key, keyid, profile)
    log.debug('login is : {0}'.format(login))
    if login:
        if 'Conflict' in login:
            ret['comment'] = '\n'.join([ret['comment'], 'Login profile for user {0} exists.'.format(name)])
        else:
            ret['comment'] = '\n'.join([ret['comment'], 'Password has been added to User {0}.'.format(name)])
            ret['changes']['password'] = password
    else:
        ret['result'] = False
        ret['comment'] = '\n'.join([ret['comment'], 'Password for user {0} could not be set.\nPlease check your password policy'.format(name)])
    return ret


def _case_group(ret, name, group, region=None, key=None, keyid=None, profile=None):
    exists = __salt__['boto_iam.get_group'](group_name=group, region=region, key=key, keyid=keyid, profile=profile)
    if exists:
        if __opts__['test']:
            ret['comment'] = 'Group {0} is set to be created.'.format(group)
            ret['result'] = None
            return ret
        result = __salt__['boto_iam.add_user_to_group'](name, group, region, key, keyid, profile)
        log.debug('result of the group is : {0} '.format(result))
        if 'Exists' in result:
            ret['comment'] = '\n'.join([ret['comment'], 'User {0} is already a member of group {1}.'.format(name, group)])
        else:
            ret['comment'] = '\n'.join([ret['comment'], 'User {0} has been added to group {1}.'.format(name, group)])
            ret['changes']['group'] = name
    else:
        ret['result'] = False
        ret['comment'] = '\n'.join([ret['comment'], 'Group {0} does not exist.'.format(group)])
    return ret


def group_present(name, policy_name=None, policy=None, users=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_group'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'IAM user {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_iam.create_group'](group_name=name, region=region, key=key, keyid=keyid, profile=profile)
        if created:
            ret['changes']['group'] = created
            ret['comment'] = '\n'.join([ret['comment'], 'Group {0} has been created.'.format(name)])
            if policy_name and policy:
                ret = _case_policy(ret, name, policy_name, policy, region, key, keyid, profile)
            if users:
                log.debug('users are : {0}'.format(users))
                for user in users:
                    log.debug('user is : {0}'.format(user))
                    ret = _case_group(ret, user, name, region, key, keyid, profile)
    else:
        ret['comment'] = '\n'.join([ret['comment'], 'Group {0} is present.'.format(name)])
        if policy_name and policy:
            ret = _case_policy(ret, name, policy_name, policy, region, key, keyid, profile)
        if users:
            log.debug('users are : {0}'.format(users))
            for user in users:
                log.debug('user is : {0}'.format(user))
                ret = _case_group(ret, user, name, region, key, keyid, profile)
    return ret


def _case_policy(ret, group_name, policy_name, policy, region=None, key=None, keyid=None, profile=None):
    exists = __salt__['boto_iam.get_group_policy'](group_name, policy_name, region, key, keyid, profile)
    if exists:
        log.debug('exists is : {0}'.format(exists))
        policy = json.loads(policy, object_pairs_hook=odict.OrderedDict)
        log.debug('policy is  : {0}'.format(policy))
        if exists == policy:
            ret['comment'] = '\n'.join([ret['comment'], 'Policy {0} is present.'.format(group_name)])
        else:
            if __opts__['test']:
                ret['comment'] = 'Group policy {0} is set to be updated.'.format(policy_name)
                ret['result'] = None
                return ret
            __salt__['boto_iam.put_group_policy'](group_name, policy_name, policy, region, key, keyid, profile)
            ret['comment'] = '\n'.join([ret['comment'], 'Policy {0} has been added to group {1}.'.format(policy_name, group_name)])
            ret['changes']['policy_name'] = policy
    else:
        if __opts__['test']:
            ret['comment'] = 'Group policy {0} is set to be created.'.format(policy_name)
            ret['result'] = None
            return ret
        __salt__['boto_iam.put_group_policy'](group_name, policy_name, policy, region, key, keyid, profile)
        ret['comment'] = '\n'.join([ret['comment'], 'Policy {0} has been added to group {1}.'.format(policy_name, group_name)])
        ret['changes'][policy_name] = policy
    return ret


def account_policy(allow_users_to_change_password=None, hard_expiry=None, max_password_age=None,
                   minimum_password_length=None,
                   password_reuse_prevention=None,
                   require_lowercase_characters=None,
                   require_numbers=None, require_symbols=None,
                   require_uppercase_characters=None,
                   region=None, key=None, keyid=None,
                   profile=None):
    config = locals()
    ret = {'name': 'Account Policy', 'result': True, 'comment': '', 'changes': {}}
    info = __salt__['boto_iam.get_account_policy'](region, key, keyid, profile)
    for key, value in config.iteritems():
        if key == 'region' or key == 'key' or key == 'keyid' or key == 'profile':
            continue
        if value is not None and str(info[key]) != str(value).lower():
            ret['comment'] = '\n'.join([ret['comment'], 'Policy value {0} has been set to {1}.'.format(value, info[key])])
            ret['changes'][key] = str(value).lower()
    if not ret['changes']:
        ret['comment'] = 'Account policy is not changed'
        return ret
    if __opts__['test']:
        ret['comment'] = 'Account policy is set to be changed'
        ret['result'] = None
        return ret
    __salt__['boto_iam.update_account_password_policy'](allow_users_to_change_password,
                                                        hard_expiry,
                                                        max_password_age,
                                                        minimum_password_length,
                                                        password_reuse_prevention,
                                                        require_lowercase_characters,
                                                        require_numbers,
                                                        require_symbols,
                                                        require_uppercase_characters,
                                                        region, key, keyid, profile)
    return ret
