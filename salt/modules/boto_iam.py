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

# Import salt libs
import salt.utils.odict as odict

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
        return False
    __utils__['boto.assign_funcs'](__name__, 'iam', pack=__salt__)
    return True


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
    if get_group(group_name, region=region, key=key, keyid=keyid, profile=profile):
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


def get_group(group_name, marker=None, max_items=None, region=None, key=None,
              keyid=None, profile=None):
    '''
    Get group information.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_iam.get_group mygroup
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        info = conn.get_group(group_name, marker, max_items)
        if not info:
            return False
        return info
    except boto.exception.BotoServerError as e:
        log.debug(e)
        msg = 'Failed to get group {0} info.'
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
    if user_exists_in_group(user_name, group_name, region=region, key=key, keyid=keyid,
                            profile=profile):
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
    group = get_group(group_name, region=region, key=key, keyid=keyid,
                      profile=profile)
    if group:
        for _users in group['get_group_response']['get_group_result']['users']:
            if user_name == _users['user_name']:
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
    group = get_group(group_name, region=region, key=key, keyid=keyid, profile=profile)
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
