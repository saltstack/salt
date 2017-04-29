# -*- coding: utf-8 -*-
'''
Tagging module for Amazon AWS Resources

.. versionadded:: Lithium

:configuration: This module accepts explicit AWS credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

        vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
        vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    Or using spefic credentials for the AWS endpoint that is being tagged::

        ec2.keyid: GKTADJGHEIQSXMKKRBJ08H
        ec2.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        vpc.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

    Currently supported resources are:

        security-groups, prefix: 'sg'
        instances, prefix: 'i'
        vpcs, prefix: 'vpc'

    Appropriate AWS Endpoint is automatically detected based on the resource id.

:depends: boto

'''
from __future__ import absolute_import

# Import Python libs
import logging
import json

# Import third party libs
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

try:
    import boto
    import boto.regioninfo
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six import string_types

def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True

def _get_conn(resource_endpoint, region, key, keyid, profile):
    '''
    Get a boto connection to vpc.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']("{0}.region".format(resource_endpoint)):
        region = __salt__['config.option']("{0}.region".format(resource_endpoint))

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']("{0}.key".format(resource_endpoint)):
        key = __salt__['config.option']("{0}.key".format(resource_endpoint))
    if not keyid and __salt__['config.option']("{0}.keyid".format(resource_endpoint)):
        keyid = __salt__['config.option']("{0}.keyid".format(resource_endpoint))

    try:
        # Can't use connect_to_region here without importing modules eg. ec2, vpc
        # inside this function. This trick allows to avoid those imports
        # region_endpoint is a hack, ec2 allows to query the regions for all
        # connections (vpc, sns, etc.)
        try:
            region = [ri for ri in \
            boto.regioninfo.get_regions(resource_endpoint) if ri.name == region][0]
        except boto.exception.BotoClientError:
            region = [ri for ri in \
            boto.regioninfo.get_regions('ec2') if ri.name == region][0]

        log.debug("Connecting to region: {0}".format(region))
        conn = getattr(boto, "connect_{0}".format(resource_endpoint))(aws_access_key_id=keyid,
                                                                      aws_secret_access_key=key,
                                                                      region=region)

    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  "make boto {0} connection.".format(resource_endpoint))
        return None
    return conn

def _get_resource(resource_id, region, key, keyid, profile):
    '''
    Get resource for tagging based on the collected attribtues
    '''
    resource_attr = _recognize_resource(resource_id)
    if resource_attr:
        conn = _get_conn(resource_endpoint=resource_attr['endpoint'],
                         region=region,
                         key=key,
                         keyid=keyid,
                         profile=profile)
        if conn:
            try:
                filters = {resource_attr['filter']:[resource_id]}
                resource = getattr(conn, resource_attr['accessor'])(**filters)
                if resource:
                    return resource.pop()
            except boto.exception.BotoServerError as exc:
                log.error(exc)
    else:
        raise CommandExecutionError("Resource id: {0} could not be recognized.".format(resource_id))
    return None

def _recognize_resource(resource_id=None):
    '''
    Get metadata about the resource for tagging
    '''
    resource_prefix = resource_id.split('-')[0]
    log.debug("Detected resource prefix: {0}".format(resource_prefix))
    resource_map = dict(sg=dict(endpoint='ec2',
                                family='instances',
                                filter='group_ids',
                                accessor='get_all_security_groups'),
                        vpc=dict(endpoint='vpc',
                                 family='vpcs',
                                 filter='vpc_ids',
                                 accessor='get_all_vpcs'),
                        i=dict(endpoint='ec2',
                               family='instances',
                               filter='instance_ids',
                               accessor='get_only_instances'))
    resource_attr = resource_map.get(resource_prefix, None)
    log.debug("Recognized resource details: {0}".format(resource_attr))
    return resource_attr


def _parse_arg_tags(tags=None):
    '''
    Convert passed string representing dict into dict obj
    '''
    ret = False
    log.debug("Parsing tags: {0}".format(tags))
    try:
        ret = json.loads(tags)
    except TypeError:
        log.warning('Could not decode passed tags as dict')
    return ret


def _is_subset(superset=None, subset=None):
    '''
    Compares dictionaries against inclusion
    '''
    return set(subset.items()).issubset(set(superset.items()))


def add(resource_id, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Adds tags to the resource_id of type resource

    CLI Example::

    .. code-block:: bash

        salt myminion boto_tag.add 'vpc-6b1fe401' tags='{"environment":"development"}'

    .. code-block:: bash

        salt myminion boto_tag.add 'sg-1b1f1112' tags='{"environment":"development"}'

    .. code-block:: bash

        salt myminion boto_tag.add 'i-7b1fe401' tags='{"environment":"development"}'

    '''
    ret = False
    resource = _get_resource(resource_id=resource_id,
                             region=region,
                             key=key,
                             keyid=keyid,
                             profile=profile)
    try:
        if resource:
            log.debug("Adding tags: {1} to {0}".format(resource.id, tags))
            resource.add_tags(tags)
            log.debug("Current Resource tags: {0}".format(resource.tags))
            ret = _is_subset(superset=resource.tags, subset=tags)
        else:
            log.warning("Failed to add tags: {1} to {0}".format(resource_id, tags))
    except boto.exception.BotoServerError as exc:
        log.error(exc)
    return ret


def remove(resource_id, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Adds tags to the resource_id of type resource

    CLI Example::

    .. code-block:: bash

        salt myminion boto_tag.remove 'vpc-6b1fe401' tags='{"environment":"development"}'

    .. code-block:: bash

        salt myminion boto_tag.remove 'sg-1b1f1112' tags='{"environment":"development"}'

    .. code-block:: bash

        salt myminion boto_tag.remove 'i-7b1fe401' tags='{"environment":"development"}'

    '''
    ret = False
    resource = _get_resource(resource_id=resource_id,
                             region=region,
                             key=key,
                             keyid=keyid,
                             profile=profile)
    try:
        if resource:
            log.debug("Removing tags: {1} to {0}".format(resource.id, tags))
            resource.remove_tags(tags)
            log.debug("Current resource tags: {0}".format(resource.tags))
            ret = not _is_subset(superset=resource.tags, subset=tags)
        else:
            log.warning("Failed to remove tags: {1} to {0}".format(resource_id, tags))
    except boto.exception.BotoServerError as exc:
        log.error(exc)
    return ret



