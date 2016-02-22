# -*- coding: utf-8 -*-
'''
Connection module for Amazon IAM

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit iam credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        iam.keyid: GKTADJGHEIQSXMKKRBJ08H
        iam.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        iam.region: us-east-1

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import json
import yaml

# Import salt libs
import salt.utils.compat
import salt.utils.odict as odict
import salt.utils.boto

# Import third party libs
# pylint: disable=unused-import
from salt.ext.six import string_types
from salt.ext.six.moves.urllib.parse import unquote as _unquote  # pylint: disable=no-name-in-module
try:
    import boto
    import boto.iam
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=unused-import

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return (False, 'The boto_iam module could not be loaded: boto libraries not found')
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto.assign_funcs'](__name__, 'iam', pack=__salt__)


def instance_profile_exists(name, region=None, key=None, keyid=None,
                            profile=None):
    '''
    Check to see if an instance profile exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        # Boto weirdly returns an exception here if an instance profile doesn't
        # exist.
        conn.get_instance_profile(name)
        return True
    except boto.exception.BotoServerError:
        return False


def create_instance_profile(name, region=None, key=None, keyid=None,
                            profile=None):
    '''
    Create an instance profile.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_instance_profile myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if instance_profile_exists(name, region, key, keyid, profile):
        return True
    try:
        # This call returns an instance profile if successful and an exception
        # if not. It's annoying.
        conn.create_instance_profile(name)
        log.info('Created {0} instance profile.'.format(name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create {0} instance profile.'
        log.error(msg.format(name))
        return False
    return True


def delete_instance_profile(name, region=None, key=None, keyid=None,
                            profile=None):
    '''
    Delete an instance profile.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_instance_profile myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not instance_profile_exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_instance_profile(name)
        log.info('Deleted {0} instance profile.'.format(name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete {0} instance profile.'
        log.error(msg.format(name))
        return False
    return True


def role_exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an IAM role exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.role_exists myirole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.get_role(name)
        return True
    except boto.exception.BotoServerError:
        return False


def describe_role(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get information for a role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.describe_role myirole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_role(name)
        if not info:
            return False
        role = info.get_role_response.get_role_result.role
        role['assume_role_policy_document'] = json.loads(_unquote(
            role.assume_role_policy_document
        ))
        # If Sid wasn't defined by the user, boto will still return a Sid in
        # each policy. To properly check idempotently, let's remove the Sid
        # from the return if it's not actually set.
        for policy_key, policy in role['assume_role_policy_document'].items():
            if policy_key == 'Statement':
                for val in policy:
                    if 'Sid' in val and not val['Sid']:
                        del val['Sid']
        return role
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get {0} information.'
        log.error(msg.format(name))
        return False


def create_user(user_name, path=None, region=None, key=None, keyid=None,
                profile=None):
    '''
    Create a user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_user myuser
    '''
    if not path:
        path = '/'
    if get_user(user_name, region, key, keyid, profile):
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.create_user(user_name, path)
        log.info('Created user : {0}.'.format(user_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create user {0}.'
        log.error(msg.format(user_name))
        return False


def get_all_access_keys(user_name, marker=None, max_items=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Get all access keys from a user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_all_access_keys myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        return conn.get_all_access_keys(user_name, marker, max_items)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('Failed to get user\'s {0} access keys.'.format(user_name))
        return str(e)


def create_access_key(user_name, region=None, key=None, keyid=None, profile=None):
    '''
    Create access key id for a user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_access_key myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        return conn.create_access_key(user_name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('Failed to create access key.')
        return str(e)


def delete_access_key(access_key_id, user_name=None, region=None, key=None,
                      keyid=None, profile=None):
    '''
    Delete access key id from a user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_access_key myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        return conn.delete_access_key(access_key_id, user_name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('Failed to delete access key id {0}.'.format(access_key_id))
        return str(e)


def delete_user(user_name, region=None, key=None, keyid=None,
                profile=None):
    '''
    Delete a user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_user myuser
    '''
    if not get_user(user_name, region, key, keyid, profile):
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.delete_user(user_name)
        log.info('Deleted user : {0} .'.format(user_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        log.error('Failed to delete user {0}'.format(user_name))
        return str(e)


def get_user(user_name=None, region=None, key=None, keyid=None, profile=None):
    '''
    Get user information.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_user myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_user(user_name)
        if not info:
            return False
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get user {0} info.'
        log.error(msg.format(user_name))
        return False


def create_group(group_name, path=None, region=None, key=None, keyid=None,
                 profile=None):
    '''
    Create a group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_group group
    '''
    if not path:
        path = '/'
    if get_group(group_name, region=region, key=key, keyid=keyid,
                 profile=profile):
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.create_group(group_name, path)
        log.info('Created group : {0}.'.format(group_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create group {0}.'
        log.error(msg.format(group_name))
        return False


def get_group(group_name, region=None, key=None, keyid=None, profile=None):
    '''
    Get group information.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_group mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_group(group_name, max_items=1)
        if not info:
            return False
        return info['get_group_response']['get_group_result']['group']
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get group {0} info.'
        log.error(msg.format(group_name))
        return False


def get_group_members(group_name, region=None, key=None, keyid=None, profile=None):
    '''
    Get group information.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_group mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        marker = None
        truncated = True
        users = []
        while truncated:
            info = conn.get_group(group_name, marker=marker, max_items=1000)
            if not info:
                return False
            truncated = bool(info['get_group_response']['get_group_result']['is_truncated'])
            if truncated and 'marker' in info['get_group_response']['get_group_result']:
                marker = info['get_group_response']['get_group_result']['marker']
            else:
                marker = None
                truncated = False
            users += info['get_group_response']['get_group_result']['users']
        return users
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get group {0} members.'
        log.error(msg.format(group_name))
        return False


def add_user_to_group(user_name, group_name, region=None, key=None, keyid=None,
                      profile=None):
    '''
    Add user to group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.add_user_to_group myuser mygroup
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username : {0} does not exist.'
        log.error(msg.format(user_name, group_name))
        return False
    if user_exists_in_group(user_name, group_name, region=region, key=key,
                            keyid=keyid, profile=profile):
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.add_user_to_group(group_name, user_name)
        if not info:
            return False
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to add user {0} to group {1}.'
        log.error(msg.format(user_name, group_name))
        return False


def user_exists_in_group(user_name, group_name, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Check if user exists in group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.user_exists_in_group myuser mygroup
    '''
    # TODO this should probably use boto.iam.get_groups_for_user
    users = get_group_members(
        group_name=group_name, region=region, key=key, keyid=keyid,
        profile=profile
    )
    if users:
        for _user in users:
            if user_name == _user['user_name']:
                msg = 'Username : {0} is already in group {1}.'
                log.info(msg.format(user_name, group_name))
                return True
    return False


def remove_user_from_group(group_name, user_name, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Remove user from group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.remove_user_from_group mygroup myuser
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username : {0} does not exist.'
        log.error(msg.format(user_name, group_name))
        return False
    if not user_exists_in_group(user_name, group_name, region=region, key=key,
                                keyid=keyid, profile=profile):
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.remove_user_from_group(group_name, user_name)
        if not info:
            return False
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to remove user {0} from group {1}.'
        log.error(msg.format(user_name, group_name))
        return False


def put_group_policy(group_name, policy_name, policy_json, region=None, key=None,
                     keyid=None, profile=None):
    '''
    Adds or updates the specified policy document for the specified group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.put_group_policy mygroup policyname policyrules
    '''
    group = get_group(group_name, region=region, key=key, keyid=keyid,
                      profile=profile)
    if not group:
        log.error('Group {0} does not exist'.format(group_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        if not isinstance(policy_json, string_types):
            policy_json = json.dumps(policy_json)
        created = conn.put_group_policy(group_name, policy_name,
                                        policy_json)
        if created:
            log.info('Created policy for group {0}.'.format(group_name))
            return True
        msg = 'Could not create policy for group {0}'
        log.error(msg.format(group_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create policy for group {0}'
        log.error(msg.format(group_name))
    return False


def delete_group_policy(group_name, policy_name, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Delete a group policy.

    CLI Example::

    .. code-block:: bash

        salt myminion boto_iam.delete_group_policy mygroup mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    _policy = get_group_policy(
        group_name, policy_name, region, key, keyid, profile
    )
    if not _policy:
        return True
    try:
        conn.delete_group_policy(group_name, policy_name)
        msg = 'Successfully deleted {0} policy for group {1}.'
        log.info(msg.format(policy_name, group_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete {0} policy for group {1}.'
        log.error(msg.format(policy_name, group_name))
        return False


def get_group_policy(group_name, policy_name, region=None, key=None,
                     keyid=None, profile=None):
    '''
    Retrieves the specified policy document for the specified group.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_group_policy mygroup policyname
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_group_policy(group_name, policy_name)
        log.debug('info for group policy is : {0}'.format(info))
        if not info:
            return False
        info = info.get_group_policy_response.get_group_policy_result.policy_document
        info = _unquote(info)
        info = json.loads(info, object_pairs_hook=odict.OrderedDict)
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get group {0} info.'
        log.error(msg.format(group_name))
        return False


def get_all_group_policies(group_name, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Get a list of policy names from a group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_all_group_policies mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    try:
        response = conn.get_all_group_policies(group_name)
        _list = response.list_group_policies_response.list_group_policies_result
        return _list.policy_names
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return []


def delete_group(group_name, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Delete a group policy.

    CLI Example::

    .. code-block:: bash

        salt myminion boto_iam.delete_group mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    _group = get_group(
        group_name, region, key, keyid, profile
    )
    if not _group:
        return True
    try:
        conn.delete_group(group_name)
        msg = 'Successfully deleted group {0}.'
        log.info(msg.format(group_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete group {0}.'
        log.error(msg.format(group_name))
        return False


def create_login_profile(user_name, password, region=None, key=None,
                         keyid=None, profile=None):
    '''
    Creates a login profile for the specified user, give the user the
    ability to access AWS services and the AWS Management Console.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_login_profile user_name password
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username {0} does not exist'
        log.error(msg.format(user_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.create_login_profile(user_name, password)
        log.info('Created profile for user {0}.'.format(user_name))
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        if 'Conflict' in e:
            log.info('Profile already exists for user {0}.'.format(user_name))
            return 'Conflict'
        msg = 'Failed to update profile for user {0}.'
        log.error(msg.format(user_name))
        return False


def delete_login_profile(user_name, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Deletes a login profile for the specified user.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_login_profile user_name
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username {0} does not exist'
        log.error(msg.format(user_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.delete_login_profile(user_name)
        log.info('Deleted login profile for user {0}.'.format(user_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        if 'Not Found' in e:
            log.info('Login profile already deleted for user {0}.'.format(user_name))
            return True
        msg = 'Failed to delete login profile for user {0}.'
        log.error(msg.format(user_name))
        return False


def get_all_mfa_devices(user_name, region=None, key=None, keyid=None,
                        profile=None):
    '''
    Get all MFA devices associated with an IAM user.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_all_mfa_devices user_name
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username {0} does not exist'
        log.error(msg.format(user_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        result = conn.get_all_mfa_devices(user_name)
        devices = result['list_mfa_devices_response']['list_mfa_devices_result']['mfa_devices']
        return devices
    except boto.exception.BotoServerError as e:
        log.debug(e)
        if 'Not Found' in e:
            log.info('Could not find user {0}.'.format(user_name))
            return []
        msg = 'Failed to get all MFA devices for user {0}.'
        log.error(msg.format(user_name))
        return False


def deactivate_mfa_device(user_name, serial, region=None, key=None, keyid=None,
                          profile=None):
    '''
    Deactivates the specified MFA device and removes it from association with
    the user.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.deactivate_mfa_device user_name serial_num
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        msg = 'Username {0} does not exist'
        log.error(msg.format(user_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.deactivate_mfa_device(user_name, serial)
        log.info('Deactivated MFA device {1} for user {0}.'.format(user_name, serial))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        if 'Not Found' in e:
            log.info('MFA device {1} not associated with user {0}.'.format(user_name, serial))
            return True
        msg = 'Failed to deactivate MFA device {1} for user {0}.'
        log.error(msg.format(user_name, serial))
        return False


def update_account_password_policy(allow_users_to_change_password=None,
                                   hard_expiry=None, max_password_age=None,
                                   minimum_password_length=None,
                                   password_reuse_prevention=None,
                                   require_lowercase_characters=None,
                                   require_numbers=None, require_symbols=None,
                                   require_uppercase_characters=None,
                                   region=None, key=None, keyid=None,
                                   profile=None):
    '''
    Update the password policy for the AWS account.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.update_account_password_policy True
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.update_account_password_policy(allow_users_to_change_password,
                                            hard_expiry, max_password_age,
                                            minimum_password_length,
                                            password_reuse_prevention,
                                            require_lowercase_characters,
                                            require_numbers, require_symbols,
                                            require_uppercase_characters)
        log.info('The password policy has been updated.')
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update the password policy'
        log.error(msg)
        return False


def get_account_policy(region=None, key=None, keyid=None, profile=None):
    '''
    Get account policy for the AWS account.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_account_policy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_account_password_policy()
        return info.get_account_password_policy_response.get_account_password_policy_result.password_policy
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update the password policy.'
        log.error(msg)
        return False


def create_role(name, policy_document=None, path=None, region=None, key=None,
                keyid=None, profile=None):
    '''
    Create an instance role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_role myrole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if role_exists(name, region, key, keyid, profile):
        return True
    try:
        conn.create_role(name, assume_role_policy_document=policy_document,
                         path=path)
        log.info('Created {0} iam role.'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create {0} iam role.'
        log.error(msg.format(name))
        return False


def delete_role(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an IAM role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_role myirole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not role_exists(name, region, key, keyid, profile):
        return True
    try:
        conn.delete_role(name)
        log.info('Deleted {0} iam role.'.format(name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete {0} iam role.'
        log.error(msg.format(name))
        return False


def profile_associated(role_name, profile_name, region, key, keyid, profile):
    '''
    Check to see if an instance profile is associated with an IAM role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.profile_associated myirole myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    # The IAM module of boto doesn't return objects. Instead you need to grab
    # values through its properties. Sigh.
    try:
        profiles = conn.list_instance_profiles_for_role(role_name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False
    profiles = profiles.list_instance_profiles_for_role_response
    profiles = profiles.list_instance_profiles_for_role_result
    profiles = profiles.instance_profiles
    for profile in profiles:
        if profile.instance_profile_name == profile_name:
            return True
    return False


def associate_profile_to_role(profile_name, role_name, region=None, key=None,
                              keyid=None, profile=None):
    '''
    Associate an instance profile with an IAM role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.associate_profile_to_role myirole myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not role_exists(role_name, region, key, keyid, profile):
        log.error('IAM role {0} does not exist.'.format(role_name))
        return False
    if not instance_profile_exists(profile_name, region, key, keyid, profile):
        log.error('Instance profile {0} does not exist.'.format(profile_name))
        return False
    associated = profile_associated(role_name, profile_name, region, key, keyid, profile)
    if associated:
        return True
    else:
        try:
            conn.add_role_to_instance_profile(profile_name, role_name)
            msg = 'Added {0} instance profile to {1} role.'
            log.info(msg.format(profile_name, role_name))
            return True
        except boto.exception.BotoServerError as e:
            log.debug(e)
            msg = 'Failed to add {0} instance profile to {1} role.'
            log.error(msg.format(profile_name, role_name))
            return False


def disassociate_profile_from_role(profile_name, role_name, region=None,
                                   key=None, keyid=None, profile=None):
    '''
    Disassociate an instance profile from an IAM role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.disassociate_profile_from_role myirole myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not role_exists(role_name, region, key, keyid, profile):
        log.error('IAM role {0} does not exist.'.format(role_name))
        return False
    if not instance_profile_exists(profile_name, region, key, keyid, profile):
        log.error('Instance profile {0} does not exist.'.format(profile_name))
        return False
    associated = profile_associated(role_name, profile_name, region, key, keyid, profile)
    if not associated:
        return True
    else:
        try:
            conn.remove_role_from_instance_profile(profile_name, role_name)
            msg = 'Removed {0} instance profile from {1} role.'
            log.info(msg.format(profile_name, role_name))
            return True
        except boto.exception.BotoServerError as e:
            log.debug(e)
            msg = 'Failed to remove {0} instance profile from {1} role.'
            log.error(msg.format(profile_name, role_name))
            return False


def list_role_policies(role_name, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Get a list of policy names from a role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_role_policies myirole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        response = conn.list_role_policies(role_name)
        _list = response.list_role_policies_response.list_role_policies_result
        return _list.policy_names
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return []


def get_role_policy(role_name, policy_name, region=None, key=None,
                    keyid=None, profile=None):
    '''
    Get a role policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_role_policy myirole mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        _policy = conn.get_role_policy(role_name, policy_name)
        # I _hate_ you for not giving me an object boto.
        _policy = _policy.get_role_policy_response.policy_document
        # Policy is url encoded
        _policy = _unquote(_policy)
        _policy = json.loads(_policy, object_pairs_hook=odict.OrderedDict)
        return _policy
    except boto.exception.BotoServerError:
        return {}


def create_role_policy(role_name, policy_name, policy, region=None, key=None,
                       keyid=None, profile=None):
    '''
    Create or modify a role policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.create_role_policy myirole mypolicy '{"MyPolicy": "Statement": [{"Action": ["sqs:*"], "Effect": "Allow", "Resource": ["arn:aws:sqs:*:*:*"], "Sid": "MyPolicySqs1"}]}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _policy = get_role_policy(role_name, policy_name, region, key, keyid, profile)
    mode = 'create'
    if _policy:
        if _policy == policy:
            return True
        mode = 'modify'
    if isinstance(policy, string_types):
        policy = json.loads(policy, object_pairs_hook=odict.OrderedDict)
    try:
        _policy = json.dumps(policy)
        conn.put_role_policy(role_name, policy_name, _policy)
        if mode == 'create':
            msg = 'Successfully added {0} policy to {1} role.'
        else:
            msg = 'Successfully modified {0} policy for role {1}.'
        log.info(msg.format(policy_name, role_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to {0} {1} policy for role {2}.'
        log.error(msg.format(mode, policy_name, role_name))
        return False


def delete_role_policy(role_name, policy_name, region=None, key=None,
                       keyid=None, profile=None):
    '''
    Delete a role policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_role_policy myirole mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _policy = get_role_policy(role_name, policy_name, region, key, keyid, profile)
    if not _policy:
        return True
    try:
        conn.delete_role_policy(role_name, policy_name)
        msg = 'Successfully deleted {0} policy for role {1}.'
        log.info(msg.format(policy_name, role_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete {0} policy for role {1}.'
        log.error(msg.format(policy_name, role_name))
        return False


def update_assume_role_policy(role_name, policy_document, region=None,
                              key=None, keyid=None, profile=None):
    '''
    Update an assume role policy for a role.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.update_assume_role_policy myrole '{"Statement":"..."}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if isinstance(policy_document, string_types):
        policy_document = json.loads(policy_document,
                                     object_pairs_hook=odict.OrderedDict)
    try:
        _policy_document = json.dumps(policy_document)
        conn.update_assume_role_policy(role_name, _policy_document)
        msg = 'Successfully updated assume role policy for role {0}.'
        log.info(msg.format(role_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to update assume role policy for role {0}.'
        log.error(msg.format(role_name))
        return False


def build_policy(region=None, key=None, keyid=None, profile=None):
    '''
    Build a default assume role policy.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.build_policy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if hasattr(conn, 'build_policy'):
        policy = json.loads(conn.build_policy())
    elif hasattr(conn, '_build_policy'):
        policy = json.loads(conn._build_policy())
    else:
        return {}
    # The format we get from build_policy isn't going to be what we get back
    # from AWS for the exact same policy. AWS converts single item list values
    # into strings, so let's do the same here.
    for key, policy_val in policy.items():
        for statement in policy_val:
            if (isinstance(statement['Action'], list)
                    and len(statement['Action']) == 1):
                statement['Action'] = statement['Action'][0]
            if (isinstance(statement['Principal']['Service'], list)
                    and len(statement['Principal']['Service']) == 1):
                statement['Principal']['Service'] = statement['Principal']['Service'][0]
    # build_policy doesn't add a version field, which AWS is going to set to a
    # default value, when we get it back, so let's set it.
    policy['Version'] = '2008-10-17'
    return policy


def get_account_id(region=None, key=None, keyid=None, profile=None):
    '''
    Get a the AWS account id associated with the used credentials.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_account_id
    '''
    cache_key = 'boto_iam.account_id'
    if cache_key not in __context__:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        try:
            ret = conn.get_user()
            # The get_user call returns an user ARN:
            #    arn:aws:iam::027050522557:user/salt-test
            arn = ret['get_user_response']['get_user_result']['user']['arn']
        except boto.exception.BotoServerError:
            # If call failed, then let's try to get the ARN from the metadata
            timeout = boto.config.getfloat(
                'Boto', 'metadata_service_timeout', 1.0
            )
            attempts = boto.config.getint(
                'Boto', 'metadata_service_num_attempts', 1
            )
            metadata = boto.utils.get_instance_metadata(
                timeout=timeout, num_retries=attempts
            )
            try:
                arn = metadata['iam']['info']['InstanceProfileArn']
            except KeyError:
                log.error('Failed to get user or metadata ARN information in'
                          ' boto_iam.get_account_id.')
        __context__[cache_key] = arn.split(':')[4]
    return __context__[cache_key]


def get_all_user_policies(user_name, marker=None, max_items=None, region=None, key=None, keyid=None, profile=None):
    '''
    Get all user policies.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_group mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_all_user_policies(user_name, marker, max_items)
        if not info:
            return False
        _list = info.list_user_policies_response.list_user_policies_result
        return _list.policy_names
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get user {0} policy.'
        log.error(msg.format(user_name))
        return False


def get_user_policy(user_name, policy_name, region=None, key=None, keyid=None, profile=None):
    '''
    Retrieves the specified policy document for the specified user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_user_policy myuser mypolicyname
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_user_policy(user_name, policy_name)
        log.debug('Info for user policy is : {0}.'.format(info))
        if not info:
            return False
        info = info.get_user_policy_response.get_user_policy_result.policy_document
        info = _unquote(info)
        info = json.loads(info, object_pairs_hook=odict.OrderedDict)
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get user {0} policy.'
        log.error(msg.format(user_name))
        return False


def put_user_policy(user_name, policy_name, policy_json, region=None, key=None, keyid=None, profile=None):
    '''
    Adds or updates the specified policy document for the specified user.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.put_user_policy myuser policyname policyrules
    '''
    user = get_user(user_name, region, key, keyid, profile)
    if not user:
        log.error('User {0} does not exist'.format(user_name))
        return False
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        if not isinstance(policy_json, string_types):
            policy_json = json.dumps(policy_json)
        created = conn.put_user_policy(user_name, policy_name,
                                       policy_json)
        if created:
            log.info('Created policy for user {0}.'.format(user_name))
            return True
        msg = 'Could not create policy for user {0}.'
        log.error(msg.format(user_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create policy for user {0}.'
        log.error(msg.format(user_name))
    return False


def delete_user_policy(user_name, policy_name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a user policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_user_policy myuser mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return False
    _policy = get_user_policy(
        user_name, policy_name, region, key, keyid, profile
    )
    if not _policy:
        return True
    try:
        conn.delete_user_policy(user_name, policy_name)
        msg = 'Successfully deleted {0} policy for user {1}.'
        log.info(msg.format(policy_name, user_name))
        return True
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete {0} policy for user {1}.'
        log.error(msg.format(policy_name, user_name))
        return False


def upload_server_cert(cert_name, cert_body, private_key, cert_chain=None, path=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Upload a certificate to Amazon.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.upload_server_cert mycert_name crt priv_key

    :param cert_name: The name for the server certificate. Do not include the path in this value.
    :param cert_body: The contents of the public key certificate in PEM-encoded format.
    :param private_key: The contents of the private key in PEM-encoded format.
    :param cert_chain:  The contents of the certificate chain. This is typically a concatenation of the PEM-encoded public key certificates of the chain.
    :param path: The path for the server certificate.
    :param region: The name of the region to connect to.
    :param key: The key to be used in order to connect
    :param keyid: The keyid to be used in order to connect
    :param profile: The profile that contains a dict of region, key, keyid
    :return: True / False
    '''

    exists = get_server_certificate(cert_name, region, key, keyid, profile)
    if exists:
        return True
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.upload_server_cert(cert_name, cert_body, private_key, cert_chain)
        log.info('Created certificate {0}.'.format(cert_name))
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to failed to create certificate {0}.'
        log.error(msg.format(cert_name))
        return False


def get_server_certificate(cert_name, region=None, key=None, keyid=None, profile=None):
    '''
    Returns certificate information from Amazon

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_server_certificate mycert_name
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_server_certificate(cert_name)
        if not info:
            return False
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get certificate {0} information.'
        log.error(msg.format(cert_name))
        return False


def delete_server_cert(cert_name, region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a certificate from Amazon.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_server_cert mycert_name
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        return conn.delete_server_cert(cert_name)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to delete certificate {0}.'
        log.error(msg.format(cert_name))
        return False


def _safe_dump(data):
    ###########################################
    # this presenter magic makes yaml.safe_dump
    # work with the objects returned from
    # boto.export_users()
    ###########################################
    def ordered_dict_presenter(dumper, data):
        return dumper.represent_dict(data.items())

    yaml.add_representer(odict.OrderedDict, ordered_dict_presenter,
                         Dumper=yaml.dumper.SafeDumper)

    return yaml.safe_dump(data, default_flow_style=False, indent=2)


def export_users(path_prefix='/', region=None, key=None, keyid=None,
                 profile=None):
    '''
    Get all IAM user details. Produces results that can be used to create an
    sls file.

    .. versionadded:: 2016.3.0

    CLI Example:

        salt-call boto_iam.export_users --out=txt | sed "s/local: //" > iam_users.sls
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if not conn:
        return None
    results = odict.OrderedDict()
    _users = conn.get_all_users(path_prefix=path_prefix)
    users = _users.list_users_response.list_users_result.users
    marker = getattr(
        _users.list_users_response.list_users_result, 'marker', None
    )
    while marker:
        _users = conn.get_all_users(path_prefix=path_prefix, marker=marker)
        users = users + _users.list_users_response.list_users_result.users
        marker = getattr(
            _users.list_users_response.list_users_result, 'marker', None
        )
    for user in users:
        name = user.user_name
        _policies = conn.get_all_user_policies(name, max_items=100)
        _policies = _policies.list_user_policies_response.list_user_policies_result.policy_names
        policies = {}
        for policy_name in _policies:
            _policy = conn.get_user_policy(name, policy_name)
            _policy = json.loads(_unquote(
                    _policy.get_user_policy_response.get_user_policy_result.policy_document
            ))
            policies[policy_name] = _policy
        user_sls = []
        user_sls.append({"name": name})
        user_sls.append({"policies": policies})
        user_sls.append({"path": user.path})
        results["manage user " + name] = {"boto_iam.user_present": user_sls}
    return _safe_dump(results)


def _get_policy_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = get_account_id(
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:iam::{0}:policy/{1}'.format(account_id, name)


def policy_exists(policy_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if policy exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.get_policy(_get_policy_arn(policy_name,
                    region=region, key=key, keyid=keyid, profile=profile))
        return True
    except boto.exception.BotoServerError:
        return False


def get_policy(policy_name,
               region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if policy exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        ret = conn.get_policy(_get_policy_arn(policy_name,
                            region=region, key=key, keyid=keyid, profile=profile))
        return ret.get('get_policy_response', {}).get('get_policy_result', {})
    except boto.exception.BotoServerError:
        return None


def create_policy(policy_name, policy_document, path=None, description=None,
                 region=None, key=None, keyid=None, profile=None):
    '''
    Create a policy.

    CLI Example:

    .. code-block:: bash

        salt myminios boto_iam.create_policy mypolicy '{"Version": "2012-10-17", "Statement": [{ "Effect": "Allow", "Action": ["s3:Get*", "s3:List*"], "Resource": ["arn:aws:s3:::my-bucket/shared/*"]},]}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not isinstance(policy_document, string_types):
        policy_document = json.dumps(policy_document)
    params = {}
    for arg in 'path', 'description':
        if locals()[arg] is not None:
            params[arg] = locals()[arg]
    if policy_exists(policy_name, region, key, keyid, profile):
        return True
    try:
        conn.create_policy(policy_name, policy_document, **params)
        log.info('Created {0} policy.'.format(policy_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create {0} policy.'
        log.error(msg.format(policy_name))
        return False
    return True


def delete_policy(policy_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Delete a policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_policy mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    if not policy_exists(policy_arn, region, key, keyid, profile):
        return True
    try:
        conn.delete_policy(policy_arn)
        log.info('Deleted {0} policy.'.format(policy_name))
    except boto.exception.BotoServerError as e:
        aws = salt.utils.boto.get_error(e)
        log.debug(aws)
        msg = 'Failed to delete {0} policy: {1}.'
        log.error(msg.format(policy_name, aws.get('message')))
        return False
    return True


def list_policies(region=None, key=None, keyid=None, profile=None):
    '''
    List policies.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_policies
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        policies = []
        for ret in salt.utils.boto.paged_call(conn.list_policies):
            policies.append(ret.get('list_policies_response', {}).get('list_policies_result', {}).get('policies'))
        return policies
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list policy versions.'
        log.error(msg)
        return []


def policy_version_exists(policy_name, version_id,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if policy exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.get_policy_version(policy_arn, version_id)
        return True
    except boto.exception.BotoServerError:
        return False


def get_policy_version(policy_name, version_id,
               region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if policy exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        ret = conn.get_policy_version(_get_policy_arn(policy_name,
                            region=region, key=key, keyid=keyid, profile=profile), version_id)
        retval = ret.get('get_policy_version_response', {}).get('get_policy_version_result', {}).get('policy_version', {})
        retval['document'] = _unquote(retval.get('document'))
        return {'policy_version': retval}
    except boto.exception.BotoServerError:
        return None


def create_policy_version(policy_name, policy_document, set_as_default=None,
                 region=None, key=None, keyid=None, profile=None):
    '''
    Create a policy version.

    CLI Example:

    .. code-block:: bash

        salt myminios boto_iam.create_policy_version mypolicy '{"Version": "2012-10-17", "Statement": [{ "Effect": "Allow", "Action": ["s3:Get*", "s3:List*"], "Resource": ["arn:aws:s3:::my-bucket/shared/*"]},]}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if not isinstance(policy_document, string_types):
        policy_document = json.dumps(policy_document)
    params = {}
    for arg in ('set_as_default',):
        if locals()[arg] is not None:
            params[arg] = locals()[arg]
    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        ret = conn.create_policy_version(policy_arn, policy_document, **params)
        vid = ret.get('create_policy_version_response', {}).get('create_policy_version_result', {}).get('policy_version', {}).get('version_id')
        log.info('Created {0} policy version {1}.'.format(policy_name, vid))
        return {'created': True, 'version_id': vid}
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to create {0} policy version.'
        log.error(msg.format(policy_name))
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete_policy_version(policy_name, version_id,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Delete a policy version.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.delete_policy_version mypolicy v1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    if not policy_version_exists(policy_arn, version_id, region, key, keyid, profile):
        return True
    try:
        conn.delete_policy_version(policy_arn, version_id)
        log.info('Deleted {0} policy version {1}.'.format(policy_name, version_id))
    except boto.exception.BotoServerError as e:
        aws = salt.utils.boto.get_error(e)
        log.debug(aws)
        msg = 'Failed to delete {0} policy version {1}: {2}'
        log.error(msg.format(policy_name, version_id, aws.get('message')))
        return False
    return True


def list_policy_versions(policy_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    List versions of a policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_policy_versions mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        ret = conn.list_policy_versions(policy_arn)
        return ret.get('list_policy_versions_response', {}).get('list_policy_versions_result', {}).get('versions')
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list {0} policy vesions.'
        log.error(msg.format(policy_name))
        return []


def set_default_policy_version(policy_name, version_id,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Set the default version of  a policy.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.set_default_policy_version mypolicy v1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.set_default_policy_version(policy_arn, version_id)
        log.info('Set {0} policy to version {1}.'.format(policy_name, version_id))
    except boto.exception.BotoServerError as e:
        aws = salt.utils.boto.get_error(e)
        log.debug(aws)
        msg = 'Failed to set {0} policy to version {1}: {2}'
        log.error(msg.format(policy_name, version_id, aws.get('message')))
        return False
    return True


def attach_user_policy(policy_name, user_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Attach a managed policy to a user.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.attach_user_policy mypolicy myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.attach_user_policy(policy_arn, user_name)
        log.info('Attached {0} policy to user {1}.'.format(policy_name, user_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to attach {0} policy to user {1}.'
        log.error(msg.format(policy_name, user_name))
        return False
    return True


def detach_user_policy(policy_name, user_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Detach a managed policy to a user.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.detach_user_policy mypolicy myuser
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.detach_user_policy(policy_arn, user_name)
        log.info('Detached {0} policy to user {1}.'.format(policy_name, user_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to detach {0} policy to user {1}.'
        log.error(msg.format(policy_name, user_name))
        return False
    return True


def attach_group_policy(policy_name, group_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Attach a managed policy to a group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.attach_group_policy mypolicy mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.attach_group_policy(policy_arn, group_name)
        log.info('Attached {0} policy to group {1}.'.format(policy_name, group_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to attach {0} policy to group {1}.'
        log.error(msg.format(policy_name, group_name))
        return False
    return True


def detach_group_policy(policy_name, group_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Detach a managed policy to a group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.detach_group_policy mypolicy mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.detach_group_policy(policy_arn, group_name)
        log.info('Detached {0} policy to group {1}.'.format(policy_name, group_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to detach {0} policy to group {1}.'
        log.error(msg.format(policy_name, group_name))
        return False
    return True


def attach_role_policy(policy_name, role_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Attach a managed policy to a role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.attach_role_policy mypolicy myrole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.attach_role_policy(policy_arn, role_name)
        log.info('Attached {0} policy to role {1}.'.format(policy_name, role_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to attach {0} policy to role {1}.'
        log.error(msg.format(policy_name, role_name))
        return False
    return True


def detach_role_policy(policy_name, role_name,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Detach a managed policy to a role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.detach_role_policy mypolicy myrole
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        conn.detach_role_policy(policy_arn, role_name)
        log.info('Detached {0} policy to role {1}.'.format(policy_name, role_name))
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to detach {0} policy to role {1}.'
        log.error(msg.format(policy_name, role_name))
        return False
    return True


def list_entities_for_policy(policy_name, path_prefix=None, entity_filter=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    List entities that a policy is attached to.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_entities_for_policy mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    params = {}
    for arg in ('path_prefix', 'entity_filter'):
        if locals()[arg] is not None:
            params[arg] = locals()[arg]

    policy_arn = _get_policy_arn(policy_name, region, key, keyid, profile)
    try:
        allret = {
          'policy_groups': [],
          'policy_users': [],
          'policy_roles': [],
        }
        for ret in salt.utils.boto.paged_call(conn.list_entities_for_policy, policy_arn=policy_arn, **params):
            for k, v in allret.iteritems():
                v.extend(ret.get('list_entities_for_policy_response', {}).get('list_entities_for_policy_result', {}).get(k))
        return allret
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list {0} policy entities.'
        log.error(msg.format(policy_name))
        return {}


def list_attached_user_policies(user_name, path_prefix=None, entity_filter=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    List entities attached to the given user.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_entities_for_policy mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    params = {'UserName': user_name}
    if path_prefix is not None:
        params['PathPrefix'] = path_prefix

    policies = []
    try:
        # Using conn.get_response is a bit of a hack, but it avoids having to
        # rewrite this whole module based on boto3
        for ret in salt.utils.boto.paged_call(conn.get_response, 'ListAttachedUserPolicies', params, list_marker='AttachedPolicies'):
            policies.extend(ret.get('list_attached_user_policies_response', {}).get('list_attached_user_policies_result', {}
                                   ).get('attached_policies', []))
        return policies
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list user {0} attached policies.'
        log.error(msg.format(user_name))
        return []


def list_attached_group_policies(group_name, path_prefix=None, entity_filter=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    List entities attached to the given group.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_entities_for_policy mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    params = {'GroupName': group_name}
    if path_prefix is not None:
        params['PathPrefix'] = path_prefix

    policies = []
    try:
        # Using conn.get_response is a bit of a hack, but it avoids having to
        # rewrite this whole module based on boto3
        for ret in salt.utils.boto.paged_call(conn.get_response, 'ListAttachedGroupPolicies', params, list_marker='AttachedPolicies'):
            policies.extend(ret.get('list_attached_group_policies_response', {}).get('list_attached_group_policies_result', {}
                                   ).get('attached_policies', []))
        return policies
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list group {0} attached policies.'
        log.error(msg.format(group_name))
        return []


def list_attached_role_policies(role_name, path_prefix=None, entity_filter=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    List entities attached to the given role.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.list_entities_for_policy mypolicy
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    params = {'RoleName': role_name}
    if path_prefix is not None:
        params['PathPrefix'] = path_prefix

    policies = []
    try:
        # Using conn.get_response is a bit of a hack, but it avoids having to
        # rewrite this whole module based on boto3
        for ret in salt.utils.boto.paged_call(conn.get_response, 'ListAttachedRolePolicies', params, list_marker='AttachedPolicies'):
            policies.extend(ret.get('list_attached_role_policies_response', {}).get('list_attached_role_policies_result', {}
                                   ).get('attached_policies', []))
        return policies
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to list role {0} attached policies.'
        log.error(msg.format(role_name))
        return []
