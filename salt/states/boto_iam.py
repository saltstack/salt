# -*- coding: utf-8 -*-
'''
Manage IAM roles.
=================

.. versionadded:: Beryllium

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit IAM credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    delete-user:
      boto_iam.user_absent:
        - name: myuser

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
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'safsdfsal;fdkjsafkljsASSADFalkfj'

.. code-block:: yaml

    create server certificate:
      boto_iam.server_cert_present:
        - name: mycert
        - public_key: salt://base/mycert.crt
        - private_key: salt://base/mycert.key
        - cert_chain: salt://base/mycert_chain.crt
        - region: eu-west-1
        - keyid: 'AKIAJHTMIQ2ASDFLASDF'
        - key: 'fdkjsafkljsASSADFalkfjasdf'

.. code-block:: yaml
    delete server certificate:
      boto_iam.server_cert_absent:
        - name: mycert
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import json
import os

# Import Salt Libs
import salt.utils.odict as odict

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_iam.get_user' in __salt__


def user_absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM user is absent

    name (string) – The name of the new user.

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string)
    that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not __salt__['boto_iam.get_user'](name, region, key, keyid, profile):
        ret['result'] = True
        ret['comment'] = 'IAM User {0} does not exist.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'IAM user {0} is set to be deleted.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_user'](name, region, key, keyid, profile)
    if deleted is True:
        ret['comment'] = 'IAM user {0} is deleted.'.format(name)
        ret['result'] = True
        ret['changes']['deleted'] = name
        return ret
    ret['comment'] = 'IAM user {0} could not be deleted.\n {1}'.format(name, deleted)
    ret['result'] = False
    return ret


def user_present(name, password=None, path=None, group=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM user is present

    name (string) – The name of the new user.

    password (string) - The password for the new user. Must comply with account policy.

    path (string) - The path of the user. Default is '/'

    group (string) - The name of the group to add the user to.

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string)
    that contains a dict with region, key and keyid.
    '''
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
            ret['comment'] = os.linesep.join([ret['comment'], 'User {0} has been created.'.format(name)])
            if password:
                ret = _case_password(ret, name, password, region, key, keyid, profile)
            if group:
                ret = _case_group(ret, name, group, region, key, keyid, profile)
    else:
        ret['comment'] = os.linesep.join([ret['comment'], 'User {0} is present.'.format(name)])
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
            ret['comment'] = os.linesep.join([ret['comment'], 'Login profile for user {0} exists.'.format(name)])
        else:
            ret['comment'] = os.linesep.join([ret['comment'], 'Password has been added to User {0}.'.format(name)])
            ret['changes']['password'] = password
    else:
        ret['result'] = False
        ret['comment'] = os.linesep.join([ret['comment'], 'Password for user {0} could not be set.\nPlease check your password policy.'.format(name)])
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
            ret['comment'] = os.linesep.join([ret['comment'], 'User {0} is already a member of group {1}.'.format(name, group)])
        else:
            ret['comment'] = os.linesep.join([ret['comment'], 'User {0} has been added to group {1}.'.format(name, group)])
            ret['changes']['group'] = name
    else:
        ret['result'] = False
        ret['comment'] = os.linesep.join([ret['comment'], 'Group {0} does not exist.'.format(group)])
    return ret


def group_present(name, policy_name=None, policy=None, users=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the IAM group is present

    name (string) – The name of the new group.

    policy_name (string) - The policy document to add to the group.

    users (list) - A list of users to be added to the group.

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string)
    that contains a dict with region, key and keyid.
    '''
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
            ret['comment'] = os.linesep.join([ret['comment'], 'Group {0} has been created.'.format(name)])
            if policy_name and policy:
                ret = _case_policy(ret, name, policy_name, policy, region, key, keyid, profile)
            if users:
                log.debug('users are : {0}'.format(users))
                for user in users:
                    log.debug('user is : {0}'.format(user))
                    ret = _case_group(ret, user, name, region, key, keyid, profile)
    else:
        ret['comment'] = os.linesep.join([ret['comment'], 'Group {0} is present.'.format(name)])
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
        if not isinstance(policy, str):
            policy = json.loads(policy, object_pairs_hook=odict.OrderedDict)
        log.debug('policy is  : {0}'.format(policy))
        if exists == policy:
            ret['comment'] = os.linesep.join([ret['comment'], 'Policy {0} is present.'.format(group_name)])
        else:
            if __opts__['test']:
                ret['comment'] = 'Group policy {0} is set to be updated.'.format(policy_name)
                ret['result'] = None
                return ret
            __salt__['boto_iam.put_group_policy'](group_name, policy_name, policy, region, key, keyid, profile)
            ret['comment'] = os.linesep.join([ret['comment'], 'Policy {0} has been added to group {1}.'.format(policy_name, group_name)])
            ret['changes']['policy_name'] = policy
    else:
        if __opts__['test']:
            ret['comment'] = 'Group policy {0} is set to be created.'.format(policy_name)
            ret['result'] = None
            return ret
        __salt__['boto_iam.put_group_policy'](group_name, policy_name, policy, region, key, keyid, profile)
        ret['comment'] = os.linesep.join([ret['comment'], 'Policy {0} has been added to group {1}.'.format(policy_name, group_name)])
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
    '''
    Change account policy

    allow_users_to_change_password (bool) – Allows all IAM users in your account to
    use the AWS Management Console to change their own passwords.

    hard_expiry (bool) – Prevents IAM users from setting a new password after their
    password has expired.

    max_password_age (int) – The number of days that an IAM user password is valid.

    minimum_password_length (int) – The minimum number of characters allowed in an
    IAM user password.

    password_reuse_prevention (int) – Specifies the number of previous passwords
    that IAM users are prevented from reusing.

    require_lowercase_characters (bool) – Specifies whether IAM user passwords
    must contain at least one lowercase character from the ISO basic Latin alphabet (a to z).

    require_numbers (bool) – Specifies whether IAM user passwords must contain at
    least one numeric character (0 to 9).

    require_symbols (bool) – Specifies whether IAM user passwords must contain at
    least one of the following non-alphanumeric characters: ! @ # $ % ^ & * ( ) _ + - = [ ] { } | '

    require_uppercase_characters (bool) – Specifies whether IAM user passwords must
    contain at least one uppercase character from the ISO basic Latin alphabet (A to Z).

    region (string) - Region to connect to.

    key (string) - Secret key to be used.

    keyid (string) - Access key to be used.

    profile (dict) - A dict with region, key and keyid, or a pillar key (string)
    '''
    config = locals()
    ret = {'name': 'Account Policy', 'result': True, 'comment': '', 'changes': {}}
    info = __salt__['boto_iam.get_account_policy'](region, key, keyid, profile)
    if not info:
        ret['comment'] = 'Account policy is not Enabled.'
        ret['result'] = False
        return ret
    for key, value in config.iteritems():
        if key == 'region' or key == 'key' or key == 'keyid' or key == 'profile':
            continue
        if value is not None and str(info[key]) != str(value).lower():
            ret['comment'] = os.linesep.join([ret['comment'], 'Policy value {0} has been set to {1}.'.format(value, info[key])])
            ret['changes'][key] = str(value).lower()
    if not ret['changes']:
        ret['comment'] = 'Account policy is not changed.'
        return ret
    if __opts__['test']:
        ret['comment'] = 'Account policy is set to be changed.'
        ret['result'] = None
        return ret
    if __salt__['boto_iam.update_account_password_policy'](allow_users_to_change_password,
                                                           hard_expiry,
                                                           max_password_age,
                                                           minimum_password_length,
                                                           password_reuse_prevention,
                                                           require_lowercase_characters,
                                                           require_numbers,
                                                           require_symbols,
                                                           require_uppercase_characters,
                                                           region, key, keyid, profile):
        return ret
    ret['comment'] = 'Account policy is not changed'
    ret['changes'] = None
    ret['result'] = False
    return ret


def server_cert_absent(name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a server certificate

    name (string) - The name for the server certificate. Do not include the path in this value.

    region (string) - The name of the region to connect to.

    key (string) - The key to be used in order to connect

    keyid (string) - The keyid to be used in order to connect

    profile (string) - The profile that contains a dict of region, key, keyid
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_server_certificate'](name, region, key, keyid, profile)
    if not exists:
        ret['comment'] = 'Certificate {0} does not exist.'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Server certificate {0} is set to be deleted.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_iam.delete_server_cert'](name, region, key, keyid, profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Certificate {0} failed to be deleted.'.format(name)
        return ret
    ret['comment'] = 'Certificate {0} was deleted.'.format(name)
    ret['changes'] = deleted
    return ret


def server_cert_present(name, public_key, private_key, cert_chain=None, path=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    name (string) - The name for the server certificate. Do not include the path in this value.

    public_key (string) -  The contents of the public key certificate in PEM-encoded format.

    private_key (string) - The contents of the private key in PEM-encoded format.

    cert_chain (string) - The contents of the certificate chain. This is typically a
    concatenation of the PEM-encoded public key certificates of the chain.

    path (string) - The path for the server certificate.

    region (string) - The name of the region to connect to.

    key (string) - The key to be used in order to connect

    keyid (string) - The keyid to be used in order to connect

    profile (string) - The profile that contains a dict of region, key, keyid
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    exists = __salt__['boto_iam.get_server_certificate'](name, region, key, keyid, profile)
    log.debug('variables are : {0}'.format(locals()))
    if exists:
        ret['comment'] = 'Certificate {0} exists.'.format(name)
        return ret
    if 'salt://' in public_key:
        try:
            public_key = __salt__['cp.get_file_str'](public_key)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(public_key)
            ret['result'] = False
            return ret
    if 'salt://' in private_key:
        try:
            private_key = __salt__['cp.get_file_str'](private_key)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(private_key)
            ret['result'] = False
            return ret
    if cert_chain is not None and 'salt://' in cert_chain:
        try:
            cert_chain = __salt__['cp.get_file_str'](cert_chain)
        except IOError as e:
            log.debug(e)
            ret['comment'] = 'File {0} not found.'.format(cert_chain)
            ret['result'] = False
            return ret
    if __opts__['test']:
        ret['comment'] = 'Server certificate {0} is set to be created.'.format(name)
        ret['result'] = None
        return ret
    created = __salt__['boto_iam.upload_server_cert'](name, public_key, private_key, cert_chain,
                                                      path, region, key, keyid, profile)
    if created is not False:
        ret['comment'] = 'Certificate {0} was created.'.format(name)
        ret['changes'] = created
        return ret
    ret['result'] = False
    ret['comment'] = 'Certificate {0} failed to be created.'.format(name)
    return ret
