# -*- coding: utf-8 -*-
'''
Connection module for Amazon VPC

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit VPC credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
        vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        vpc.region: us-east-1

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

    Request methods (e.g., `describe_vpc`) return:

    .. code-block:: yaml

        vpcs:
          - {...}
          - {...}

    or

    .. code-block:: yaml

        error:
          message: error message

:depends: boto

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
import salt.utils.boto3
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
    import boto.vpc
    #pylint: enable=unused-import
    from boto.exception import BotoServerError
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=import-error
try:
    #pylint: disable=unused-import
    import boto3
    #pylint: enable=unused-import
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.8.0'
    # the boto_vpc execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return (False, 'The boto_vpc module could not be loaded: boto libraries not found')
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return (False, 'The boto_vpc module could not be loaded: boto library is not required version 2.8.0')
    required_boto3_version = '1.2.6'
    # the boto_vpc execution module relies on the create_nat_gateway() method
    # which was added in boto3 1.2.6
    if not HAS_BOTO3:
        return (False, 'The boto_vpc module could not be loaded: boto3 libraries not found')
    elif _LooseVersion(boto3.__version__) < _LooseVersion(required_boto3_version):
        return (False, 'The boto_vpc module could not be loaded: boto3 library is not required version 1.2.6')
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto.assign_funcs'](__name__, 'vpc', pack=__salt__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'ec2',
                  get_conn_funcname='_get_conn3',
                  cache_id_funcname='_cache_id3',
                  exactly_one_funcname=None)


def check_vpc(vpc_id=None, vpc_name=None, region=None, key=None,
              keyid=None, profile=None):
    '''
    Check whether a VPC with the given name or id exists.
    Returns the vpc_id or None. Raises SaltInvocationError if
    both vpc_id and vpc_name are None. Optionally raise a
    CommandExecutionError if the VPC does not exist.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.check_vpc vpc_name=myvpc profile=awsprofile
    '''

    if not _exactly_one((vpc_name, vpc_id)):
        raise SaltInvocationError('One (but not both) of vpc_id or vpc_name '
                                  'must be provided.')
    if vpc_name:
        vpc_id = _get_id(vpc_name=vpc_name, region=region, key=key, keyid=keyid,
                         profile=profile)
    elif not _find_vpcs(vpc_id=vpc_id, region=region, key=key, keyid=keyid,
                        profile=profile):
        log.info('VPC {0} does not exist.'.format(vpc_id))
        return None
    return vpc_id


def _create_resource(resource, name=None, tags=None, region=None, key=None,
                     keyid=None, profile=None, **kwargs):
    '''
    Create a VPC resource. Returns the resource id if created, or False
    if not created.
    '''

    try:
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            create_resource = getattr(conn, 'create_' + resource)
        except AttributeError:
            raise AttributeError('{0} function does not exist for boto VPC '
                                 'connection.'.format('create_' + resource))

        if name and _get_resource_id(resource, name, region=region, key=key,
                                     keyid=keyid, profile=profile):
            return {'created': False, 'error': {'message':
                    'A {0} named {1} already exists.'.format(
                        resource, name)}}

        r = create_resource(**kwargs)

        if r:
            if isinstance(r, bool):
                return {'created': True}
            else:
                log.info('A {0} with id {1} was created'.format(resource, r.id))
                _maybe_set_name_tag(name, r)
                _maybe_set_tags(tags, r)

                if name:
                    _cache_id(name,
                              sub_resource=resource,
                              resource_id=r.id,
                              region=region,
                              key=key, keyid=keyid,
                              profile=profile)
                return {'created': True, 'id': r.id}
        else:
            if name:
                e = '{0} {1} was not created.'.format(resource, name)
            else:
                e = '{0} was not created.'.format(resource)
            log.warning(e)
            return {'created': False, 'error': {'message': e}}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def _delete_resource(resource, name=None, resource_id=None, region=None,
                     key=None, keyid=None, profile=None, **kwargs):
    '''
    Delete a VPC resource. Returns True if successful, otherwise False.
    '''

    if not _exactly_one((name, resource_id)):
        raise SaltInvocationError('One (but not both) of name or id must be '
                                  'provided.')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

        try:
            delete_resource = getattr(conn, 'delete_' + resource)
        except AttributeError:
            raise AttributeError('{0} function does not exist for boto VPC '
                                 'connection.'.format('delete_' + resource))
        if name:
            resource_id = _get_resource_id(resource, name,
                                           region=region, key=key,
                                           keyid=keyid, profile=profile)
            if not resource_id:
                return {'deleted': False, 'error': {'message':
                        '{0} {1} does not exist.'.format(resource, name)}}

        if delete_resource(resource_id, **kwargs):
            _cache_id(name, sub_resource=resource,
                      resource_id=resource_id,
                      invalidate=True,
                      region=region,
                      key=key, keyid=keyid,
                      profile=profile)
            return {'deleted': True}
        else:
            if name:
                e = '{0} {1} was not deleted.'.format(resource, name)
            else:
                e = '{0} was not deleted.'.format(resource)
            return {'deleted': False, 'error': {'message': e}}
    except BotoServerError as e:
        return {'deleted': False, 'error': salt.utils.boto.get_error(e)}


def _get_resource(resource, name=None, resource_id=None, region=None,
                  key=None, keyid=None, profile=None):
    '''
    Get a VPC resource based on resource type and name or id.
    Cache the id if name was provided.
    '''

    if not _exactly_one((name, resource_id)):
        raise SaltInvocationError('One (but not both) of name or id must be '
                                  'provided.')

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    f = 'get_all_{0}'.format(resource)
    if not f.endswith('s'):
        f = f + 's'
    get_resources = getattr(conn, f)
    filter_parameters = {}

    if name:
        filter_parameters['filters'] = {'tag:Name': name}
    if resource_id:
        filter_parameters['{0}_ids'.format(resource)] = resource_id

    try:
        r = get_resources(**filter_parameters)
    except BotoServerError as e:
        if e.code.endswith('.NotFound'):
            return None
        raise

    if r:
        if len(r) == 1:
            if name:
                _cache_id(name, sub_resource=resource,
                          resource_id=r[0].id,
                          region=region,
                          key=key, keyid=keyid,
                          profile=profile)
            return r[0]
        else:
            raise CommandExecutionError('Found more than one '
                                        '{0} named "{1}"'.format(
                                            resource, name))
    else:
        return None


def _find_resources(resource, name=None, resource_id=None, tags=None,
                    region=None, key=None, keyid=None, profile=None):
    '''
    Get VPC resources based on resource type and name, id, or tags.
    '''

    if all((resource_id, name)):
        raise SaltInvocationError('Only one of name or id may be '
                                  'provided.')

    if not any((resource_id, name, tags)):
        raise SaltInvocationError('At least one of the following must be '
                                  'provided: id, name, or tags.')

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    f = 'get_all_{0}'.format(resource)
    if not f.endswith('s'):
        f = f + 's'
    get_resources = getattr(conn, f)

    filter_parameters = {}
    if name:
        filter_parameters['filters'] = {'tag:Name': name}
    if resource_id:
        filter_parameters['{0}_ids'.format(resource)] = resource_id
    if tags:
        for tag_name, tag_value in six.iteritems(tags):
            filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

    try:
        r = get_resources(**filter_parameters)
    except BotoServerError as e:
        if e.code.endswith('.NotFound'):
            return None
        raise
    return r


def _get_resource_id(resource, name, region=None, key=None,
                     keyid=None, profile=None):
    '''
    Get an AWS id for a VPC resource by type and name.
    '''

    _id = _cache_id(name, sub_resource=resource,
                    region=region, key=key,
                    keyid=keyid, profile=profile)
    if _id:
        return _id

    r = _get_resource(resource, name=name, region=region, key=key,
                      keyid=keyid, profile=profile)

    if r:
        return r.id


def get_resource_id(resource, name=None, resource_id=None, region=None,
                    key=None, keyid=None, profile=None):
    '''
    Get an AWS id for a VPC resource by type and name.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.get_resource_id internet_gateway myigw

    '''

    try:
        return {'id': _get_resource_id(resource, name, region=region, key=key,
                                       keyid=keyid, profile=profile)}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def resource_exists(resource, name=None, resource_id=None, tags=None,
                    region=None, key=None, keyid=None, profile=None):
    '''
    Given a resource type and name, return {exists: true} if it exists,
    {exists: false} if it does not exist, or {error: {message: error text}
    on error.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.resource_exists internet_gateway myigw

    '''

    try:
        return {'exists': bool(_find_resources(resource, name=name,
                                               resource_id=resource_id,
                                               tags=tags, region=region,
                                               key=key, keyid=keyid,
                                               profile=profile))}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def _find_vpcs(vpc_id=None, vpc_name=None, cidr=None, tags=None,
               region=None, key=None, keyid=None, profile=None):

    '''
    Given VPC properties, find and return matching VPC ids.
    '''

    if all((vpc_id, vpc_name)):
        raise SaltInvocationError('Only one of vpc_name or vpc_id may be '
                                  'provided.')

    if not any((vpc_id, vpc_name, tags, cidr)):
        raise SaltInvocationError('At least one of the following must be '
                                  'provided: vpc_id, vpc_name, cidr or tags.')

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    filter_parameters = {'filters': {}}

    if vpc_id:
        filter_parameters['vpc_ids'] = [vpc_id]

    if cidr:
        filter_parameters['filters']['cidr'] = cidr

    if vpc_name:
        filter_parameters['filters']['tag:Name'] = vpc_name

    if tags:
        for tag_name, tag_value in six.iteritems(tags):
            filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

    vpcs = conn.get_all_vpcs(**filter_parameters)
    log.debug('The filters criteria {0} matched the following VPCs:{1}'.format(filter_parameters, vpcs))

    if vpcs:
        return [vpc.id for vpc in vpcs]
    else:
        return []


def _get_id(vpc_name=None, cidr=None, tags=None, region=None, key=None,
            keyid=None, profile=None):
    '''
    Given VPC properties, return the VPC id if a match is found.
    '''

    if vpc_name and not any((cidr, tags)):
        vpc_id = _cache_id(vpc_name, region=region,
                           key=key, keyid=keyid,
                           profile=profile)
        if vpc_id:
            return vpc_id

    vpc_ids = _find_vpcs(vpc_name=vpc_name, cidr=cidr, tags=tags, region=region,
                         key=key, keyid=keyid, profile=profile)
    if vpc_ids:
        log.info("Matching VPC: {0}".format(" ".join(vpc_ids)))
        if len(vpc_ids) == 1:
            vpc_id = vpc_ids[0]
            if vpc_name:
                _cache_id(vpc_name, vpc_id,
                          region=region, key=key,
                          keyid=keyid, profile=profile)
            return vpc_id
        else:
            raise CommandExecutionError('Found more than one VPC matching the criteria.')
    else:
        log.info('No VPC found.')
        return None


def get_id(name=None, cidr=None, tags=None, region=None, key=None, keyid=None,
           profile=None):
    '''
    Given VPC properties, return the VPC id if a match is found.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.get_id myvpc

    '''

    try:
        return {'id': _get_id(vpc_name=name, cidr=cidr, tags=tags, region=region,
                              key=key, keyid=keyid, profile=profile)}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def exists(vpc_id=None, name=None, cidr=None, tags=None, region=None, key=None,
           keyid=None, profile=None):
    '''
    Given a VPC ID, check to see if the given VPC ID exists.

    Returns True if the given VPC ID exists and returns False if the given
    VPC ID does not exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.exists myvpc

    '''

    try:
        vpc_ids = _find_vpcs(vpc_id=vpc_id, vpc_name=name, cidr=cidr, tags=tags,
                             region=region, key=key, keyid=keyid, profile=profile)
        return {'exists': bool(vpc_ids)}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def create(cidr_block, instance_tenancy=None, vpc_name=None,
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
            _maybe_name_route_table(conn, vpc.id, vpc_name)
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
        vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
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


def describe_vpcs(vpc_id=None, name=None, cidr=None, tags=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Describe all VPCs, matching the filter criteria if provided.

    Returns a a list of dictionaries with interesting properties.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.describe_vpcs

    '''

    keys = ('id',
            'cidr_block',
            'is_default',
            'state',
            'tags',
            'dhcp_options_id',
            'instance_tenancy')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'filters': {}}

        if vpc_id:
            filter_parameters['vpc_ids'] = [vpc_id]

        if cidr:
            filter_parameters['filters']['cidr'] = cidr

        if name:
            filter_parameters['filters']['tag:Name'] = name

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

        vpcs = conn.get_all_vpcs(**filter_parameters)

        if vpcs:
            ret = []
            for vpc in vpcs:
                ret.append(dict((k, getattr(vpc, k)) for k in keys))
            return {'vpcs': ret}
        else:
            return {'vpcs': None}

    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def _find_subnets(subnet_name=None, vpc_id=None, cidr=None, tags=None, conn=None):
    '''
    Given subnet properties, find and return matching subnet ids
    '''

    if not any(subnet_name, tags, cidr):
        raise SaltInvocationError('At least one of the following must be '
                                  'specified: subnet_name, cidr or tags.')

    filter_parameters = {'filters': {}}

    if cidr:
        filter_parameters['filters']['cidr'] = cidr

    if subnet_name:
        filter_parameters['filters']['tag:Name'] = subnet_name

    if vpc_id:
        filter_parameters['filters']['VpcId'] = vpc_id

    if tags:
        for tag_name, tag_value in six.iteritems(tags):
            filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

    subnets = conn.get_all_subnets(**filter_parameters)
    log.debug('The filters criteria {0} matched the following subnets: {1}'.format(filter_parameters, subnets))

    if subnets:
        return [subnet.id for subnet in subnets]
    else:
        return False


def create_subnet(vpc_id=None, cidr_block=None, vpc_name=None,
                  availability_zone=None, subnet_name=None, tags=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid VPC ID or Name and a CIDR block, create a subnet for the VPC.

    An optional availability zone argument can be provided.

    Returns True if the VPC subnet was created and returns False if the VPC subnet was not created.

    .. versionchanged:: 2015.8.0
        Added vpc_name argument

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.create_subnet vpc_id='vpc-6b1fe402' \\
                subnet_name='mysubnet' cidr_block='10.0.0.0/25'
        salt myminion boto_vpc.create_subnet vpc_name='myvpc' \\
                subnet_name='mysubnet', cidr_block='10.0.0.0/25'
    '''

    try:
        vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
        if not vpc_id:
            return {'created': False, 'error': {'message': 'VPC {0} does not exist.'.format(vpc_name or vpc_id)}}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}

    return _create_resource('subnet', name=subnet_name, tags=tags, vpc_id=vpc_id,
                            availability_zone=availability_zone,
                            cidr_block=cidr_block, region=region, key=key,
                            keyid=keyid, profile=profile)


def delete_subnet(subnet_id=None, subnet_name=None, region=None, key=None,
                  keyid=None, profile=None):
    '''
    Given a subnet ID or name, delete the subnet.

    Returns True if the subnet was deleted and returns False if the subnet was not deleted.

    .. versionchanged:: 2015.8.0
        Added subnet_name argument

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete_subnet 'subnet-6a1fe403'

    '''

    return _delete_resource(resource='subnet', name=subnet_name,
                            resource_id=subnet_id, region=region, key=key,
                            keyid=keyid, profile=profile)


def subnet_exists(subnet_id=None, name=None, subnet_name=None, cidr=None,
                  tags=None, zones=None, region=None, key=None, keyid=None,
                  profile=None):
    '''
    Check if a subnet exists.

    Returns True if the subnet exists, otherwise returns False.

    .. versionchanged:: 2015.8.0
        Added subnet_name argument
        Deprecated name argument

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.subnet_exists subnet_id='subnet-6a1fe403'

    '''
    if name:
        log.warning('boto_vpc.subnet_exists: name parameter is deprecated '
                    'use subnet_name instead.')
        subnet_name = name

    if not any((subnet_id, subnet_name, cidr, tags, zones)):
        raise SaltInvocationError('At least one of the following must be '
                                  'specified: subnet id, cidr, subnet_name, '
                                  'tags, or zones.')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'filters': {}}

        if subnet_id:
            filter_parameters['subnet_ids'] = [subnet_id]

        if subnet_name:
            filter_parameters['filters']['tag:Name'] = subnet_name

        if cidr:
            filter_parameters['filters']['cidr'] = cidr

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

        if zones:
            filter_parameters['filters']['availability_zone'] = zones

        subnets = conn.get_all_subnets(**filter_parameters)
        log.debug('The filters criteria {0} matched the following subnets:{1}'.format(filter_parameters, subnets))
        if subnets:
            log.info('Subnet {0} exists.'.format(subnet_name or subnet_id))
            return {'exists': True}
        else:
            log.info('Subnet {0} does not exist.'.format(subnet_name or subnet_id))
            return {'exists': False}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def get_subnet_association(subnets, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Given a subnet (aka: a vpc zone identifier) or list of subnets, returns
    vpc association.

    Returns a VPC ID if the given subnets are associated with the same VPC ID.
    Returns False on an error or if the given subnets are associated with
    different VPC IDs.

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.get_subnet_association subnet-61b47516

    .. code-block:: bash

        salt myminion boto_vpc.get_subnet_association ['subnet-61b47516','subnet-2cb9785b']

    '''
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

        # subnet_ids=subnets can accept either a string or a list
        subnets = conn.get_all_subnets(subnet_ids=subnets)
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}

    # using a set to store vpc_ids - the use of set prevents duplicate
    # vpc_id values
    vpc_ids = set()
    for subnet in subnets:
        log.debug('examining subnet id: {0} for vpc_id'.format(subnet.id))
        if subnet in subnets:
            log.debug('subnet id: {0} is associated with vpc id: {1}'
                      .format(subnet.id, subnet.vpc_id))
            vpc_ids.add(subnet.vpc_id)
    if not vpc_ids:
        return {'vpc_id': None}
    elif len(vpc_ids) == 1:
        return {'vpc_id': vpc_ids.pop()}
    else:
        return {'vpc_ids': list(vpc_ids)}


def describe_subnet(subnet_id=None, subnet_name=None, region=None,
                    key=None, keyid=None, profile=None):
    '''
    Given a subnet id or name, describe its properties.

    Returns a dictionary of interesting properties.

    .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.describe_subnet subnet_id=subnet-123456
        salt myminion boto_vpc.describe_subnet subnet_name=mysubnet

    '''
    try:
        subnet = _get_resource('subnet', name=subnet_name, resource_id=subnet_id,
                               region=region, key=key, keyid=keyid, profile=profile)
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}

    if not subnet:
        return {'subnet': None}
    log.debug('Found subnet: {0}'.format(subnet.id))

    keys = ('id', 'cidr_block', 'availability_zone', 'tags')
    return {'subnet': dict((k, getattr(subnet, k)) for k in keys)}


def describe_subnets(subnet_ids=None, subnet_names=None, vpc_id=None, cidr=None,
                     region=None, key=None, keyid=None, profile=None):
    '''
    Given a VPC ID or subnet CIDR, returns a list of associated subnets and
    their details. Return all subnets if VPC ID or CIDR are not provided.
    If a subnet id or CIDR is provided, only its associated subnet details will be
    returned.

    .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.describe_subnets

    .. code-block:: bash

        salt myminion boto_vpc.describe_subnets subnet_ids=['subnet-ba1987ab', 'subnet-ba1987cd']

    .. code-block:: bash

        salt myminion boto_vpc.describe_subnets vpc_id=vpc-123456

    .. code-block:: bash

        salt myminion boto_vpc.describe_subnets cidr=10.0.0.0/21

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'filters': {}}

        if vpc_id:
            filter_parameters['filters']['vpcId'] = vpc_id

        if cidr:
            filter_parameters['filters']['cidrBlock'] = cidr

        if subnet_names:
            filter_parameters['filters']['tag:Name'] = subnet_names

        subnets = conn.get_all_subnets(subnet_ids=subnet_ids, **filter_parameters)
        log.debug('The filters criteria {0} matched the following subnets: '
                  '{1}'.format(filter_parameters, subnets))

        if not subnets:
            return {'subnets': None}

        subnets_list = []
        keys = ('id', 'cidr_block', 'availability_zone', 'tags')
        for item in subnets:
            subnet = {}
            for key in keys:
                if hasattr(item, key):
                    subnet[key] = getattr(item, key)
            subnets_list.append(subnet)
        return {'subnets': subnets_list}

    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def create_internet_gateway(internet_gateway_name=None, vpc_id=None,
                            vpc_name=None, tags=None, region=None, key=None,
                            keyid=None, profile=None):
    '''
    Create an Internet Gateway, optionally attaching it to an existing VPC.

    Returns the internet gateway id if the internet gateway was created and
    returns False if the internet gateways was not created.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_internet_gateway \\
                internet_gateway_name=myigw vpc_name=myvpc

    '''

    try:
        if vpc_id or vpc_name:
            vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
            if not vpc_id:
                return {'created': False,
                        'error': {'message': 'VPC {0} does not exist.'.format(vpc_name or vpc_id)}}

        r = _create_resource('internet_gateway', name=internet_gateway_name,
                             tags=tags, region=region, key=key, keyid=keyid,
                             profile=profile)
        if r.get('created') and vpc_id:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.attach_internet_gateway(r['id'], vpc_id)
            log.info('Attached internet gateway {0} to '
                     'VPC {1}'.format(r['id'], (vpc_name or vpc_id)))
        return r
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete_internet_gateway(internet_gateway_id=None,
                            internet_gateway_name=None,
                            detach=False, region=None,
                            key=None, keyid=None, profile=None):
    '''
    Delete an internet gateway (by name or id).

    Returns True if the internet gateway was deleted and otherwise False.

    .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.delete_internet_gateway internet_gateway_id=igw-1a2b3c
        salt myminion boto_vpc.delete_internet_gateway internet_gateway_name=myigw

    '''

    try:
        if internet_gateway_name:
            internet_gateway_id = _get_resource_id('internet_gateway',
                                                   internet_gateway_name,
                                                   region=region, key=key,
                                                   keyid=keyid, profile=profile)
        if not internet_gateway_id:
            return {'deleted': False, 'error': {
                    'message': 'internet gateway {0} does not exist.'.format(
                        internet_gateway_name)}}

        if detach:
            igw = _get_resource('internet_gateway',
                                resource_id=internet_gateway_id, region=region,
                                key=key, keyid=keyid, profile=profile)

            if not igw:
                return {'deleted': False, 'error': {
                        'message': 'internet gateway {0} does not exist.'.format(
                            internet_gateway_id)}}

            if igw.attachments:
                conn = _get_conn(region=region, key=key, keyid=keyid,
                                 profile=profile)
                conn.detach_internet_gateway(internet_gateway_id,
                                             igw.attachments[0].vpc_id)
        return _delete_resource('internet_gateway',
                                resource_id=internet_gateway_id,
                                region=region, key=key, keyid=keyid,
                                profile=profile)
    except BotoServerError as e:
        return {'deleted': False, 'error': salt.utils.boto.get_error(e)}


def _find_nat_gateways(nat_gateway_id=None, subnet_id=None, subnet_name=None, vpc_id=None, vpc_name=None,
                       states=('pending', 'available'),
                       region=None, key=None, keyid=None, profile=None):
    '''
    Given gateway properties, find and return matching nat gateways
    '''

    if not any((nat_gateway_id, subnet_id, subnet_name, vpc_id, vpc_name)):
        raise SaltInvocationError('At least one of the following must be '
                                  'provided: nat_gateway_id, subnet_id, '
                                  'subnet_name, vpc_id, or vpc_name.')
    filter_parameters = {'Filter': []}

    if nat_gateway_id:
        filter_parameters['NatGatewayIds'] = [nat_gateway_id]

    if subnet_name:
        subnet_id = _get_resource_id('subnet', subnet_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
        if not subnet_id:
            return False

    if subnet_id:
        filter_parameters['Filter'].append({'Name': 'subnet-id', 'Values': [subnet_id]})

    if vpc_name:
        vpc_id = _get_resource_id('vpc', vpc_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
        if not vpc_id:
            return False

    if vpc_id:
        filter_parameters['Filter'].append({'Name': 'vpc-id', 'Values': [vpc_id]})

    conn3 = _get_conn3(region=region, key=key, keyid=keyid, profile=profile)
    nat_gateways = []
    for ret in salt.utils.boto3.paged_call(conn3.describe_nat_gateways,
                                           marker_flag='NextToken', marker_arg='NextToken',
                                           **filter_parameters):
        for gw in ret.get('NatGateways', []):
            if gw.get('State') in states:
                nat_gateways.append(gw)
    log.debug('The filters criteria {0} matched the following nat gateways: {1}'.format(filter_parameters, nat_gateways))

    if nat_gateways:
        return nat_gateways
    else:
        return False


def nat_gateway_exists(nat_gateway_id=None, subnet_id=None, subnet_name=None,
                       vpc_id=None, vpc_name=None,
                       states=('pending', 'available'),
                       region=None, key=None, keyid=None, profile=None):
    '''
    Checks if a nat gateway exists.

    This function requires boto3 to be installed.

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.nat_gateway_exists nat_gateway_id='nat-03b02643b43216fe7'
        salt myminion boto_vpc.nat_gateway_exists subnet_id='subnet-5b05942d'

    '''

    return bool(_find_nat_gateways(nat_gateway_id=nat_gateway_id,
                                   subnet_id=subnet_id,
                                   subnet_name=subnet_name,
                                   vpc_id=vpc_id,
                                   vpc_name=vpc_name,
                                   states=states,
                           region=region, key=key, keyid=keyid,
                           profile=profile))


def describe_nat_gateways(nat_gateway_id=None, subnet_id=None, subnet_name=None,
                       vpc_id=None, vpc_name=None,
                       states=('pending', 'available'),
                       region=None, key=None, keyid=None, profile=None):
    '''
    Return a description of nat gateways matching the selection criteria

    This function requires boto3 to be installed.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.describe_nat_gateways nat_gateway_id='nat-03b02643b43216fe7'
        salt myminion boto_vpc.describe_nat_gateways subnet_id='subnet-5b05942d'

    '''

    return _find_nat_gateways(nat_gateway_id=nat_gateway_id,
                                   subnet_id=subnet_id,
                                   subnet_name=subnet_name,
                                   vpc_id=vpc_id,
                                   vpc_name=vpc_name,
                                   states=states,
                           region=region, key=key, keyid=keyid,
                           profile=profile)


def create_nat_gateway(subnet_id=None,
                       subnet_name=None, allocation_id=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Create a NAT Gateway within an existing subnet. If allocation_id is
    specified, the elastic IP address it references is associated with the
    gateway. Otherwise, a new allocation_id is created and used.

    This function requires boto3 to be installed.

    Returns the nat gateway id if the nat gateway was created and
    returns False if the nat gateway was not created.

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_nat_gateway subnet_name=mysubnet

    '''

    try:
        if all((subnet_id, subnet_name)):
            raise SaltInvocationError('Only one of subnet_name or subnet_id may be '
                                  'provided.')
        if subnet_name:
            subnet_id = _get_resource_id('subnet', subnet_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
            if not subnet_id:
                return {'created': False,
                        'error': {'message': 'Subnet {0} does not exist.'.format(subnet_name)}}
        else:
            if not _get_resource('subnet', resource_id=subnet_id,
                                 region=region, key=key, keyid=keyid, profile=profile):
                return {'created': False,
                        'error': {'message': 'Subnet {0} does not exist.'.format(subnet_id)}}

        conn3 = _get_conn3(region=region, key=key, keyid=keyid, profile=profile)

        if not allocation_id:
            address = conn3.allocate_address(Domain='vpc')
            allocation_id = address.get('AllocationId')

        # Have to go to boto3 to create NAT gateway
        r = conn3.create_nat_gateway(SubnetId=subnet_id, AllocationId=allocation_id)
        return {'created': True, 'id': r.get('NatGateway', {}).get('NatGatewayId')}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete_nat_gateway(nat_gateway_id,
                       release_eips=False, region=None,
                       key=None, keyid=None, profile=None):
    '''
    Delete a nat gateway (by id).

    Returns True if the internet gateway was deleted and otherwise False.

    This function requires boto3 to be installed.

    .. versionadded:: Carbon

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.delete_nat_gateway nat_gateway_id=igw-1a2b3c

    '''

    try:
        conn3 = _get_conn3(region=region, key=key, keyid=keyid, profile=profile)
        gwinfo = conn3.describe_nat_gateways(NatGatewayIds=[nat_gateway_id])
        if gwinfo:
            gwinfo = gwinfo.get('NatGateways', [None])[0]
        conn3.delete_nat_gateway(NatGatewayId=nat_gateway_id)
        if release_eips and gwinfo:
            for addr in gwinfo.get('NatGatewayAddresses'):
                conn3.release_address(AllocationId=addr.get('AllocationId'))
        return {'deleted': True}
    except BotoServerError as e:
        return {'deleted': False, 'error': salt.utils.boto.get_error(e)}


def create_customer_gateway(vpn_connection_type, ip_address, bgp_asn,
                            customer_gateway_name=None, tags=None,
                            region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid VPN connection type, a static IP address and a customer
    gateway’s Border Gateway Protocol (BGP) Autonomous System Number,
    create a customer gateway.

    Returns the customer gateway id if the customer gateway was created and
    returns False if the customer gateway was not created.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_customer_gateway 'ipsec.1', '12.1.2.3', 65534

    '''

    return _create_resource('customer_gateway', customer_gateway_name,
                            type=vpn_connection_type,
                            ip_address=ip_address, bgp_asn=bgp_asn,
                            tags=tags, region=region, key=key,
                            keyid=keyid, profile=profile)


def delete_customer_gateway(customer_gateway_id=None, customer_gateway_name=None,
                            region=None, key=None, keyid=None, profile=None):
    '''
    Given a customer gateway ID or name, delete the customer gateway.

    Returns True if the customer gateway was deleted and returns False if the customer gateway was not deleted.

    .. versionchanged:: 2015.8.0
        Added customer_gateway_name argument

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete_customer_gateway 'cgw-b6a247df'

    '''

    return _delete_resource(resource='customer_gateway',
                            name=customer_gateway_name,
                            resource_id=customer_gateway_id,
                            region=region, key=key,
                            keyid=keyid, profile=profile)


def customer_gateway_exists(customer_gateway_id=None, customer_gateway_name=None,
                            region=None, key=None, keyid=None, profile=None):
    '''
    Given a customer gateway ID, check if the customer gateway ID exists.

    Returns True if the customer gateway ID exists; Returns False otherwise.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.customer_gateway_exists cgw-b6a247df
        salt myminion boto_vpc.customer_gateway_exists customer_gatway_name=mycgw

    '''

    return resource_exists('customer_gateway', name=customer_gateway_name,
                           resource_id=customer_gateway_id,
                           region=region, key=key, keyid=keyid, profile=profile)


def create_dhcp_options(domain_name=None, domain_name_servers=None, ntp_servers=None,
                        netbios_name_servers=None, netbios_node_type=None,
                        dhcp_options_name=None, tags=None, vpc_id=None, vpc_name=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Given valid DHCP options, create a DHCP options record, optionally associating it with
    an existing VPC.

    Returns True if the DHCP options record was created and returns False if the DHCP options record was not deleted.

    .. versionchanged:: 2015.8.0
        Added vpc_name and vpc_id arguments

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_dhcp_options domain_name='example.com' \\
                domain_name_servers='[1.2.3.4]' ntp_servers='[5.6.7.8]' \\
                netbios_name_servers='[10.0.0.1]' netbios_node_type=1 \\
                vpc_name='myvpc'

    '''

    try:
        if vpc_id or vpc_name:
            vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
            if not vpc_id:
                return {'created': False,
                        'error': {'message': 'VPC {0} does not exist.'.format(vpc_name or vpc_id)}}

        r = _create_resource('dhcp_options', name=dhcp_options_name, domain_name=domain_name,
                             domain_name_servers=domain_name_servers,
                             ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                             netbios_node_type=netbios_node_type,
                             region=region, key=key, keyid=keyid,
                             profile=profile)
        if r.get('created') and vpc_id:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            conn.associate_dhcp_options(r['id'], vpc_id)
            log.info('Associated options {0} to '
                     'VPC {1}'.format(r['id'], (vpc_name or vpc_id)))
        return r
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def get_dhcp_options(dhcp_options_name=None, dhcp_options_id=None,
                     region=None, key=None, keyid=None, profile=None):
    '''
    Return a dict with the current values of the requested DHCP options set

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.get_dhcp_options 'myfunnydhcpoptionsname'

    .. versionadded:: 2016.3.0
    '''
    if not any((dhcp_options_name, dhcp_options_id)):
        raise SaltInvocationError('At least one of the following must be specified: '
                                  'dhcp_options_name, dhcp_options_id.')

    if not dhcp_options_id and dhcp_options_name:
        dhcp_options_id = _get_resource_id('dhcp_options', dhcp_options_name,
                                            region=region, key=key,
                                            keyid=keyid, profile=profile)
    if not dhcp_options_id:
        return {'dhcp_options': {}}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        r = conn.get_all_dhcp_options(dhcp_options_ids=[dhcp_options_id])
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}

    if not r:
        return {'dhcp_options': None}

    keys = ('domain_name', 'domain_name_servers', 'ntp_servers',
            'netbios_name_servers', 'netbios_node_type')

    return {'dhcp_options': dict((k, r[0].options.get(k)) for k in keys)}


def delete_dhcp_options(dhcp_options_id=None, dhcp_options_name=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Delete dhcp options by id or name.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete_dhcp_options 'dopt-b6a247df'

    '''

    return _delete_resource(resource='dhcp_options',
                            name=dhcp_options_name,
                            resource_id=dhcp_options_id,
                            region=region, key=key,
                            keyid=keyid, profile=profile)


def associate_dhcp_options_to_vpc(dhcp_options_id, vpc_id=None, vpc_name=None,
                                  region=None, key=None, keyid=None, profile=None):
    '''
    Given valid DHCP options id and a valid VPC id, associate the DHCP options record with the VPC.

    Returns True if the DHCP options record were associated and returns False if the DHCP options record was not associated.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.associate_dhcp_options_to_vpc 'dhcp-a0bl34pp' 'vpc-6b1fe402'

    '''
    try:
        vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
        if not vpc_id:
            return {'associated': False,
                    'error': {'message': 'VPC {0} does not exist.'.format(vpc_name or vpc_id)}}

        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if conn.associate_dhcp_options(dhcp_options_id, vpc_id):
            log.info('DHCP options with id {0} were associated with VPC {1}'.format(dhcp_options_id, vpc_id))
            return {'associated': True}
        else:
            log.warning('DHCP options with id {0} were not associated with VPC {1}'.format(dhcp_options_id, vpc_id))
            return {'associated': False, 'error': {'message': 'DHCP options could not be associated.'}}
    except BotoServerError as e:
        return {'associated': False, 'error': salt.utils.boto.get_error(e)}


def dhcp_options_exists(dhcp_options_id=None, name=None, dhcp_options_name=None,
                        tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Check if a dhcp option exists.

    Returns True if the dhcp option exists; Returns False otherwise.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.dhcp_options_exists dhcp_options_id='dhcp-a0bl34pp'

    '''

    if name:
        log.warning('boto_vpc.dhcp_options_exists: name parameter is deprecated '
                    'use dhcp_options_name instead.')
        dhcp_options_name = name

    return resource_exists('dhcp_options', name=dhcp_options_name,
                           resource_id=dhcp_options_id, tags=tags,
                           region=region, key=key, keyid=keyid,
                           profile=profile)


def create_network_acl(vpc_id=None, vpc_name=None, network_acl_name=None,
                       subnet_id=None, subnet_name=None, tags=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Given a vpc_id, creates a network acl.

    Returns the network acl id if successful, otherwise returns False.

    .. versionchanged:: 2015.8.0
        Added vpc_name, subnet_id, and subnet_name arguments

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_network_acl 'vpc-6b1fe402'

    '''

    _id = vpc_name or vpc_id

    try:
        vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}

    if not vpc_id:
        return {'created': False,
                'error': {'message': 'VPC {0} does not exist.'.format(_id)}}

    if all((subnet_id, subnet_name)):
        raise SaltInvocationError('Only one of subnet_name or subnet_id may be '
                                  'provided.')
    if subnet_name:
        subnet_id = _get_resource_id('subnet', subnet_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
        if not subnet_id:
            return {'created': False,
                    'error': {'message': 'Subnet {0} does not exist.'.format(subnet_name)}}
    elif subnet_id:
        if not _get_resource('subnet', resource_id=subnet_id,
                             region=region, key=key, keyid=keyid, profile=profile):
            return {'created': False,
                    'error': {'message': 'Subnet {0} does not exist.'.format(subnet_id)}}

    r = _create_resource('network_acl', name=network_acl_name, vpc_id=vpc_id,
                         region=region, key=key, keyid=keyid,
                         profile=profile)

    if r.get('created') and subnet_id:
        try:
            conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
            association_id = conn.associate_network_acl(r['id'], subnet_id)
        except BotoServerError as e:
            return {'created': False, 'error': salt.utils.boto.get_error(e)}
        r['association_id'] = association_id
    return r


def delete_network_acl(network_acl_id=None, network_acl_name=None, disassociate=False,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Delete a network acl based on the network_acl_id or network_acl_name provided.

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.delete_network_acl network_acl_id='acl-5fb85d36' \\
                disassociate=false

    .. code-block:: bash

        salt myminion boto_vpc.delete_network_acl network_acl_name='myacl' \\
                disassociate=true

    '''

    if disassociate:
        network_acl = _get_resource('network_acl', name=network_acl_name, region=region, key=key, keyid=keyid, profile=profile)
        if network_acl and network_acl.associations:
            subnet_id = network_acl.associations[0].subnet_id
            try:
                conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
                conn.disassociate_network_acl(subnet_id)
            except BotoServerError:
                pass

    return _delete_resource(resource='network_acl',
                            name=network_acl_name,
                            resource_id=network_acl_id,
                            region=region, key=key,
                            keyid=keyid, profile=profile)


def network_acl_exists(network_acl_id=None, name=None, network_acl_name=None,
                       tags=None, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Checks if a network acl exists.

    Returns True if the network acl exists or returns False if it doesn't exist.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.network_acl_exists network_acl_id='acl-5fb85d36'
    '''

    if name:
        log.warning('boto_vpc.network_acl_exists: name parameter is deprecated '
                    'use network_acl_name instead.')
        network_acl_name = name

    return resource_exists('network_acl', name=network_acl_name,
                           resource_id=network_acl_id, tags=tags,
                           region=region, key=key, keyid=keyid,
                           profile=profile)


def associate_network_acl_to_subnet(network_acl_id=None, subnet_id=None,
                                    network_acl_name=None,
                                    subnet_name=None, region=None,
                                    key=None, keyid=None, profile=None):
    '''
    Given a network acl and subnet ids or names, associate a network acl to a subnet.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.associate_network_acl_to_subnet \\
                network_acl_id='acl-5fb85d36' subnet_id='subnet-6a1fe403'

    .. code-block:: bash

        salt myminion boto_vpc.associate_network_acl_to_subnet \\
                network_acl_id='myacl' subnet_id='mysubnet'

    '''

    if network_acl_name:
        network_acl_id = _get_resource_id('network_acl', network_acl_name,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
        if not network_acl_id:
            return {'associated': False,
                    'error': {'message': 'Network ACL {0} does not exist.'.format(network_acl_name)}}
    if subnet_name:
        subnet_id = _get_resource_id('subnet', subnet_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
        if not subnet_id:
            return {'associated': False,
                    'error': {'message': 'Subnet {0} does not exist.'.format(subnet_name)}}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        association_id = conn.associate_network_acl(network_acl_id, subnet_id)
        if association_id:
            log.info('Network ACL with id {0} was associated with subnet {1}'.format(network_acl_id, subnet_id))

            return {'associated': True, 'id': association_id}
        else:
            log.warning('Network ACL with id {0} was not associated with subnet {1}'.format(network_acl_id, subnet_id))
            return {'associated': False, 'error': {'message': 'ACL could not be assocaited.'}}
    except BotoServerError as e:
        return {'associated': False, 'error': salt.utils.boto.get_error(e)}


def disassociate_network_acl(subnet_id=None, vpc_id=None, subnet_name=None, vpc_name=None,
                             region=None, key=None, keyid=None, profile=None):
    '''
    Given a subnet ID, disassociates a network acl.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.disassociate_network_acl 'subnet-6a1fe403'

    '''

    if not _exactly_one((subnet_name, subnet_id)):
        raise SaltInvocationError('One (but not both) of subnet_id or subnet_name '
                                  'must be provided.')

    if all((vpc_name, vpc_id)):
        raise SaltInvocationError('Only one of vpc_id or vpc_name '
                                  'may be provided.')
    try:
        if subnet_name:
            subnet_id = _get_resource_id('subnet', subnet_name,
                                         region=region, key=key,
                                         keyid=keyid, profile=profile)
            if not subnet_id:
                return {'disassociated': False,
                        'error': {'message': 'Subnet {0} does not exist.'.format(subnet_name)}}

        if vpc_name or vpc_id:
            vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)

        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        association_id = conn.disassociate_network_acl(subnet_id, vpc_id=vpc_id)
        return {'disassociated': True, 'association_id': association_id}
    except BotoServerError as e:
        return {'disassociated': False, 'error': salt.utils.boto.get_error(e)}


def _create_network_acl_entry(network_acl_id=None, rule_number=None, protocol=None,
                              rule_action=None, cidr_block=None, egress=None,
                              network_acl_name=None, icmp_code=None, icmp_type=None,
                              port_range_from=None, port_range_to=None, replace=False,
                              region=None, key=None, keyid=None, profile=None):
    if replace:
        rkey = 'replaced'
    else:
        rkey = 'created'

    if not _exactly_one((network_acl_name, network_acl_id)):
        raise SaltInvocationError('One (but not both) of network_acl_id or '
                                  'network_acl_name must be provided.')

    for v in ('rule_number', 'protocol', 'rule_action', 'cidr_block'):
        if locals()[v] is None:
            raise SaltInvocationError('{0} is required.'.format(v))

    if network_acl_name:
        network_acl_id = _get_resource_id('network_acl', network_acl_name,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
    if not network_acl_id:
        return {rkey: False,
                'error': {'message': 'Network ACL {0} does not exist.'.format(network_acl_name or network_acl_id)}}

    if isinstance(protocol, six.string_types):
        if protocol == 'all':
            protocol = -1
        else:
            try:
                protocol = socket.getprotobyname(protocol)
            except socket.error as e:
                raise SaltInvocationError(e)
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if replace:
            f = conn.replace_network_acl_entry
        else:
            f = conn.create_network_acl_entry
        created = f(network_acl_id, rule_number, protocol, rule_action,
                    cidr_block, egress=egress, icmp_code=icmp_code,
                    icmp_type=icmp_type, port_range_from=port_range_from,
                    port_range_to=port_range_to)
        if created:
            log.info('Network ACL entry was {0}'.format(rkey))
        else:
            log.warning('Network ACL entry was not {0}'.format(rkey))
        return {rkey: created}
    except BotoServerError as e:
        return {rkey: False, 'error': salt.utils.boto.get_error(e)}


def create_network_acl_entry(network_acl_id=None, rule_number=None, protocol=None,
                             rule_action=None, cidr_block=None, egress=None,
                             network_acl_name=None, icmp_code=None, icmp_type=None,
                             port_range_from=None, port_range_to=None,
                             region=None, key=None, keyid=None, profile=None):
    '''
    Creates a network acl entry.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_network_acl_entry 'acl-5fb85d36' '32767' \\
                'all' 'deny' '0.0.0.0/0' egress=true

    '''

    kwargs = locals()
    return _create_network_acl_entry(**kwargs)


def replace_network_acl_entry(network_acl_id=None, rule_number=None, protocol=None,
                              rule_action=None, cidr_block=None, egress=None,
                              network_acl_name=None, icmp_code=None, icmp_type=None,
                              port_range_from=None, port_range_to=None,
                              region=None, key=None, keyid=None, profile=None):
    '''

    Replaces a network acl entry.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.replace_network_acl_entry 'acl-5fb85d36' '32767' \\
                'all' 'deny' '0.0.0.0/0' egress=true

    '''

    kwargs = locals()
    return _create_network_acl_entry(replace=True, **kwargs)


def delete_network_acl_entry(network_acl_id=None, rule_number=None, egress=None,
                             network_acl_name=None, region=None, key=None, keyid=None,
                             profile=None):
    '''
    Deletes a network acl entry.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete_network_acl_entry 'acl-5fb85d36' '32767'

    '''
    if not _exactly_one((network_acl_name, network_acl_id)):
        raise SaltInvocationError('One (but not both) of network_acl_id or '
                                  'network_acl_name must be provided.')

    for v in ('rule_number', 'egress'):
        if locals()[v] is None:
            raise SaltInvocationError('{0} is required.'.format(v))

    if network_acl_name:
        network_acl_id = _get_resource_id('network_acl', network_acl_name,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
    if not network_acl_id:
        return {'deleted': False,
                'error': {'message': 'Network ACL {0} does not exist.'.format(network_acl_name or network_acl_id)}}
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        deleted = conn.delete_network_acl_entry(network_acl_id, rule_number, egress=egress)
        if deleted:
            log.info('Network ACL entry was deleted')
        else:
            log.warning('Network ACL was not deleted')
        return {'deleted': deleted}
    except BotoServerError as e:
        return {'deleted': False, 'error': salt.utils.boto.get_error(e)}


def create_route_table(vpc_id=None, vpc_name=None, route_table_name=None,
                       tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Creates a route table.

    .. versionchanged:: 2015.8.0
        Added vpc_name argument

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.create_route_table vpc_id='vpc-6b1fe402' \\
                route_table_name='myroutetable'
        salt myminion boto_vpc.create_route_table vpc_name='myvpc' \\
                route_table_name='myroutetable'
    '''
    vpc_id = check_vpc(vpc_id, vpc_name, region, key, keyid, profile)
    if not vpc_id:
        return {'created': False, 'error': {'message': 'VPC {0} does not exist.'.format(vpc_name or vpc_id)}}

    return _create_resource('route_table', route_table_name, tags=tags,
                            vpc_id=vpc_id, region=region, key=key,
                            keyid=keyid, profile=profile)


def delete_route_table(route_table_id=None, route_table_name=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Deletes a route table.

    CLI Examples:

    .. code-block:: bash

        salt myminion boto_vpc.delete_route_table route_table_id='rtb-1f382e7d'
        salt myminion boto_vpc.delete_route_table route_table_name='myroutetable'

    '''
    return _delete_resource(resource='route_table', name=route_table_name,
                            resource_id=route_table_id, region=region, key=key,
                            keyid=keyid, profile=profile)


def route_table_exists(route_table_id=None, name=None, route_table_name=None,
                       tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Checks if a route table exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.route_table_exists route_table_id='rtb-1f382e7d'

    '''

    if name:
        log.warning('boto_vpc.route_table_exists: name parameter is deprecated '
                    'use route_table_name instead.')
        route_table_name = name

    return resource_exists('route_table', name=route_table_name,
                           resource_id=route_table_id, tags=tags,
                           region=region, key=key, keyid=keyid,
                           profile=profile)


def route_exists(destination_cidr_block, route_table_name=None, route_table_id=None,
                 gateway_id=None, instance_id=None, interface_id=None, tags=None,
                 region=None, key=None, keyid=None, profile=None, vpc_peering_connection_id=None):
    '''
    Checks if a route exists.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.route_exists destination_cidr_block='10.0.0.0/20' gateway_id='local' route_table_name='test'

    '''

    if not any((route_table_name, route_table_id)):
        raise SaltInvocationError('At least one of the following must be specified: route table name or route table id.')

    if not any((gateway_id, instance_id, interface_id, vpc_peering_connection_id)):
        raise SaltInvocationError('At least one of the following must be specified: gateway id, instance id, '
                                  'interface id or VPC peering connection id.')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'filters': {}}

        if route_table_id:
            filter_parameters['route_table_ids'] = [route_table_id]

        if route_table_name:
            filter_parameters['filters']['tag:Name'] = route_table_name

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

        route_tables = conn.get_all_route_tables(**filter_parameters)

        if len(route_tables) != 1:
            raise SaltInvocationError('Found more than one route table.')

        route_check = {'destination_cidr_block': destination_cidr_block,
                       'gateway_id': gateway_id,
                       'instance_id': instance_id,
                       'interface_id': interface_id,
                       'vpc_peering_connection_id': vpc_peering_connection_id
                       }

        for route_match in route_tables[0].routes:

            route_dict = {'destination_cidr_block': route_match.destination_cidr_block,
                          'gateway_id': route_match.gateway_id,
                          'instance_id': route_match.instance_id,
                          'interface_id': route_match.interface_id,
                          'vpc_peering_connection_id': vpc_peering_connection_id
                          }
            route_comp = set(route_dict.items()) ^ set(route_check.items())
            if len(route_comp) == 0:
                log.info('Route {0} exists.'.format(destination_cidr_block))
                return {'exists': True}

        log.warning('Route {0} does not exist.'.format(destination_cidr_block))
        return {'exists': False}
    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def associate_route_table(route_table_id=None, subnet_id=None,
                          route_table_name=None, subnet_name=None,
                          region=None, key=None, keyid=None,
                          profile=None):
    '''
    Given a route table and subnet name or id, associates the route table with the subnet.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.associate_route_table 'rtb-1f382e7d' 'subnet-6a1fe403'

    .. code-block:: bash

        salt myminion boto_vpc.associate_route_table route_table_name='myrtb' \\
                subnet_name='mysubnet'

    '''

    if all((subnet_id, subnet_name)):
        raise SaltInvocationError('Only one of subnet_name or subnet_id may be '
                                  'provided.')
    if subnet_name:
        subnet_id = _get_resource_id('subnet', subnet_name,
                                     region=region, key=key,
                                     keyid=keyid, profile=profile)
        if not subnet_id:
            return {'associated': False,
                    'error': {'message': 'Subnet {0} does not exist.'.format(subnet_name)}}

    if all((route_table_id, route_table_name)):
        raise SaltInvocationError('Only one of route_table_name or route_table_id may be '
                                  'provided.')
    if route_table_name:
        route_table_id = _get_resource_id('route_table', route_table_name,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
        if not route_table_id:
            return {'associated': False,
                    'error': {'message': 'Route table {0} does not exist.'.format(route_table_name)}}

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        association_id = conn.associate_route_table(route_table_id, subnet_id)
        log.info('Route table {0} was associated with subnet {1}'.format(route_table_id, subnet_id))
        return {'association_id': association_id}
    except BotoServerError as e:
        return {'associated': False, 'error': salt.utils.boto.get_error(e)}


def disassociate_route_table(association_id, region=None, key=None, keyid=None, profile=None):
    '''
    Dissassociates a route table.

    association_id
        The Route Table Association ID to disassociate

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.disassociate_route_table 'rtbassoc-d8ccddba'

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        if conn.disassociate_route_table(association_id):
            log.info('Route table with association id {0} has been disassociated.'.format(association_id))
            return {'disassociated': True}
        else:
            log.warning('Route table with association id {0} has not been disassociated.'.format(association_id))
            return {'disassociated': False}
    except BotoServerError as e:
        return {'disassociated': False, 'error': salt.utils.boto.get_error(e)}


def replace_route_table_association(association_id, route_table_id, region=None, key=None, keyid=None, profile=None):
    '''
    Replaces a route table association.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.replace_route_table_association 'rtbassoc-d8ccddba' 'rtb-1f382e7d'

    '''

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        association_id = conn.replace_route_table_association_with_assoc(association_id, route_table_id)
        log.info('Route table {0} was reassociated with association id {1}'.format(route_table_id, association_id))
        return {'replaced': True, 'association_id': association_id}
    except BotoServerError as e:
        return {'replaced': False, 'error': salt.utils.boto.get_error(e)}


def create_route(route_table_id=None, destination_cidr_block=None,
                 route_table_name=None, gateway_id=None,
                 internet_gateway_name=None,
                 instance_id=None, interface_id=None,
                 vpc_peering_connection_id=None, vpc_peering_connection_name=None,
                 region=None, key=None, keyid=None, profile=None,
                 nat_gateway_id=None,
                 nat_gateway_subnet_name=None,
                 nat_gateway_subnet_id=None,
                 ):
    '''
    Creates a route.

    If a nat gateway is specified, boto3 must be installed

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.create_route 'rtb-1f382e7d' '10.0.0.0/16' gateway_id='vgw-a1b2c3'

    '''

    if not _exactly_one((route_table_name, route_table_id)):
        raise SaltInvocationError('One (but not both) of route_table_id or route_table_name '
                                  'must be provided.')

    if not _exactly_one((gateway_id, internet_gateway_name, instance_id, interface_id, vpc_peering_connection_id,
                         interface_id, nat_gateway_id, nat_gateway_subnet_id, nat_gateway_subnet_name)):
        raise SaltInvocationError('Only one of gateway_id, internet_gateway_name, instance_id, '
                                  'interface_id, vpc_peering_connection_id, nat_gateway_id, '
                                  'nat_gateway_subnet_id or nat_gateway_subnet_name may be provided.')

    if destination_cidr_block is None:
        raise SaltInvocationError('destination_cidr_block is required.')

    try:
        if route_table_name:
            route_table_id = _get_resource_id('route_table', route_table_name,
                                              region=region, key=key,
                                              keyid=keyid, profile=profile)
            if not route_table_id:
                return {'created': False,
                        'error': {'message': 'route table {0} does not exist.'.format(route_table_name)}}

        if internet_gateway_name:
            gateway_id = _get_resource_id('internet_gateway', internet_gateway_name,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
            if not gateway_id:
                return {'created': False,
                        'error': {'message': 'internet gateway {0} does not exist.'.format(internet_gateway_name)}}

        if vpc_peering_connection_name:
            vpc_peering_connection_id = _get_resource_id('vpc_peering_connection', vpc_peering_connection_name,
                                                         region=region, key=key,
                                                         keyid=keyid, profile=profile)
            if not vpc_peering_connection_id:
                return {'created': False,
                        'error': {'message': 'VPC peering connection {0} does not exist.'.format(vpc_peering_connection_name)}}

        if nat_gateway_subnet_name:
            gws = describe_nat_gateways(subnet_name=nat_gateway_subnet_name,
                                     region=region, key=key, keyid=keyid, profile=profile)
            if not gws:
                return {'created': False,
                        'error': {'message': 'nat gateway for {0} does not exist.'.format(nat_gateway_subnet_name)}}
            nat_gateway_id = gws[0]['NatGatewayId']

        if nat_gateway_subnet_id:
            gws = describe_nat_gateways(subnet_id=nat_gateway_subnet_id,
                                     region=region, key=key, keyid=keyid, profile=profile)
            if not gws:
                return {'created': False,
                        'error': {'message': 'nat gateway for {0} does not exist.'.format(nat_gateway_subnet_id)}}
            nat_gateway_id = gws[0]['NatGatewayId']

    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}

    if not nat_gateway_id:
        return _create_resource('route', route_table_id=route_table_id,
                            destination_cidr_block=destination_cidr_block,
                            gateway_id=gateway_id, instance_id=instance_id,
                            interface_id=interface_id, vpc_peering_connection_id=vpc_peering_connection_id,
                            region=region, key=key, keyid=keyid, profile=profile)
    # for nat gateway, boto3 is required
    try:
        conn3 = _get_conn3(region=region, key=key, keyid=keyid, profile=profile)
        ret = conn3.create_route(RouteTableId=route_table_id,
                       DestinationCidrBlock=destination_cidr_block,
                       NatGatewayId=nat_gateway_id)
        return {'created': True, 'id': ret.get('NatGatewayId')}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}


def delete_route(route_table_id=None, destination_cidr_block=None,
                 route_table_name=None, region=None, key=None,
                 keyid=None, profile=None):
    '''
    Deletes a route.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.delete_route 'rtb-1f382e7d' '10.0.0.0/16'

    '''

    if not _exactly_one((route_table_name, route_table_id)):
        raise SaltInvocationError('One (but not both) of route_table_id or route_table_name '
                                  'must be provided.')

    if destination_cidr_block is None:
        raise SaltInvocationError('destination_cidr_block is required.')

    try:
        if route_table_name:
            route_table_id = _get_resource_id('route_table', route_table_name,
                                              region=region, key=key,
                                              keyid=keyid, profile=profile)
            if not route_table_id:
                return {'created': False,
                        'error': {'message': 'route table {0} does not exist.'.format(route_table_name)}}
    except BotoServerError as e:
        return {'created': False, 'error': salt.utils.boto.get_error(e)}

    return _delete_resource(resource='route', resource_id=route_table_id,
                            destination_cidr_block=destination_cidr_block,
                            region=region, key=key,
                            keyid=keyid, profile=profile)


def replace_route(route_table_id=None, destination_cidr_block=None,
                  route_table_name=None, gateway_id=None,
                  instance_id=None, interface_id=None,
                  region=None, key=None, keyid=None, profile=None,
                  vpc_peering_connection_id=None):
    '''
    Replaces a route.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.replace_route 'rtb-1f382e7d' '10.0.0.0/16' gateway_id='vgw-a1b2c3'

    '''

    if not _exactly_one((route_table_name, route_table_id)):
        raise SaltInvocationError('One (but not both) of route_table_id or route_table_name '
                                  'must be provided.')

    if destination_cidr_block is None:
        raise SaltInvocationError('destination_cidr_block is required.')

    try:
        if route_table_name:
            route_table_id = _get_resource_id('route_table', route_table_name,
                                              region=region, key=key,
                                              keyid=keyid, profile=profile)
            if not route_table_id:
                return {'replaced': False,
                        'error': {'message': 'route table {0} does not exist.'.format(route_table_name)}}
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

        if conn.replace_route(route_table_id, destination_cidr_block,
                              gateway_id=gateway_id, instance_id=instance_id,
                              interface_id=interface_id, vpc_peering_connection_id=vpc_peering_connection_id):
            log.info('Route with cidr block {0} on route table {1} was '
                     'replaced'.format(route_table_id, destination_cidr_block))
            return {'replaced': True}
        else:
            log.warning('Route with cidr block {0} on route table {1} was not replaced'.format(route_table_id,
                        destination_cidr_block))
            return {'replaced': False}
    except BotoServerError as e:
        return {'replaced': False, 'error': salt.utils.boto.get_error(e)}


def describe_route_table(route_table_id=None, route_table_name=None,
                         tags=None, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Given route table properties, return route table details if matching table(s) exist.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.describe_route_table route_table_id='rtb-1f382e7d'

    '''

    salt.utils.warn_until('Nitrogen',
         'The \'describe_route_table\' method has been deprecated and '
         'replaced by \'describe_route_tables\'.'
    )
    if not any((route_table_id, route_table_name, tags)):
        raise SaltInvocationError('At least one of the following must be specified: '
                                  'route table id, route table name, or tags.')

    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'filters': {}}

        if route_table_id:
            filter_parameters['route_table_ids'] = route_table_id

        if route_table_name:
            filter_parameters['filters']['tag:Name'] = route_table_name

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['filters']['tag:{0}'.format(tag_name)] = tag_value

        route_tables = conn.get_all_route_tables(**filter_parameters)

        if not route_tables:
            return {}

        route_table = {}
        keys = ['id', 'vpc_id', 'tags', 'routes', 'associations']
        route_keys = ['destination_cidr_block', 'gateway_id', 'instance_id', 'interface_id', 'vpc_peering_connection_id']
        assoc_keys = ['id', 'main', 'route_table_id', 'subnet_id']
        for item in route_tables:
            for key in keys:
                if hasattr(item, key):
                    route_table[key] = getattr(item, key)
                    if key == 'routes':
                        route_table[key] = _key_iter(key, route_keys, item)
                    if key == 'associations':
                        route_table[key] = _key_iter(key, assoc_keys, item)
        return route_table

    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def describe_route_tables(route_table_id=None, route_table_name=None,
                         vpc_id=None,
                         tags=None, region=None, key=None, keyid=None,
                         profile=None):
    '''
    Given route table properties, return details of all matching route tables.

    This function requires boto3 to be installed.

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt myminion boto_vpc.describe_route_tables vpc_id='vpc-a6a9efc3'

    '''

    if not any((route_table_id, route_table_name, tags, vpc_id)):
        raise SaltInvocationError('At least one of the following must be specified: '
                                  'route table id, route table name, vpc_id, or tags.')

    try:
        conn3 = _get_conn3(region=region, key=key, keyid=keyid, profile=profile)
        filter_parameters = {'Filters': []}

        if route_table_id:
            filter_parameters['RouteTableIds'] = [route_table_id]

        if vpc_id:
            filter_parameters['Filters'].append({'Name': 'vpc-id', 'Values': [vpc_id]})

        if route_table_name:
            filter_parameters['Filters'].append({'Name': 'tag:Name', 'Values': [route_table_name]})

        if tags:
            for tag_name, tag_value in six.iteritems(tags):
                filter_parameters['Filters'].append({'Name': 'tag:{0}'.format(tag_name),
                                                     'Values': [tag_value]})

        route_tables = conn3.describe_route_tables(**filter_parameters).get('RouteTables', [])

        if not route_tables:
            return []

        tables = []
        keys = {'id': 'RouteTableId',
                'vpc_id': 'VpcId',
                'tags': 'Tags',
                'routes': 'Routes',
                'associations': 'Associations'
            }
        route_keys = {'destination_cidr_block': 'DestinationCidrBlock',
                      'gateway_id': 'GatewayId',
                      'instance_id': 'Instance',
                      'interface_id': 'NetworkInterfaceId',
                      'nat_gateway_id': 'NatGatewayId',
                      }
        assoc_keys = {'id': 'RouteTableAssociationId',
                      'main': 'Main',
                      'route_table_id': 'RouteTableId',
                      'SubnetId': 'subnet_id',
                      }
        for item in route_tables:
            route_table = {}
            for outkey, inkey in keys.iteritems():
                if inkey in item:
                    if outkey == 'routes':
                        route_table[outkey] = _key_remap(inkey, route_keys, item)
                    elif outkey == 'associations':
                        route_table[outkey] = _key_remap(inkey, assoc_keys, item)
                    elif outkey == 'tags':
                        route_table[outkey] = {}
                        for tagitem in item.get(inkey, []):
                            route_table[outkey][tagitem.get('Key')] = tagitem.get('Value')
                    else:
                        route_table[outkey] = item.get(inkey)
            tables.append(route_table)
        return tables

    except BotoServerError as e:
        return {'error': salt.utils.boto.get_error(e)}


def _create_dhcp_options(conn, domain_name=None, domain_name_servers=None, ntp_servers=None, netbios_name_servers=None,
                         netbios_node_type=None):
    return conn.create_dhcp_options(domain_name=domain_name, domain_name_servers=domain_name_servers,
                                    ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                                    netbios_node_type=netbios_node_type)


def _maybe_set_name_tag(name, obj):
    if name:
        obj.add_tag("Name", name)

        log.debug('{0} is now named as {1}'.format(obj, name))


def _maybe_set_tags(tags, obj):
    if tags:
        obj.add_tags(tags)

        log.debug('The following tags: {0} were added to {1}'.format(', '.join(tags), obj))


def _maybe_set_dns(conn, vpcid, dns_support, dns_hostnames):
    if dns_support:
        conn.modify_vpc_attribute(vpc_id=vpcid, enable_dns_support=dns_support)
        log.debug('DNS spport was set to: {0} on vpc {1}'.format(dns_support, vpcid))
    if dns_hostnames:
        conn.modify_vpc_attribute(vpc_id=vpcid, enable_dns_hostnames=dns_hostnames)
        log.debug('DNS hostnames was set to: {0} on vpc {1}'.format(dns_hostnames, vpcid))


def _maybe_name_route_table(conn, vpcid, vpc_name):
    route_tables = conn.get_all_route_tables(filters={'vpc_id': vpcid})
    if not route_tables:
        log.warn('no default route table found')
        return
    default_table = None
    for table in route_tables:
        for association in getattr(table, 'associations', {}):
            if getattr(association, 'main', False):
                default_table = table
                break
    if not default_table:
        log.warn('no default route table found')
        return

    name = '{0}-default-table'.format(vpc_name)
    _maybe_set_name_tag(name, default_table)
    log.debug('Default route table name was set to: {0} on vpc {1}'.format(name, vpcid))


def _key_iter(key, keys, item):
    elements_list = []
    for r_item in getattr(item, key):
        element = {}
        for r_key in keys:
            if hasattr(r_item, r_key):
                element[r_key] = getattr(r_item, r_key)
        elements_list.append(element)
    return elements_list


def _key_remap(key, keys, item):
    elements_list = []
    for r_item in item.get(key, []):
        element = {}
        for r_outkey, r_inkey in keys.iteritems():
            if r_inkey in r_item:
                element[r_outkey] = r_item.get(r_inkey)
        elements_list.append(element)
    return elements_list
