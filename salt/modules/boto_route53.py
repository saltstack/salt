# -*- coding: utf-8 -*-
'''
Connection module for Amazon Route53

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit route53 credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: yaml

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        route53.keyid: GKTADJGHEIQSXMKKRBJ08H
        route53.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        route53.region: us-east-1

    If a region is not specified, the default is 'universal', which is what the boto_route53
    library expects, rather than None.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

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

# Import salt libs
import salt.utils.compat
import salt.utils.odict as odict

log = logging.getLogger(__name__)

# Import third party libs
try:
    #pylint: disable=unused-import
    import boto
    import boto.route53
    from boto.route53.exception import DNSServerError
    #pylint: enable=unused-import
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto.assign_funcs'](__name__, 'route53')


def _get_split_zone(zone, _conn, private_zone):
    '''
    With boto route53, zones can only be matched by name
    or iterated over in a list.  Since the name will be the
    same for public and private zones in a split DNS situation,
    iterate over the list and match the zone name and public/private
    status.
    '''
    for _zone in _conn.get_zones():
        if _zone.name == zone:
            _private_zone = True if _zone.config['PrivateZone'].lower() == 'true' else False
            if _private_zone == private_zone:
                return _zone
    return False


def zone_exists(zone, region=None, key=None, keyid=None, profile=None,
                retry_on_rate_limit=True, rate_limit_retries=5):
    '''
    Check for the existence of a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    CLI Example::

        salt myminion boto_route53.zone_exists example.org
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    while rate_limit_retries > 0:
        try:
            return bool(conn.get_zone(zone))

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e


def create_zone(zone, private=False, vpc_id=None, vpc_region=None, region=None,
                key=None, keyid=None, profile=None):
    '''
    Create a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    CLI Example::

        salt myminion boto_route53.create_zone example.org
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _zone = conn.get_zone(zone, private_zone=private, vpc_id=vpc_id,
                          vpc_region=vpc_region)

    if _zone:
        return False

    conn.create_zone(zone)
    return True


def delete_zone(zone, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a Route53 hosted zone.

    .. versionadded:: 2015.8.0

    CLI Example::

        salt myminion boto_route53.delete_zone example.org
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _zone = conn.get_zone(zone)

    if _zone:
        conn.delete_hosted_zone(_zone.id)
        return True
    return False


def _encode_name(name):
    return name.replace('*', r'\052')


def _decode_name(name):
    return name.replace(r'\052', '*')


def get_record(name, zone, record_type, fetch_all=False, region=None, key=None,
               keyid=None, profile=None, split_dns=False, private_zone=False,
               retry_on_rate_limit=True, rate_limit_retries=5, identifier=None):
    '''
    Get a record from a zone.

    CLI example::

        salt myminion boto_route53.get_record test.example.org example.org A
    '''
    if region is None:
        region = 'universal'
    if identifier:
        identifier = [str(x) for x in identifier]

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    while rate_limit_retries > 0:
        try:
            if split_dns:
                _zone = _get_split_zone(zone, conn, private_zone)
            else:
                _zone = conn.get_zone(zone)
            if not _zone:
                msg = 'Failed to retrieve zone {0}'.format(zone)
                log.error(msg)
                return None
            _type = record_type.upper()
            ret = odict.OrderedDict()

            name = _encode_name(name)
            _record = _zone.find_records(name, _type, all=fetch_all, identifier=identifier)
            break  # the while True

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e

    if _record:
        ret = {}
        if isinstance(_record, list):
            ret = []
            for this_record in _record:
                tret = {}
                tret['name'] = _decode_name(this_record.name)
                tret['record_type'] = this_record.type
                tret['ttl'] = this_record.ttl
                if this_record.weight:
                    tret['identifier'] = [this_record.identifier, this_record.weight]
                elif this_record.region:
                    tret['identifier'] = [this_record.identifier, this_record.region]
                if this_record.resource_records:
                    tret['value'] = ','.join(this_record.resource_records)
                ret.append(tret)
        else:
            ret['name'] = _decode_name(_record.name)
            ret['record_type'] = _record.type
            ret['ttl'] = _record.ttl
            if _record.weight:
                ret['identifier'] = [_record.identifier, _record.weight]
            elif _record.region:
                ret['identifier'] = [_record.identifier, _record.region]
            if _record.resource_records:
                ret['value'] = ','.join(_record.resource_records)

    return ret


def _munge_value(value, _type):
    split_types = ['A', 'MX', 'AAAA', 'TXT', 'SRV', 'SPF', 'NS']
    if _type in split_types:
        return value.split(',')
    return value


def add_record(name, value, zone, record_type, identifier=None, ttl=None,
               region=None, key=None, keyid=None, profile=None,
               wait_for_sync=True, split_dns=False, private_zone=False,
               retry_on_rate_limit=True, rate_limit_retries=5):
    '''
    Add a record to a zone.

    CLI example::

        salt myminion boto_route53.add_record test.example.org 1.1.1.1 example.org A
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    while rate_limit_retries > 0:
        try:
            if split_dns:
                _zone = _get_split_zone(zone, conn, private_zone)
            else:
                _zone = conn.get_zone(zone)
            if not _zone:
                msg = 'Failed to retrieve zone {0}'.format(zone)
                log.error(msg)
                return False
            _type = record_type.upper()
            break

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e

    _value = _munge_value(value, _type)
    while rate_limit_retries > 0:
        try:
            if _type == 'A':
                status = _zone.add_a(name, _value, ttl, identifier)
                return _wait_for_sync(status.id, conn, wait_for_sync)
            elif _type == 'CNAME':
                status = _zone.add_cname(name, _value, ttl, identifier)
                return _wait_for_sync(status.id, conn, wait_for_sync)
            elif _type == 'MX':
                status = _zone.add_mx(name, _value, ttl, identifier)
                return _wait_for_sync(status.id, conn, wait_for_sync)
            else:
                # add_record requires a ttl value, annoyingly.
                if ttl is None:
                    ttl = 60
                status = _zone.add_record(_type, name, _value, ttl, identifier)
                return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e


def update_record(name, value, zone, record_type, identifier=None, ttl=None,
                  region=None, key=None, keyid=None, profile=None,
                  wait_for_sync=True, split_dns=False, private_zone=False,
                  retry_on_rate_limit=True, rate_limit_retries=5, new_identifier=None):
    '''
    Modify a record in a zone.

    name
        the name of the record to update

    value
        the new value to set for the record

    record_type
        the type of record to update (i.e. A, MX, CNAME, etc)

    identifier
        record set policy identifer
            for a weighted policy record ['unique id', 'weight']
            for a latency policy record ['unique id', 'region']

    ttl
        the new ttl for the record

    region
        the amazon region

    key
        secret key

    keyid
        key id

    wait_for_sync
        wait for the record to sync before returning

    split_dns

    private_zone

    retry_on_rate_limit

    rate_limit_retries=5

    new_identifier
        the new record set policy identifier
            weighted policy records ['unique id', 'weight']
            latency policy records ['unique id', 'region']

    CLI example::

        salt myminion boto_route53.update_record test.example.org 1.1.1.1 example.org A
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if split_dns:
        _zone = _get_split_zone(zone, conn, private_zone)
    else:
        _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return False
    _type = record_type.upper()

    if not new_identifier:
        new_identifier = identifier
    if identifier:
        identifier = [str(x) for x in identifier]
    _value = _munge_value(value, _type)
    while rate_limit_retries > 0:
        try:
            old_record = _zone.find_records(name, _type, identifier=identifier)
            log.debug('old_record = {0}'.format(old_record))
            if not old_record:
                return False
            status = _zone.update_record(old_record, _value, ttl, new_identifier)
            return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e


def delete_record(name, zone, record_type, identifier=None, all_records=False,
                  region=None, key=None, keyid=None, profile=None,
                  wait_for_sync=True, split_dns=False, private_zone=False,
                  retry_on_rate_limit=True, rate_limit_retries=5):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.delete_record test.example.org example.org A
    '''
    if region is None:
        region = 'universal'

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    if split_dns:
        _zone = _get_split_zone(zone, conn, private_zone)
    else:
        _zone = conn.get_zone(zone)
    if not _zone:
        msg = 'Failed to retrieve zone {0}'.format(zone)
        log.error(msg)
        return False
    _type = record_type.upper()
    if identifier:
        identifier = [str(x) for x in identifier]

    while rate_limit_retries > 0:
        try:
            old_record = _zone.find_records(name, _type, all=all_records, identifier=identifier)
            if not old_record:
                return False
            status = _zone.delete_record(old_record)
            return _wait_for_sync(status.id, conn, wait_for_sync)

        except DNSServerError as e:
            # if rate limit, retry:
            if retry_on_rate_limit and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(2)
                rate_limit_retries -= 1
                continue  # the while True; try again if not out of retries
            raise e


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
