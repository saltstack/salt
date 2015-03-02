# -*- coding: utf-8 -*-
'''
Connection module for Amazon IAM

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit iam credentials but can also utilize
    IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        iam.keyid: GKTADJGHEIQSXMKKRBJ08H
        iam.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        iam.region: us-east-1

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json

log = logging.getLogger(__name__)

# Import third party libs
# pylint: disable=import-error
from salt.ext.six import string_types
from salt.ext.six.moves.urllib.parse import unquote as _unquote  # pylint: disable=no-name-in-module
try:
    import boto
    import boto.iam
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error

# Import salt libs
import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def instance_profile_exists(name, region=None, key=None, keyid=None,
                            profile=None):
    '''
    Check to see if an instance profile exists.

    CLI example::

        salt myminion boto_iam.instance_profile_exists myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
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

    CLI example::

        salt myminion boto_iam.create_instance_profile myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_iam.instance_profile_exists'](name, region, key, keyid,
                                                    profile):
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

    CLI example::

        salt myminion boto_iam.delete_instance_profile myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_iam.instance_profile_exists'](name, region, key,
                                                        keyid, profile):
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

    CLI example::

        salt myminion boto_iam.role_exists myirole
    '''
    conn = _get_conn(region, key, keyid, profile)
    try:
        conn.get_role(name)
        return True
    except boto.exception.BotoServerError:
        return False


def create_role(name, policy_document=None, path=None, region=None, key=None,
                keyid=None, profile=None):
    '''
    Create an instance role.

    CLI example::

        salt myminion boto_iam.create_role myrole
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if __salt__['boto_iam.role_exists'](name, region, key, keyid, profile):
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

    CLI example::

        salt myminion boto_iam.delete_role myirole
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_iam.role_exists'](name, region, key, keyid, profile):
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

    CLI example::

        salt myminion boto_iam.profile_associated myirole myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
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

    CLI example::

        salt myminion boto_iam.associate_profile_to_role myirole myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_iam.role_exists'](role_name, region, key, keyid,
                                            profile):
        log.error('IAM role {0} does not exist.'.format(role_name))
        return False
    if not __salt__['boto_iam.instance_profile_exists'](profile_name, region,
                                                        key, keyid, profile):
        log.error('Instance profile {0} does not exist.'.format(profile_name))
        return False
    associated = __salt__['boto_iam.profile_associated'](role_name,
                                                         profile_name, region,
                                                         key, keyid, profile)
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

    CLI example::

        salt myminion boto_iam.disassociate_profile_from_role myirole myiprofile
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    if not __salt__['boto_iam.role_exists'](role_name, region, key, keyid,
                                            profile):
        log.error('IAM role {0} does not exist.'.format(role_name))
        return False
    if not __salt__['boto_iam.instance_profile_exists'](profile_name, region,
                                                        key, keyid, profile):
        log.error('Instance profile {0} does not exist.'.format(profile_name))
        return False
    associated = __salt__['boto_iam.profile_associated'](role_name,
                                                         profile_name, region,
                                                         key, keyid, profile)
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

    CLI example::

        salt myminion boto_iam.list_role_policies myirole
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
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

    CLI example::

        salt myminion boto_iam.get_role_policy myirole mypolicy
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
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

    CLI example::

        salt myminion boto_iam.create_role_policy myirole mypolicy '{"MyPolicy": "Statement": [{"Action": ["sqs:*"], "Effect": "Allow", "Resource": ["arn:aws:sqs:*:*:*"], "Sid": "MyPolicySqs1"}]}'
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    _policy = __salt__['boto_iam.get_role_policy'](role_name, policy_name,
                                                   region, key, keyid, profile)
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

    CLI example::

        salt myminion boto_iam.delete_role_policy myirole mypolicy
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    _policy = __salt__['boto_iam.get_role_policy'](role_name, policy_name,
                                                   region, key, keyid, profile)
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


def get_account_id(region=None, key=None, keyid=None, profile=None):
    '''
    Get a the AWS account id associated with the used credentials.

    CLI example::

        salt myminion boto_iam.get_account_id
    '''
    cache_key = 'boto_iam.account_id'
    if cache_key not in __context__:
        conn = _get_conn(region, key, keyid, profile)
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


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to IAM.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('iam.region'):
        region = __salt__['config.option']('iam.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('iam.key'):
        key = __salt__['config.option']('iam.key')
    if not keyid and __salt__['config.option']('iam.keyid'):
        keyid = __salt__['config.option']('iam.keyid')

    try:
        conn = boto.iam.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto iam connection.')
        return None
    return conn
