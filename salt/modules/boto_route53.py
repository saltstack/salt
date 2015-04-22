# -*- coding: utf-8 -*-
'''
Connection module for Amazon Route53

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit route53 credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        route53.keyid: GKTADJGHEIQSXMKKRBJ08H
        route53.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        route53.region: us-east-1

    If a region is not specified, the default is us-east-1.

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
import time

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.route53
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six import string_types
import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def _is_valid_resource(_type):
    if _type in ('A', 'CNAME', 'MX'):
        return True
    else:
        log.error('{0} is an unsupported resource type.'.format(_type))
        return False


def get_record(name, zone, record_type, fetch_all=False, region=None, key=None,
               keyid=None, profile=None):
    '''
    Get a record from a zone.

    CLI example::

        salt myminion boto_route53.get_record test.example.org example.org A
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return None
    _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return None
    _type = record_type.upper()
    ret = odict.OrderedDict()

    if not _is_valid_resource(_type):
        return None

    if _type == 'A':
        _record = _zone.get_a(name, fetch_all)
    elif _type == 'CNAME':
        _record = _zone.get_cname(name, fetch_all)
    elif _type == 'MX':
        _record = _zone.get_mx(name, fetch_all)

    if _record:
        ret['name'] = _record.name
        ret['value'] = _record.to_print()
        ret['record_type'] = _record.type
        ret['ttl'] = _record.ttl

    return ret


def add_record(name, value, zone, record_type, identifier=None, ttl=None,
               region=None, key=None, keyid=None, profile=None, sync_wait=False):
    '''
    Add a record to a zone.

    CLI example::

        salt myminion boto_route53.add_record test.example.org 1.1.1.1 example.org A
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return False
    _type = record_type.upper()

    if not _is_valid_resource(_type):
        return False

    if _type == 'A':
        status = _zone.add_a(name, value, ttl, identifier)
    elif _type == 'CNAME':
        status = _zone.add_cname(name, value, ttl, identifier)
    elif _type == 'MX':
        status = _zone.add_mx(name, value, ttl, identifier)

    if sync_wait:
        if _wait_for_sync(status.id, conn):
            return True
        else:
            log.error('Failed to add route53 record {0}.'.format(name))
            return False
    else:
        return True


def update_record(name, value, zone, record_type, identifier=None, ttl=None,
                  region=None, key=None, keyid=None, profile=None, sync_wait=False):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.modify_record test.example.org 1.1.1.1 example.org A
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return False
    _type = record_type.upper()

    if not _is_valid_resource(_type):
        return False

    if _type == 'A':
        status = _zone.update_a(name, value, ttl, identifier)
    elif _type == 'CNAME':
        status = _zone.update_cname(name, value, ttl, identifier)
    elif _type == 'MX':
        status = _zone.update_mx(name, value, ttl, identifier)

    if sync_wait:
        if _wait_for_sync(status.id, conn):
            return True
        else:
            log.error('Failed to update route53 record {0}.'.format(name))
            return False
    else:
        return True


def delete_record(name, zone, record_type, identifier=None, all_records=False,
                  region=None, key=None, keyid=None, profile=None, sync_wait=False):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.delete_record test.example.org example.org A
    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return False
    _type = record_type.upper()

    if not _is_valid_resource(_type):
        return False

    if _type == 'A':
        status = _zone.delete_a(name, identifier, all_records)
    elif _type == 'CNAME':
        status = _zone.delete_cname(name, identifier, all_records)
    elif _type == 'MX':
        status = _zone.delete_mx(name, identifier, all_records)

    if sync_wait:
        if _wait_for_sync(status.id, conn):
            return True
        else:
            log.error('Failed to delete route53 record {0}.'.format(name))
            return False
    else:
        return True


def _wait_for_sync(status, conn):
    retry = 10
    i = 0
    while i < retry:
        log.info('Getting route53 status (attempt {0})'.format(i + 1))
        change = conn.get_change(status)
        log.debug(change.GetChangeResponse.ChangeInfo.Status)
        if change.GetChangeResponse.ChangeInfo.Status == 'INSYNC':
            return True
        i = i + 1
        time.sleep(20)
    log.error('Timed out waiting for Route53 status update.')
    return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to Route53.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('route53.region'):
        region = __salt__['config.option']('route53.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('route53.key'):
        key = __salt__['config.option']('route53.key')
    if not keyid and __salt__['config.option']('route53.keyid'):
        keyid = __salt__['config.option']('route53.keyid')

    try:
        conn = boto.route53.connect_to_region(region, aws_access_key_id=keyid,
                                              aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto route53 connection.')
        return None
    return conn
