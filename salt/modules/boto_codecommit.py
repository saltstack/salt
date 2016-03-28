# -*- coding: utf-8 -*-
'''
Connection module for Amazon CodeCommit 

.. versionadded:: 2016.3.0

:configuration: This module accepts explicit Lambda credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        iot.keyid: GKTADJGHEIQSXMKKRBJ08H
        iot.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        iot.region: us-east-1

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
        __utils__['boto3.assign_funcs'](__name__, 'codecommit')


def repository_exists(repositoryName,
           region=None, key=None, keyid=None, profile=None):
    '''
    Given a repository name, check to see if the given repository exists.

    Returns True if the given repository exists and returns False if the given
    repository does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_codecommit.repository_exists myrepository

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.get_repository(repositoryName=repositoryName)
        return {'exists': True}
    except ClientError as e:
        err = salt.utils.boto3.get_error(e)
        if e.response.get('Error', {}).get('Code') == 'RepositoryDoesNotExistException':
            return {'exists': False}
        return {'error': err}


def create_repository(repositoryName, repositoryDescription="",
            region=None, key=None, keyid=None, profile=None):
    '''
    Creates a new repository.

    Returns {created: true} if the repository was created and returns
    {created: False} if the repository was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_codecommit.create_repository myrepository repositoryDescription="Test repository"

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        repository = conn.create_repository(repositoryName=repositoryName,
                                    repositoryDescription=repositoryDescription)
        if repository and repository.get('repositoryMetadata'):
            log.info('The newly created repository {0}'.format(repository['repositoryMetadata'].get('Arn')))

            return {'created': True, 'repository': repository}
        else:
            log.warning('Repository was not created')
            return {'created': False}
    except ClientError as e:
        return {'created': False, 'error': salt.utils.boto3.get_error(e)}


def delete_repository(repositoryName,
            region=None, key=None, keyid=None, profile=None):
    '''
    Given a repository name, delete it.

    Returns {deleted: true} if the repository was deleted and returns
    {deleted: false} if the repository was not deleted.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_codecommit.delete_repository myrepository

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.delete_repository(repositoryName=repositoryName)
        return {'deleted': True}
    except ClientError as e:
        return {'deleted': False, 'error': salt.utils.boto3.get_error(e)}


def _filter_repositories(name, repositories):
    '''
    Return list of repositories matching the given name.
    '''
    return [r for r in repositories if r['repositoryName'] == name]


def _multi_call(function, contentkey):
    '''
    Retrieve full list of values for the contentkey from a boto3 CodeCOmmit 
    client function that may be paged via 'nextToken'
    '''
    ret = function()
    token = ret.get('nextToken')

    while token:
        more = function(nextToken=token)
        ret[contentkey].extend(more[contentkey])
        token = more.get('nextToken')
    return ret.get(contentkey)

def _find_repositories(name, 
                       region=None, key=None, keyid=None, profile=None):

    '''
    get and return list of matching repositories by the given name.
    If name evaluates to False, return all repositories w/o filtering the name.
    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        repositories = _multi_call(conn.list_repositories, 'repositories')
        if name:
            repositories = _filter_repositories(name, repositories)
        return {'repositories': repositories}
    except ClientError as e:
        return {'error': salt.utils.boto3.get_error(e)}

def describe_repositories(repositoryName=None,
             region=None, key=None, keyid=None, profile=None):
    '''
    Given a repository name describe its properties.

    Returns a dictionary of interesting properties.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_codecommit.describe_repository myrepository

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        return _find_repositories(repositoryName, region=region, key=key, keyid=keyid, profile=profile)
    except ClientError as e:
        err = salt.utils.boto3.get_error(e)
        if e.response.get('Error', {}).get('Code') == 'ResourceNotFoundException':
            return {'repositories': None}
        return {'error': salt.utils.boto3.get_error(e)}

