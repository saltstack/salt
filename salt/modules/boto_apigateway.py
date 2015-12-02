# -*- coding: utf-8 -*-
'''
Connection module for Amazon APIGateway 

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

        apigateway.keyid: GKTADJGHEIQSXMKKRBJ08H
        apigateway.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        apigateway.region: us-west-2

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-west-2

.. versionchanged:: 2015.8.0
    All methods now return a dictionary. Create and delete methods return:

    .. code-block:: yaml

        created: true

    or

    .. code-block:: yaml

        created: false
        error:
          message: error message

    Request methods (e.g., `describe_apigateway`) return:

    .. code-block:: yaml

        apigateway:
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
    # the boto_apigateway execution module relies on the connect_to_region() method
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
        __utils__['boto3.assign_funcs'](__name__, 'apigateway')


def _filter_api(name, apis):
    '''
    Given a name, and a list of api items, return list of api items matching 
    the given name.
    '''

    res = []
    for api in apis:
        if api['name'] == name:
            res.append(api)
    return res

def _find_apis(name,
               region=None, key=None, keyid=None, profile=None):

    '''
    Given rest api name, find and return list of matching rest api information.
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    apis = []
    _apis = conn.get_rest_apis()

    while True:
        if (_apis):
            apis = apis + _filter_api(name, _apis['items'])
            if not _apis.has_key('position'):
                break
            _apis = conn.get_rest_apis(position=_apis['position'])
    return apis


def exists(name, region=None, key=None,
           keyid=None, profile=None):
    '''
    Given a Rest API Name, check to see if the given Rest API Name 
    exists.

    Returns True if the given Rest API Name exists and returns False if 
    the given Rest API Name does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.exists myapi_name

    '''

    try:
        apis = _find_apis(name,
                          region=region, key=key, keyid=keyid, profile=profile)
        return {'exists': bool(apis)}
    except ClientError as e:
        # TODO: error with utils.boto3.get_error on exception
        return {'exists': False, 'error': salt.utils.boto.get_error(e)}


def _get_role_arn(name, region=None, key=None, keyid=None, profile=None):
    if name.startswith('arn:aws:iam:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:iam::{0}:role/{1}'.format(account_id, name)


def create_api(name, description, cloneFrom=None,
               region=None, key=None, keyid=None, profile=None):
    '''
    Create a new REST API Service with the given name

    Returns False if there is already an API with the same name, as
    AWS allows you to create multiple APIs w/ the same name and 
    description.  Returns True if the REST API is created.


    CLI Example:
    
    .. code-block:: bash

        salt myminion boto_apigateway.create_api myapi_name api_description

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if (cloneFrom):
            api = conn.create_rest_api(name=name, description=description, cloneFrom=cloneFrom)
        else:
            api = conn.create_rest_api(name=name, description=description)

        if api:
            log.info('The newly created rest api name is {0}'.format(api['name']))
            return {'created': True, 'api': api}
        else:
            log.warn('rest api {0} was not created'.format(name))
            return {'created': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete_api(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete all REST API Service with the given name

    CLI Example:

    .. code-block:: bash

        salt myminion boto_apigateway.delete_api myapi_name

    '''
    try:
        apis = _find_apis(name,
                          region=region, key=key, keyid=keyid, profile=profile)

        if (len(apis)):
            conn = _get_conn(region=region, key=key, 
                             keyid=keyid, profile=profile)
            for api in apis:
                conn.delete_rest_api(restApiId=api['id'])

            return {'deleted': True, 'count': len(apis)}  
        else:
            log.warn('rest api name {0} was not found'.format(name))
            return {'deleted': False}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}
