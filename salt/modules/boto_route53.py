# -*- coding: utf-8 -*-
'''
Connection module for Amazon Route53

.. versionadded:: 2014.7.0

:configuration: This module accepts explicit route53 credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
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
from salt.exceptions import SaltInvocationError
from salt.utils.versions import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
REQUIRED_BOTO_VERSION = '2.35.0'
try:
    #pylint: disable=unused-import
    import boto
    import boto.route53
    from boto.route53.exception import DNSServerError
    #pylint: enable=unused-import
    # create_zone params were changed in boto 2.35+
    if _LooseVersion(boto.__version__) < _LooseVersion(REQUIRED_BOTO_VERSION):
        raise ImportError()
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        msg = ('A boto library with version at least {0} was not '
               'found').format(REQUIRED_BOTO_VERSION)
        return (False, msg)
    return True


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO:
        __utils__['boto.assign_funcs'](__name__, 'route53', pack=__salt__)


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


def describe_hosted_zones(zone_id=None, domain_name=None, region=None,
                          key=None, keyid=None, profile=None):
    '''
    Return detailed info about one, or all, zones in the bound account.
    If neither zone_id nor domain_name is provided, return all zones.
    Note that the return format is slightly different between the 'all'
    and 'single' description types.

    zone_id
        The unique identifier for the Hosted Zone

    domain_name
        The FQDN of the Hosted Zone (including final period)

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.describe_hosted_zones domain_name=foo.bar.com. \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if zone_id and domain_name:
        raise SaltInvocationError('At most one of zone_id or domain_name may '
                                  'be provided')
    retries = 10
    while retries:
        try:
            if zone_id:
                zone_id = zone_id.replace('/hostedzone/',
                        '') if zone_id.startswith('/hostedzone/') else zone_id
                ret = getattr(conn.get_hosted_zone(zone_id),
                              'GetHostedZoneResponse', None)
            elif domain_name:
                ret = getattr(conn.get_hosted_zone_by_name(domain_name),
                              'GetHostedZoneResponse', None)
            else:
                marker = None
                ret = None
                while marker is not '':
                    r = conn.get_all_hosted_zones(start_marker=marker,
                                                  zone_list=ret)
                    ret = r['ListHostedZonesResponse']['HostedZones']
                    marker = r['ListHostedZonesResponse'].get('NextMarker', '')
            return ret if ret else []
        except DNSServerError as e:
            # if rate limit, retry:
            if retries and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Could not list zones: {0}'.format(e.message))
            return []


def list_all_zones_by_name(region=None, key=None, keyid=None, profile=None):
    '''
    List, by their FQDNs, all hosted zones in the bound account.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.list_all_zones_by_name
    '''
    ret = describe_hosted_zones(region=region, key=key, keyid=keyid,
                                profile=profile)
    return [r['Name'] for r in ret]


def list_all_zones_by_id(region=None, key=None, keyid=None, profile=None):
    '''
    List, by their IDs, all hosted zones in the bound account.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_route53.list_all_zones_by_id
    '''
    ret = describe_hosted_zones(region=region, key=key, keyid=keyid,
                                profile=profile)
    return [r['Id'].replace('/hostedzone/', '') for r in ret]


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

    zone
        DNS zone to create

    private
        True/False if the zone will be a private zone

    vpc_id
        VPC ID to associate the zone to (required if private is True)

    vpc_region
        VPC Region (required if private is True)

    region
        region endpoint to connect to

    key
        AWS key

    keyid
        AWS keyid

    profile
        AWS pillar profile

    CLI Example::

        salt myminion boto_route53.create_zone example.org
    '''
    if region is None:
        region = 'universal'

    if private:
        if not vpc_id or not vpc_region:
            msg = 'vpc_id and vpc_region must be specified for a private zone'
            raise SaltInvocationError(msg)

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    _zone = conn.get_zone(zone)

    if _zone:
        return False

    conn.create_zone(zone, private_zone=private, vpc_id=vpc_id,
                     vpc_region=vpc_region)
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
               identifier=None, retry_on_rate_limit=True, rate_limit_retries=5):
    '''
    Get a record from a zone.

    CLI example::

        salt myminion boto_route53.get_record test.example.org example.org A
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
        ret['name'] = _decode_name(_record.name)
        ret['value'] = _record.resource_records[0]
        ret['record_type'] = _record.type
        ret['ttl'] = _record.ttl
        if _record.identifier:
            ret['identifier'] = []
            ret['identifier'].append(_record.identifier)
            ret['identifier'].append(_record.weight)

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
                  retry_on_rate_limit=True, rate_limit_retries=5):
    '''
    Modify a record in a zone.

    CLI example::

        salt myminion boto_route53.modify_record test.example.org 1.1.1.1 example.org A
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

    _value = _munge_value(value, _type)
    while rate_limit_retries > 0:
        try:
            old_record = _zone.find_records(name, _type, identifier=identifier)
            if not old_record:
                return False
            status = _zone.update_record(old_record, _value, ttl, identifier)
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


def create_hosted_zone(domain_name, caller_ref=None, comment='',
                       private_zone=False, vpc_id=None, vpc_name=None,
                       vpc_region=None, region=None, key=None, keyid=None,
                       profile=None):
    '''
    Create a new Route53 Hosted Zone. Returns a Python data structure with
    information about the newly created Hosted Zone.

    domain_name
        The name of the domain. This should be a fully-specified domain, and
        should terminate with a period. This is the name you have registered
        with your DNS registrar. It is also the name you will delegate from your
        registrar to the Amazon Route 53 delegation servers returned in response
        to this request.

    caller_ref
        A unique string that identifies the request and that allows
        create_hosted_zone() calls to be retried without the risk of executing
        the operation twice.  You want to provide this where possible, since
        additional calls while the first is in PENDING status will be accepted
        and can lead to multiple copies of the zone being created in Route53.

    comment
        Any comments you want to include about the hosted zone.

    private_zone
        Set True if creating a private hosted zone.

    vpc_id
        When creating a private hosted zone, either the VPC ID or VPC Name to
        associate with is required.  Exclusive with vpe_name.  Ignored if passed
        for a non-private zone.

    vpc_name
        When creating a private hosted zone, either the VPC ID or VPC Name to
        associate with is required.  Exclusive with vpe_id.  Ignored if passed
        for a non-private zone.

    vpc_region
        When creating a private hosted zone, the region of the associated VPC is
        required.  If not provided, an effort will be made to determine it from
        vpc_id or vpc_name, if possible.  If this fails, you'll need to provide
        an explicit value for this option.  Ignored if passed for a non-private
        zone.

    region
        Region endpoint to connect to

    key
        AWS key to bind with

    keyid
        AWS keyid to bind with

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid

    CLI Example::

        salt myminion boto_route53.create_hosted_zone example.org
    '''
    if region is None:
        region = 'universal'

    if not domain_name.endswith('.'):
        raise SaltInvocationError('Domain MUST be fully-qualified, complete '
                                  'with ending period.')

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    deets = conn.get_hosted_zone_by_name(domain_name)
    if deets:
        log.info('Route53 hosted zone {0} already exists'.format(domain_name))
        return None

    args = {'domain_name': domain_name,
            'caller_ref': caller_ref,
            'comment': comment,
            'private_zone': private_zone}

    if private_zone:
        if not _exactly_one((vpc_name, vpc_id)):
            raise SaltInvocationError('Either vpc_name or vpc_id is required '
                                      'when creating a private zone.')
        vpcs = __salt__['boto_vpc.describe_vpcs'](
                vpc_id=vpc_id, name=vpc_name, region=region, key=key,
                keyid=keyid, profile=profile).get('vpcs', [])
        if vpc_region and vpcs:
            vpcs = [v for v in vpcs if v['region'] == vpc_region]
        if not vpcs:
            log.error('Private zone requested but a VPC matching given criteria'
                      ' not found.')
            return None
        if len(vpcs) > 1:
            log.error('Private zone requested but multiple VPCs matching given '
                      'criteria found: {0}.'.format([v['id'] for v in vpcs]))
            return None
        vpc = vpcs[0]
        if vpc_name:
            vpc_id = vpc['id']
        if not vpc_region:
            vpc_region = vpc['region']
        args.update({'vpc_id': vpc_id, 'vpc_region': vpc_region})
    else:
        if any((vpc_id, vpc_name, vpc_region)):
            log.info('Options vpc_id, vpc_name, and vpc_region are ignored '
                     'when creating non-private zones.')

    retries = 10
    while retries:
        try:
            # Crazy layers of dereference...
            r = conn.create_hosted_zone(**args)
            r = r.CreateHostedZoneResponse.__dict__ if hasattr(r,
                    'CreateHostedZoneResponse') else {}
            return r.get('parent', {}).get('CreateHostedZoneResponse')
        except DNSServerError as e:
            if retries and 'Throttling' == e.code:
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                retries -= 1
                continue
            log.error('Failed to create hosted zone {0}: {1}'.format(
                    domain_name, e.message))
            return None
