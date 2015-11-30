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


def _zipdata(zipfile):
    with open(zipfile, 'rb') as f:
       return f.read()

def create(name, runtime, role, handler, zipfile=None, s3bucket=None, s3key=None, s3objectversion=None,
            description="", timeout=3, memorysize=128, publish=False,
            region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid config, create a Lambda function.

    Returns {created: true} if the Lambda function was created and returns
    {created: False} if the Lambda function was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lamba.create my_lambda python2.7 my_role my_file.my_function my_lambda.zip

    '''

    role_arn = _get_role_arn(role, region, key, keyid, profile)
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if zipfile:
            if s3bucket or s3key or s3objectversion:
                raise SaltInvocationError('Either zipfile must be specified, or '
                                's3bucket and s3key must be provided.')
            code = {
               'ZipFile': _zipdata(zipfile),
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


def describe(name, region=None, key=None,
             keyid=None, profile=None):
    '''
    Given a Lambda function name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lambda.describe myfunction

    '''

    try:
        lmbda = _find_lambda(name,
                             region=region, key=key, keyid=keyid, profile=profile)
        if lmbda:
            keys = ('FunctionName', 'Runtime', 'Role', 'Handler', 'CodeSha256',
                'CodeSize', 'Description', 'Timeout', 'MemorySize', 'FunctionArn',
                'LastModified')
            return {'lambda': dict([(k, lmbda.get(k)) for k in keys])}
        else:
            return {'lambda': None}
    except ClientError as e:
        return {'error': salt.utils.boto.get_error(e)}


def update_config(name, role, handler, description="", timeout=3, memorysize=128,
            region=None, key=None, keyid=None, profile=None):
    '''
    Update the named lambda function to the configuration.

    Returns {updated: true} if the Lambda function was updated and returns
    {updated: False} if the Lambda function was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lamba.update_config my_lambda my_role my_file.my_function "my lambda function"

    '''

    role_arn = _get_role_arn(role, region, key, keyid, profile)
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        r = conn.update_function_configuration(FunctionName=name, Role=role_arn, Handler=handler, 
                                   Description=description, Timeout=timeout,
                                   MemorySize=memorysize)
        if r:
            keys = ('FunctionName', 'Runtime', 'Role', 'Handler', 'CodeSha256',
                'CodeSize', 'Description', 'Timeout', 'MemorySize', 'FunctionArn',
                'LastModified')
            return {'updated': True, 'lambda': dict([(k, r.get(k)) for k in keys])}
        else:
            log.warning('Lambda function was not updated')
            return {'updated': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def update_code(name, zipfile=None, s3bucket=None, s3key=None,
            s3objectversion=None, publish=False,
            region=None, key=None, keyid=None, profile=None):
    '''
    Upload the given code to the named lambda function.

    Returns {updated: true} if the Lambda function was updated and returns
    {updated: False} if the Lambda function was not updated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lamba.update_code my_lambda zipfile=lambda.zip

    '''

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        if zipfile:
            if s3bucket or s3key or s3objectversion:
                raise SaltInvocationError('Either zipfile must be specified, or '
                                's3bucket and s3key must be provided.')
            r = conn.update_function_code(FunctionName=name,
                                   ZipFile=_zipdata(zipfile),
                                   Publish=publish)
        else:
            args = {
                'S3Bucket': s3bucket, 
                'S3Key': s3key,
            }
            if s3objectversion:
              args['S3ObjectVersion'] = s3objectversion
            r = conn.update_function_code(FunctionName=name,
                                   Publish=publish, **args)
        if r:
            keys = ('FunctionName', 'Runtime', 'Role', 'Handler', 'CodeSha256',
                'CodeSize', 'Description', 'Timeout', 'MemorySize', 'FunctionArn',
                'LastModified')
            return {'updated': True, 'lambda': dict([(k, r.get(k)) for k in keys])}
        else:
            log.warning('Lambda function was not updated')
            return {'updated': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


