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
    from boto.exception import BotoServerError
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


def _find_lambda(lambda_id=None, lambda_name=None, 
               region=None, key=None, keyid=None, profile=None):

    '''
    Given Lambda function properties, find and return matching Lambda information.
    '''

    if all((lambda_id, lambda_name)):
        raise SaltInvocationError('Only one of lambda_name or lambda_id may be '
                                  'provided.')

    if not any((lambda_id, lambda_name)):
        raise SaltInvocationError('At least one of the following must be '
                                  'provided: lambda_id or lambda_name.')

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    lambdas = conn.list_functions()

    found=False

    if lambda_id:
	for lmbda in lambdas['Functions']:
            if lmbda['FunctionArn'] == lambda_id:
                found=True
                break

    if lambda_name:
	for lmbda in lambdas['Functions']:
            if lmbda['FunctionName'] == lambda_name:
                found=True
                break
    if found:
       return lmbda
    return None

def _get_id(lambda_name=None, region=None, key=None,
            keyid=None, profile=None):
    '''
    Given Lambda function name, return the Lambda function id if a match is found.
    '''

    lambda_id = _cache_id(lambda_name, region=region,
                       key=key, keyid=keyid,
                       profile=profile)
    if lambda_id:
        return lambda_id
    log.info('No Lambda function found.')
    return None

def get_id(name=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Given Lambda function name, return the Lambda id if a match is found.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_lambda.get_id mylambda

    '''

    try:
        return {'id': _get_id(lambda_name=name, region=region,
                              key=key, keyid=keyid, profile=profile)}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def exists(lambda_id=None, name=None, region=None, key=None,
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
        lmbda = _find_lambda(lambda_id=lambda_id, lambda_name=name,
                             region=region, key=key, keyid=keyid, profile=profile)
        return {'exists': bool(lmbda)}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def create(cidr_block, instance_tenancy=None, lambda_name=None,
           enable_dns_support=None, enable_dns_hostnames=None, tags=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid CIDR block, create a VPC.

    An optional instance_tenancy argument can be provided. If provided, the
    valid values are 'default' or 'dedicated'

    An optional vpc_name argument can be provided.

    Returns {created: true} if the VPC was created and returns
    {created: False} if the VPC was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create '10.0.0.0/24'

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        vpc = conn.create_vpc(cidr_block, instance_tenancy=instance_tenancy)
        if vpc:
            log.info('The newly created VPC id is {0}'.format(vpc.id))

            _maybe_set_name_tag(vpc_name, vpc)
            _maybe_set_tags(tags, vpc)
            _maybe_set_dns(conn, vpc.id, enable_dns_support, enable_dns_hostnames)
            if vpc_name:
                _cache_id(vpc_name, vpc.id,
                          region=region, key=key,
                          keyid=keyid, profile=profile)
            return {'created': True, 'id': vpc.id}
        else:
            log.warning('VPC was not created')
            return {'created': False}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete(vpc_id=None, name=None, vpc_name=None, tags=None,
           region=None, key=None, keyid=None, profile=None):
    '''
    Given a VPC ID or VPC name, delete the VPC.

    Returns {deleted: true} if the VPC was deleted and returns
    {deleted: false} if the VPC was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete vpc_id='vpc-6b1fe402'
        salt myminion boto_vpc.delete name='myvpc'

    '''

    if name:
        log.warning('boto_vpc.delete: name parameter is deprecated '
                    'use vpc_name instead.')
        vpc_name = name

    if not _exactly_one((vpc_name, vpc_id)):
        raise SaltInvocationError('One (but not both) of vpc_name or vpc_id must be '
                                  'provided.')
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if not vpc_id:
            vpc_id = _get_id(vpc_name=vpc_name, tags=tags, region=region, key=key,
                             keyid=keyid, profile=profile)
            if not vpc_id:
                return {'deleted': False, 'error': {'message':
                        'VPC {0} not found'.format(vpc_name)}}

        if conn.delete_vpc(vpc_id):
            log.info('VPC {0} was deleted.'.format(vpc_id))
            if vpc_name:
                _cache_id(vpc_name, resource_id=vpc_id,
                          invalidate=True,
                          region=region,
                          key=key, keyid=keyid,
                          profile=profile)
            return {'deleted': True}
        else:
            log.warning('VPC {0} was not deleted.'.format(vpc_id))
            return {'deleted': False}
    except BotoServerError as e:
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

    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}
