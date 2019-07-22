# -*- coding: utf-8 -*-
'''
Connection module for Amazon STS

'''
# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import hashlib

# Import Salt libs
import salt.utils.compat
from salt.ext import six
from salt.utils.versions import LooseVersion as _LooseVersion


# Support 2017 to 2018+ transition of salt release
try:
    # 2018+ Salt Release
    from salt.utils.stringutils import to_bytes as salt_utils_stringutils_to_bytes
except ImportError:
    from salt.utils import to_bytes as salt_utils_stringutils_to_bytes
log = logging.getLogger(__name__)

# Import third party libs

# pylint: disable=import-error
try:
    # pylint: disable=unused-import
    import boto
    import boto3
    # pylint: enable=unused-import
    from botocore import __version__ as found_botocore_version
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.8.0'
    required_boto3_version = '1.2.5'
    required_botocore_version = '1.5.2'
    if not HAS_BOTO:
        return (False, 'The boto_lambda module could not be loaded: '
                'boto libraries not found')
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return (False, 'The boto_lambda module could not be loaded: '
                'boto version {0} or later must be installed.'.format(required_boto_version))
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return (False, 'The boto_lambda module could not be loaded: '
                'boto version {0} or later must be installed.'.format(required_boto3_version))
    elif _LooseVersion(found_botocore_version) < _LooseVersion(required_botocore_version):
        return (False, 'The boto_apigateway module could not be loaded: '
                'botocore version {0} or later must be installed.'.format(required_botocore_version))
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto3.assign_funcs'](__name__, 'sts')


def get_account_id(region=None, key=None, keyid=None, profile=None):
    '''
    Get a the AWS account id associated with the used credentials.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_sts.get_account_id
    '''

    cxkey, _aregion, _akey, _akeyid = _hash_profile('sts', region, key,
                                                    keyid, profile)
    cxkey = cxkey + ':account_id'

    cache_key = cxkey
    if cache_key not in __context__:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        try:
            ret = conn.get_caller_identity()
            # The get_user call returns an user ARN:
            #    arn:aws:iam::027050522557:user/salt-test
            arn = ret['Arn']
            account_id = arn.split(':')[4]
        except boto.exception.BotoServerError as err:
            log.info("Falling back to the metadata server - this is probably wrong")
            log.debug(err)
            # If call failed, then let's try to get the ARN from the metadata
            timeout = boto.config.getfloat(
                'Boto', 'metadata_service_timeout', 1.0
            )
            attempts = boto.config.getint(
                'Boto', 'metadata_service_num_attempts', 1
            )
            identity = boto.utils.get_instance_identity(
                timeout=timeout, num_retries=attempts
            )
            try:
                account_id = identity['document']['accountId']
            except KeyError:
                log.error('Failed to get account id from instance_identity in'
                          ' boto_sts.get_caller_identity.')
        __context__[cache_key] = account_id
    return __context__[cache_key]


def get_partition(region=None, key=None, keyid=None, profile=None):
    '''
    Get a the AWS partition associated with the used credentials.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_sts.get_partition
    '''
    cxkey, _aregion, _akey, _akeyid = _hash_profile('sts', region, key,
                                                    keyid, profile)
    cxkey = cxkey + ':partition'

    cache_key = cxkey
    if cache_key not in __context__:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        try:
            ret = conn.get_caller_identity()
            # The get_user call returns an user ARN:
            #    arn:aws:iam::027050522557:user/salt-test
            arn = ret['Arn']
            partition = arn.split(':')[1]
        except boto.exception.BotoServerError as err:
            log.info("Falling back to the metadata server - this is probably wrong")
            log.debug(err)
            # If call failed, then let's try to get the ARN from the metadata
            timeout = boto.config.getfloat(
                'Boto', 'metadata_service_timeout', 1.0
            )
            attempts = boto.config.getint(
                'Boto', 'metadata_service_num_attempts', 1
            )
            identity = boto.utils.get_instance_metadata(
                timeout=timeout, num_retries=attempts
            )
            try:
                partition = identity['iam']['info']['InstanceProfileArn'].split(':')[1]
            except KeyError:
                log.error('Failed to get partition from metadata in'
                          ' boto_sts.partition.')
        __context__[cache_key] = partition
    return __context__[cache_key]


def _hash_profile(service, region=None, key=None, keyid=None, profile=None):
    '''
    Generate a bunch of hashed values for injecting stuff into the __context__ dunder

    '''
    if profile:
        key = profile.get('key', None)
        keyid = profile.get('keyid', None)
        region = profile.get('region', None)

    if not region:
        region = 'us-east-1'
        msg = 'Assuming default region {0}'.format(region)
        log.info(msg)

    label = 'boto_{0}:'.format(service)
    if keyid:
        hash_string = region + keyid + key
        if six.PY3:
            hash_string = salt_utils_stringutils_to_bytes(hash_string)
        cxkey = label + hashlib.md5(hash_string).hexdigest()
    else:
        cxkey = label + region

    return (cxkey, region, key, keyid)
