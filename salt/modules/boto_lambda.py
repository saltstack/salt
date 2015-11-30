# -*- coding: utf-8 -*-
'''
Connection module for Amazon Lambda

.. versionadded:: 

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        lambda.keyid: GKTADJGHEIQSXMKKRBJ08H
        lambda.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        lambda.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. versionchanged:: 2015.8.0
    All methods now return a dictionary. Create and delete methods return:

    .. code-block:: yaml

        created: true

    or

    .. code-block:: yaml

        created: false
        error:
          message: error message

    Request methods (e.g., `describe_lambda`) return:

    .. code-block:: yaml

        lambda:
          - {...}
          - {...}

    or

    .. code-block:: yaml

        error:
          message: error message

:depends: boto3

'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import
import logging
import socket
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt libs
import salt.utils.boto
import salt.utils.compat
from salt.exceptions import SaltInvocationError, CommandExecutionError
# from salt.utils import exactly_one
# TODO: Uncomment this and s/_exactly_one/exactly_one/
# See note in utils.boto

log = logging.getLogger(__name__)

# Import third party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    #pylint: disable=unused-import
    import boto
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
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
    required_boto3_version = '1.2.1'
    # the boto_lambda execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return False
    else:
        return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto3.assign_funcs'](__name__, 'lambda')


def _find_lambda(name,
               region=None, key=None, keyid=None, profile=None):

    '''
    Given Lambda function name, find and return matching Lambda information.
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    lambdas = conn.list_functions()

    for lmbda in lambdas['Functions']:
        if lmbda['FunctionName'] == name:
            return lmbda
    return None


def exists(name, region=None, key=None,
           keyid=None, profile=None):
    '''
    Given a Lambda function ID, check to see if the given Lambda function ID exists.

    Returns True if the given Lambda function ID exists and returns False if the given
    Lambda function ID does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lambda.exists mylambda

    '''

    try:
        lmbda = _find_lambda(name,
                             region=region, key=key, keyid=keyid, profile=profile)
        return {'exists': bool(lmbda)}
    except ClientError as e:
        return {'error': salt.utils.boto.get_error(e)}


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def create(name, runtime, role, handler, zipfile=None, s3bucket=None, s3key=None, s3objectversion=None,
            description="", timeout=3, memorysize=128, publish=False,
            region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid config, create a Lambda function.

    Returns {created: true} if the Lambda function was created and returns
    {created: False} if the Lambda function was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lamba.create my_lambda python2.7 my_file.my_function my_lambda.zip

    '''

    role_arn = _get_role_arn(role, region, key, keyid, profile)
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if zipfile:
            if s3bucket or s3key or s3objectversion:
                raise SaltInvocationError('Either zipfile must be specified, or '
                                's3bucket, and s3key must be provided.')
            with open(zipfile, 'rb') as f:
               zipdata = f.read()
            code = {
               'ZipFile': zipdata,
            }
        else:
            code = {
               'S3Bucket': s3bucket,
               'S3Key': s3key,
            }
            if s3objectversion:
                code['S3ObjectVersion']= s3objectversion
        lmbda = conn.create_function(FunctionName=name, Runtime=runtime, Role=role_arn, Handler=handler, 
                                   Code=code, Description=description, Timeout=timeout, MemorySize=memorysize, 
                                   Publish=publish)
        if lmbda:
            log.info('The newly created Lambda function name is {0}'.format(lmbda['FunctionName']))

            return {'created': True, 'name': lmbda['FunctionName']}
        else:
            log.warning('Lambda function was not created')
            return {'created': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete(name, version=None, region=None, key=None, keyid=None, profile=None):
    '''
    Given a Lambda function name and optional version, delete it.

    Returns {deleted: true} if the Lambda function was deleted and returns
    {deleted: false} if the Lambda function was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lambda.delete myfunction

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if version:
           conn.delete_function(FunctionName=name, Qualifier=version)
        else:
           conn.delete_function(FunctionName=name)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto.get_error(e)}


def describe(vpc_id=None, vpc_name=None, region=None, key=None,
             keyid=None, profile=None):
    '''
    Given a VPC ID describe its properties.

    Returns a dictionary of interesting properties.

    .. versionchanged:: 2015.8.0
        Added vpc_name argument

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.describe vpc_id=vpc-123456
        salt myminion boto_vpc.describe vpc_name=myvpc

    '''

    if not any((vpc_id, vpc_name)):
        raise SaltInvocationError('A valid vpc id or name needs to be specified.')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        vpc_id = _check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
        if not vpc_id:
            return {'vpc': None}

        filter_parameters = {'vpc_ids': vpc_id}

        vpcs = conn.get_all_vpcs(**filter_parameters)

        if vpcs:
            vpc = vpcs[0]  # Found!
            log.debug('Found VPC: {0}'.format(vpc.id))

            keys = ('id', 'cidr_block', 'is_default', 'state', 'tags',
                    'dhcp_options_id', 'instance_tenancy')
            return {'vpc': dict([(k, getattr(vpc, k)) for k in keys])}
        else:
            return {'vpc': None}

    except ClientError as e:
        return {'error': salt.utils.boto.get_error(e)}
