# -*- coding: utf-8 -*-
'''
Connection module for Amazon CloudTrail

.. versionadded:: Boron

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        cloudtrail.keyid: GKTADJGHEIQSXMKKRBJ08H
        cloudtrail.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        cloudtrail.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto3

'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import json
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils
from salt.ext.six import string_types

log = logging.getLogger(__name__)

# Import third party libs

# pylint: disable=import-error
try:
    #pylint: disable=unused-import
    import boto
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
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
    required_boto3_version = '1.2.1'
    # the boto_lambda execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return False
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto3.assign_funcs'](__name__, 'cloudtrail')


def exists(Name, 
           region=None, key=None, keyid=None, profile=None):
    '''
    Given a trail name, check to see if the given trail exists.

    Returns True if the given trail exists and returns False if the given
    trail does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.exists mytrail

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.get_trail_status(Name=Name)
        return {'exists': True}
    except ClientError as e:
        err = salt.utils.boto3.get_error(e)
        if e.response.get('Error', {}).get('Code') == 'TrailNotFoundException':
            return {'exists': False}
        return {'error': err}


def create(Name,
           S3BucketName, S3KeyPrefix=None,
           SnsTopicName=None,
           IncludeGlobalServiceEvents=None,
           #IsMultiRegionTrail=None,
           EnableLogFileValidation=None,
           CloudWatchLogsLogGroupArn=None,
           CloudWatchLogsRoleArn=None,
           KmsKeyId=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid config, create a trail.

    Returns {created: true} if the trail was created and returns
    {created: False} if the trail was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.create my_trail my_bucket

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        kwargs={}
        for arg in ('S3KeyPrefix', 'SnsTopicName', 'IncludeGlobalServiceEvents',
                    #'IsMultiRegionTrail',
                    'EnableLogFileValidation', 'CloudWatchLogsLogGroupArn',
                    'CloudWatchLogsRoleArn', 'KmsKeyId'):
            if locals()[arg] is not None:
               kwargs[arg] = locals()[arg]
        trail = conn.create_trail(Name=Name,
                                  S3BucketName=S3BucketName,
                                  **kwargs)
        if trail:
            log.info('The newly created trail name is {0}'.format(trail['Name']))

            return {'created': True, 'name': trail['Name']}
        else:
            log.warning('Trail was not created')
            return {'created': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def delete(Name,
            region=None, key=None, keyid=None, profile=None):
    '''
    Given a trail name, delete it.

    Returns {deleted: true} if the trail was deleted and returns
    {deleted: false} if the trail was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.delete mytrail

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_trail(Name=Name)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}


def describe(Name,
             region=None, key=None, keyid=None, profile=None):
    '''
    Given a trail name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.describe mytrail

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        trails = conn.describe_trails(trailNameList=[Name])
        if trails and len(trails.get('trailList',[])) > 0:
            keys = ('Name', 'S3BucketName', 'S3KeyPrefix',
                    'SnsTopicName', 'IncludeGlobalServiceEvents',
                    #'IsMultiRegionTrail',
                    'HomeRegion', 'TrailARN',
                    'LogFileValidationEnabled', 'CloudWatchLogsLogGroupArn',
                    'CloudWatchLogsRoleArn', 'KmsKeyId')
            trail = trails['trailList'].pop()
            return {'trail': dict([(k, trail.get(k)) for k in keys])}
        else:
            return {'trail': None}
    except ClientError as e:
        err = salt.utils.boto3.get_error(e)
        if e.response.get('Error', {}).get('Code') == 'TrailNotFoundException':
            return {'trail': None}
        return {'error': salt.utils.boto3.get_error(e)}


def status(Name,
             region=None, key=None, keyid=None, profile=None):
    '''
    Given a trail name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_cloudtrail.describe mytrail

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        trail = conn.get_trail_status(Name=Name)
        if trail:
            keys = ('IsLogging', 'LatestDeliveryError', 'LatestNotificationError',
                    'LatestDeliveryTime', 'LatestNotificationTime',
                    'StartLoggingTime', 'StopLoggingTime',
                    'LatestCloudWatchLogsDeliveryError',
                    'LatestCloudWatchLogsDeliveryTime',
                    'LatestDigestDeliveryTime', 'LatestDigestDeliveryError',
                    'LatestDeliveryAttemptTime',
                    'LatestNotificationAttemptTime',
                    'LatestNotificationAttemptSucceeded',
                    'LatestDeliveryAttemptSucceeded',
                    'TimeLoggingStarted',
                    'TimeLoggingStopped')
            return {'trail': dict([(k, trail.get(k)) for k in keys])}
        else:
            return {'trail': None}
    except ClientError as e:
        err = salt.utils.boto3.get_error(e)
        if e.response.get('Error', {}).get('Code') == 'TrailNotFoundException':
            return {'trail': None}
        return {'error': salt.utils.boto3.get_error(e)}


def list(region=None, key=None, keyid=None, profile=None):
    '''
    List all trails

    Returns list of trails

    CLI Example:

    .. code-block:: yaml

        policies:
          - {...}
          - {...}

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        trails = conn.describe_trails()
        if not bool(trails.get('trailList')):
            log.warning('No trails found')
        return {'trails': trails.get('trailList',[])}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}
