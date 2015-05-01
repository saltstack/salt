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
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

# Import Python libs
import logging
import time

log = logging.getLogger(__name__)

# Import third party libs
try:
    #pylint: disable=unused-import
    import boto
    import boto.route53
    #pylint: enable=unused-import
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

import salt.utils.odict as odict


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    __utils__['boto.assign_funcs'](__name__, 'route53')
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
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
               region=None, key=None, keyid=None, profile=None,
               wait_for_sync=True):
    '''
    Add a record to a zone.

    CLI example::

        salt myminion boto_route53.add_record test.example.org 1.1.1.1 example.org A
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'CNAME':
        status = _zone.add_cname(name, value, ttl, identifier)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'MX':
        status = _zone.add_mx(name, value, ttl, identifier)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    else:
        return True


def update_record(name, value, zone, record_type, identifier=None, ttl=None,
                  region=None, key=None, keyid=None, profile=None,
                  wait_for_sync=True):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.modify_record test.example.org 1.1.1.1 example.org A
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'CNAME':
        status = _zone.update_cname(name, value, ttl, identifier)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'MX':
        status = _zone.update_mx(name, value, ttl, identifier)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    else:
        return True


def delete_record(name, zone, record_type, identifier=None, all_records=False,
                  region=None, key=None, keyid=None, profile=None,
                  wait_for_sync=True):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.delete_record test.example.org example.org A
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

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
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'CNAME':
        status = _zone.delete_cname(name, identifier, all_records)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    elif _type == 'MX':
        status = _zone.delete_mx(name, identifier, all_records)
        return _wait_for_sync(status.id, conn, wait_for_sync)
    else:
        return True


def _wait_for_sync(status, conn, wait_for_sync):
    if not wait_for_sync:
        return True
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
