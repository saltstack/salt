# -*- coding: utf-8 -*-
'''
Execution module for Amazon Route53 written against Boto 3

.. versionadded:: 2017.7.0

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

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
          keyid: GKTADJGHEIQSXMKKRBJ08H
          key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
          region: us-east-1

    Note that Route53 essentially ignores all (valid) settings for 'region',
    since there is only one Endpoint (in us-east-1 if you care) and any (valid)
    region setting will just send you there.  It is entirely safe to set it to
    None as well.

:depends: boto3
'''

# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602,W0106

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time

# Import Salt libs
import salt.utils.boto3
import salt.utils.compat
import salt.utils.versions
from salt.exceptions import SaltInvocationError
log = logging.getLogger(__name__)  # pylint: disable=W1699

# Import third party libs
try:
    #pylint: disable=unused-import
    import boto3
    #pylint: enable=unused-import
    from botocore.exceptions import ClientError
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    return salt.utils.versions.check_boto_reqs()


def __init__(opts):
    salt.utils.compat.pack_dunder(__name__)
    if HAS_BOTO3:
        __utils__['boto3.assign_funcs'](__name__, 'route53')


def _collect_results(func, item, args, marker='Marker', nextmarker='NextMarker'):
    ret = []
    Marker = args.get(marker, '')
    tries = 10
    while Marker is not None:
        try:
            r = func(**args)
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                # Rate limited - retry
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Could not collect results from %s(): %s', func, e)
            return []
        i = r.get(item, []) if item else r
        i.pop('ResponseMetadata', None) if isinstance(i, dict) else None
        ret += i if isinstance(i, list) else [i]
        Marker = r.get(nextmarker)
        args.update({marker: Marker})
    return ret


def _wait_for_sync(change, conn, tries=10, sleep=20):
    for retry in range(1, tries+1):
        log.info('Getting route53 status (attempt %s)', retry)
        status = 'wait'
        try:
            status = conn.get_change(Id=change)['ChangeInfo']['Status']
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
            else:
                raise e
        if status == 'INSYNC':
            return True
        time.sleep(sleep)
    log.error('Timed out waiting for Route53 INSYNC status.')
    return False


def find_hosted_zone(Id=None, Name=None, PrivateZone=None,
                     region=None, key=None, keyid=None, profile=None):
    '''
    Find a hosted zone with the given characteristics.

    Id
        The unique Zone Identifier for the Hosted Zone.  Exclusive with Name.

    Name
        The domain name associated with the Hosted Zone.  Exclusive with Id.
        Note this has the potential to match more then one hosted zone (e.g. a public and a private
        if both exist) which will raise an error unless PrivateZone has also been passed in order
        split the different.

    PrivateZone
        Boolean - Set to True if searching for a private hosted zone.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_route53.find_hosted_zone Name=salt.org. \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    '''
    if not _exactly_one((Id, Name)):
        raise SaltInvocationError('Exactly one of either Id or Name is required.')
    if PrivateZone is not None and not isinstance(PrivateZone, bool):
        raise SaltInvocationError('If set, PrivateZone must be a bool (e.g. True / False).')
    if Id:
        ret = get_hosted_zone(Id, region=region, key=key, keyid=keyid, profile=profile)
    else:
        ret = get_hosted_zones_by_domain(Name, region=region, key=key, keyid=keyid, profile=profile)
    if PrivateZone is not None:
        ret = [m for m in ret if m['HostedZone']['Config']['PrivateZone'] is PrivateZone]
    if len(ret) > 1:
        log.error(
            'Request matched more than one Hosted Zone (%s). Refine your '
            'criteria and try again.', [z['HostedZone']['Id'] for z in ret]
        )
        ret = []
    return ret


def get_hosted_zone(Id, region=None, key=None, keyid=None, profile=None):
    '''
    Return detailed info about the given zone.

    Id
        The unique Zone Identifier for the Hosted Zone.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_route53.get_hosted_zone Z1234567690 \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    args = {'Id': Id}
    return _collect_results(conn.get_hosted_zone, None, args)


def get_hosted_zones_by_domain(Name, region=None, key=None, keyid=None, profile=None):
    '''
    Find any zones with the given domain name and return detailed info about them.
    Note that this can return multiple Route53 zones, since a domain name can be used in
    both public and private zones.

    Name
        The domain name associated with the Hosted Zone(s).

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_route53.get_hosted_zones_by_domain salt.org. \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    zones = [z for z in _collect_results(conn.list_hosted_zones, 'HostedZones', {})
            if z['Name'] == Name]
    ret = []
    for z in zones:
        ret += get_hosted_zone(Id=z['Id'], region=region, key=key, keyid=keyid, profile=profile)
    return ret


def list_hosted_zones(DelegationSetId=None, region=None, key=None, keyid=None, profile=None):
    '''
    Return detailed info about all zones in the bound account.

    DelegationSetId
        If you're using reusable delegation sets and you want to list all of the hosted zones that
        are associated with a reusable delegation set, specify the ID of that delegation set.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_route53.describe_hosted_zones \
                profile='{"region": "us-east-1", "keyid": "A12345678AB", "key": "xblahblahblah"}'
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    args = {'DelegationSetId': DelegationSetId} if DelegationSetId else {}
    return _collect_results(conn.list_hosted_zones, 'HostedZones', args)


def create_hosted_zone(Name, VPCId=None, VPCName=None, VPCRegion=None, CallerReference=None,
                       Comment='', PrivateZone=False, DelegationSetId=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Create a new Route53 Hosted Zone. Returns a Python data structure with information about the
    newly created Hosted Zone.

    Name
        The name of the domain. This should be a fully-specified domain, and should terminate with
        a period. This is the name you have registered with your DNS registrar. It is also the name
        you will delegate from your registrar to the Amazon Route 53 delegation servers returned in
        response to this request.

    VPCId
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCName.  Ignored if passed for a non-private zone.

    VPCName
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCId.  Ignored if passed for a non-private zone.

    VPCRegion
        When creating a private hosted zone, the region of the associated VPC is required.  If not
        provided, an effort will be made to determine it from VPCId or VPCName, if possible.  If
        this fails, you'll need to provide an explicit value for this option.  Ignored if passed for
        a non-private zone.

    CallerReference
        A unique string that identifies the request and that allows create_hosted_zone() calls to be
        retried without the risk of executing the operation twice.  This is a required parameter
        when creating new Hosted Zones.  Maximum length of 128.

    Comment
        Any comments you want to include about the hosted zone.

    PrivateZone
        Boolean - Set to True if creating a private hosted zone.

    DelegationSetId
        If you want to associate a reusable delegation set with this hosted zone, the ID that Amazon
        Route 53 assigned to the reusable delegation set when you created it.  Note that XXX TODO
        create_delegation_set() is not yet implemented, so you'd need to manually create any
        delegation sets before utilizing this.

    region
        Region endpoint to connect to.

    key
        AWS key to bind with.

    keyid
        AWS keyid to bind with.

    profile
        Dict, or pillar key pointing to a dict, containing AWS region/key/keyid.

    CLI Example::

        salt myminion boto3_route53.create_hosted_zone example.org.
    '''
    if not Name.endswith('.'):
        raise SaltInvocationError('Domain must be fully-qualified, complete with trailing period.')
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    deets = find_hosted_zone(Name=Name, PrivateZone=PrivateZone,
                             region=region, key=key, keyid=keyid, profile=profile)
    if deets:
        log.info(
            'Route 53 hosted zone %s already exists. You may want to pass '
            'e.g. \'PrivateZone=True\' or similar...', Name
        )
        return None
    args = {
            'Name': Name,
            'CallerReference': CallerReference,
            'HostedZoneConfig': {
              'Comment': Comment,
              'PrivateZone': PrivateZone
            }
          }
    args.update({'DelegationSetId': DelegationSetId}) if DelegationSetId else None
    if PrivateZone:
        if not _exactly_one((VPCName, VPCId)):
            raise SaltInvocationError('Either VPCName or VPCId is required when creating a '
                                      'private zone.')
        vpcs = __salt__['boto_vpc.describe_vpcs'](
                vpc_id=VPCId, name=VPCName, region=region, key=key,
                keyid=keyid, profile=profile).get('vpcs', [])
        if VPCRegion and vpcs:
            vpcs = [v for v in vpcs if v['region'] == VPCRegion]
        if not vpcs:
            log.error('Private zone requested but no VPC matching given criteria found.')
            return None
        if len(vpcs) > 1:
            log.error(
                'Private zone requested but multiple VPCs matching given '
                'criteria found: %s.', [v['id'] for v in vpcs]
            )
            return None
        vpc = vpcs[0]
        if VPCName:
            VPCId = vpc['id']
        if not VPCRegion:
            VPCRegion = vpc['region']
        args.update({'VPC': {'VPCId': VPCId, 'VPCRegion': VPCRegion}})
    else:
        if any((VPCId, VPCName, VPCRegion)):
            log.info('Options VPCId, VPCName, and VPCRegion are ignored when creating '
                     'non-private zones.')
    tries = 10
    while tries:
        try:
            r = conn.create_hosted_zone(**args)
            r.pop('ResponseMetadata', None)
            if _wait_for_sync(r['ChangeInfo']['Id'], conn):
                return [r]
            return []
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Failed to create hosted zone %s: %s', Name, e)
            return []
    return []


def update_hosted_zone_comment(Id=None, Name=None, Comment=None, PrivateZone=None,
                               region=None, key=None, keyid=None, profile=None):
    '''
    Update the comment on an existing Route 53 hosted zone.

    Id
        The unique Zone Identifier for the Hosted Zone.

    Name
        The domain name associated with the Hosted Zone(s).

    Comment
        Any comments you want to include about the hosted zone.

    PrivateZone
        Boolean - Set to True if changing a private hosted zone.

    CLI Example::

        salt myminion boto3_route53.update_hosted_zone_comment Name=example.org. \
                Comment="This is an example comment for an example zone"
    '''
    if not _exactly_one((Id, Name)):
        raise SaltInvocationError('Exactly one of either Id or Name is required.')
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    if Name:
        args = {'Name': Name, 'PrivateZone': PrivateZone, 'region': region,
                'key': key, 'keyid': keyid, 'profile': profile}
        zone = find_hosted_zone(**args)
        if not zone:
            log.error("Couldn't resolve domain name %s to a hosted zone ID.", Name)
            return []
        Id = zone[0]['HostedZone']['Id']
    tries = 10
    while tries:
        try:
            r = conn.update_hosted_zone_comment(Id=Id, Comment=Comment)
            r.pop('ResponseMetadata', None)
            return [r]
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Failed to update comment on hosted zone %s: %s',
                      Name or Id, e)
    return []


def associate_vpc_with_hosted_zone(HostedZoneId=None, Name=None, VPCId=None,
                                   VPCName=None, VPCRegion=None, Comment=None,
                                   region=None, key=None, keyid=None, profile=None):
    '''
    Associates an Amazon VPC with a private hosted zone.

    To perform the association, the VPC and the private hosted zone must already exist. You can't
    convert a public hosted zone into a private hosted zone.  If you want to associate a VPC from
    one AWS account with a zone from a another, the AWS account owning the hosted zone must first
    submit a CreateVPCAssociationAuthorization (using create_vpc_association_authorization() or by
    other means, such as the AWS console).  With that done, the account owning the VPC can then call
    associate_vpc_with_hosted_zone() to create the association.

    Note that if both sides happen to be within the same account, associate_vpc_with_hosted_zone()
    is enough on its own, and there is no need for the CreateVPCAssociationAuthorization step.

    Also note that looking up hosted zones by name (e.g. using the Name parameter) only works
    within a single account - if you're associating a VPC to a zone in a different account, as
    outlined above, you unfortunately MUST use the HostedZoneId parameter exclusively.

    HostedZoneId
        The unique Zone Identifier for the Hosted Zone.

    Name
        The domain name associated with the Hosted Zone(s).

    VPCId
        When working with a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCName.

    VPCName
        When working with a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCId.

    VPCRegion
        When working with a private hosted zone, the region of the associated VPC is required.  If
        not provided, an effort will be made to determine it from VPCId or VPCName, if possible.  If
        this fails, you'll need to provide an explicit value for VPCRegion.

    Comment
        Any comments you want to include about the change being made.

    CLI Example::

        salt myminion boto3_route53.associate_vpc_with_hosted_zone \
                    Name=example.org. VPCName=myVPC \
                    VPCRegion=us-east-1 Comment="Whoo-hoo!  I added another VPC."

    '''
    if not _exactly_one((HostedZoneId, Name)):
        raise SaltInvocationError('Exactly one of either HostedZoneId or Name is required.')
    if not _exactly_one((VPCId, VPCName)):
        raise SaltInvocationError('Exactly one of either VPCId or VPCName is required.')
    if Name:
        # {'PrivateZone': True} because you can only associate VPCs with private hosted zones.
        args = {'Name': Name, 'PrivateZone': True, 'region': region,
                'key': key, 'keyid': keyid, 'profile': profile}
        zone = find_hosted_zone(**args)
        if not zone:
            log.error(
                "Couldn't resolve domain name %s to a private hosted zone ID.",
                Name
            )
            return False
        HostedZoneId = zone[0]['HostedZone']['Id']
    vpcs = __salt__['boto_vpc.describe_vpcs'](vpc_id=VPCId, name=VPCName, region=region, key=key,
                                              keyid=keyid, profile=profile).get('vpcs', [])
    if VPCRegion and vpcs:
        vpcs = [v for v in vpcs if v['region'] == VPCRegion]
    if not vpcs:
        log.error('No VPC matching the given criteria found.')
        return False
    if len(vpcs) > 1:
        log.error('Multiple VPCs matching the given criteria found: %s.',
                  ', '.join([v['id'] for v in vpcs]))
        return False
    vpc = vpcs[0]
    if VPCName:
        VPCId = vpc['id']
    if not VPCRegion:
        VPCRegion = vpc['region']
    args = {'HostedZoneId': HostedZoneId, 'VPC': {'VPCId': VPCId, 'VPCRegion': VPCRegion}}
    args.update({'Comment': Comment}) if Comment is not None else None

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    tries = 10
    while tries:
        try:
            r = conn.associate_vpc_with_hosted_zone(**args)
            return _wait_for_sync(r['ChangeInfo']['Id'], conn)
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Failed to associate VPC %s with hosted zone %s: %s',
                      VPCName or VPCId, Name or HostedZoneId, e)
    return False


def disassociate_vpc_from_hosted_zone(HostedZoneId=None, Name=None, VPCId=None,
                                     VPCName=None, VPCRegion=None, Comment=None,
                                     region=None, key=None, keyid=None, profile=None):
    '''
    Disassociates an Amazon VPC from a private hosted zone.

    You can't disassociate the last VPC from a private hosted zone.  You also can't convert a
    private hosted zone into a public hosted zone.

    Note that looking up hosted zones by name (e.g. using the Name parameter) only works XXX FACTCHECK
    within a single AWS account - if you're disassociating a VPC in one account from a hosted zone
    in a different account you unfortunately MUST use the HostedZoneId parameter exclusively. XXX FIXME DOCU

    HostedZoneId
        The unique Zone Identifier for the Hosted Zone.

    Name
        The domain name associated with the Hosted Zone(s).

    VPCId
        When working with a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCName.

    VPCName
        When working with a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with VPCId.

    VPCRegion
        When working with a private hosted zone, the region of the associated VPC is required.  If
        not provided, an effort will be made to determine it from VPCId or VPCName, if possible.  If
        this fails, you'll need to provide an explicit value for VPCRegion.

    Comment
        Any comments you want to include about the change being made.

    CLI Example::

        salt myminion boto3_route53.disassociate_vpc_from_hosted_zone \
                    Name=example.org. VPCName=myVPC \
                    VPCRegion=us-east-1 Comment="Whoops!  Don't wanna talk to this-here zone no more."

    '''
    if not _exactly_one((HostedZoneId, Name)):
        raise SaltInvocationError('Exactly one of either HostedZoneId or Name is required.')
    if not _exactly_one((VPCId, VPCName)):
        raise SaltInvocationError('Exactly one of either VPCId or VPCName is required.')
    if Name:
        # {'PrivateZone': True} because you can only associate VPCs with private hosted zones.
        args = {'Name': Name, 'PrivateZone': True, 'region': region,
                'key': key, 'keyid': keyid, 'profile': profile}
        zone = find_hosted_zone(**args)
        if not zone:
            log.error("Couldn't resolve domain name %s to a private hosted zone ID.", Name)
            return False
        HostedZoneId = zone[0]['HostedZone']['Id']
    vpcs = __salt__['boto_vpc.describe_vpcs'](vpc_id=VPCId, name=VPCName, region=region, key=key,
                                              keyid=keyid, profile=profile).get('vpcs', [])
    if VPCRegion and vpcs:
        vpcs = [v for v in vpcs if v['region'] == VPCRegion]
    if not vpcs:
        log.error('No VPC matching the given criteria found.')
        return False
    if len(vpcs) > 1:
        log.error('Multiple VPCs matching the given criteria found: %s.',
                  ', '.join([v['id'] for v in vpcs]))
        return False
    vpc = vpcs[0]
    if VPCName:
        VPCId = vpc['id']
    if not VPCRegion:
        VPCRegion = vpc['region']
    args = ({'HostedZoneId': HostedZoneId, 'VPC': {'VPCId': VPCId, 'VPCRegion': VPCRegion}})
    args.update({'Comment': Comment}) if Comment is not None else None

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    tries = 10
    while tries:
        try:
            r = conn.disassociate_vpc_from_hosted_zone(**args)
            return _wait_for_sync(r['ChangeInfo']['Id'], conn)
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Failed to associate VPC %s with hosted zone %s: %s',
                      VPCName or VPCId, Name or HostedZoneId, e)
    return False


#def create_vpc_association_authorization(*args, **kwargs):
#    '''
#    unimplemented
#    '''
#    pass


#def delete_vpc_association_authorization(*args, **kwargs):
#    '''
#    unimplemented
#    '''
#    pass


#def list_vpc_association_authorizations(*args, **kwargs):
#    '''
#    unimplemented
#    '''
#    pass


def delete_hosted_zone(Id, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a Route53 hosted zone.

    CLI Example::

        salt myminion boto3_route53.delete_hosted_zone Z1234567890
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        r = conn.delete_hosted_zone(Id=Id)
        return _wait_for_sync(r['ChangeInfo']['Id'], conn)
    except ClientError as e:
        log.error('Failed to delete hosted zone %s: %s', Id, e)
    return False


def delete_hosted_zone_by_domain(Name, PrivateZone=None, region=None, key=None, keyid=None,
                                 profile=None):
    '''
    Delete a Route53 hosted zone by domain name, and PrivateZone status if provided.

    CLI Example::

        salt myminion boto3_route53.delete_hosted_zone_by_domain example.org.
    '''
    args = {'Name': Name, 'PrivateZone': PrivateZone,
            'region': region, 'key': key, 'keyid': keyid, 'profile': profile}
    # Be extra pedantic in the service of safety - if public/private is not provided and the domain
    # name resolves to both, fail and require them to declare it explicitly.
    zone = find_hosted_zone(**args)
    if not zone:
        log.error("Couldn't resolve domain name %s to a hosted zone ID.", Name)
        return False
    Id = zone[0]['HostedZone']['Id']
    return delete_hosted_zone(Id=Id, region=region, key=key, keyid=keyid, profile=profile)


def get_resource_records(HostedZoneId=None, Name=None, StartRecordName=None,
                         StartRecordType=None, PrivateZone=None,
                         region=None, key=None, keyid=None, profile=None):
    '''
    Get all resource records from a given zone matching the provided StartRecordName (if given) or all
    records in the zone (if not), optionally filtered by a specific StartRecordType.  This will return
    any and all RRs matching, regardless of their special AWS flavors (weighted, geolocation, alias,
    etc.) so your code should be prepared for potentially large numbers of records back from this
    function - for example, if you've created a complex geolocation mapping with lots of entries all
    over the world providing the same server name to many different regional clients.

    If you want EXACTLY ONE record to operate on, you'll need to implement any logic required to
    pick the specific RR you care about from those returned.

    Note that if you pass in Name without providing a value for PrivateZone (either True or
    False), CommandExecutionError can be raised in the case of both public and private zones
    matching the domain. XXX FIXME DOCU

    CLI example::

        salt myminion boto3_route53.get_records test.example.org example.org A
    '''
    if not _exactly_one((HostedZoneId, Name)):
        raise SaltInvocationError('Exactly one of either HostedZoneId or Name must '
                                  'be provided.')
    if Name:
        args = {'Name': Name, 'region': region, 'key': key, 'keyid': keyid,
                'profile': profile}
        args.update({'PrivateZone': PrivateZone}) if PrivateZone is not None else None
        zone = find_hosted_zone(**args)
        if not zone:
            log.error("Couldn't resolve domain name %s to a hosted zone ID.", Name)
            return []
        HostedZoneId = zone[0]['HostedZone']['Id']

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    ret = []
    next_rr_name = StartRecordName
    next_rr_type = StartRecordType
    next_rr_id = None
    done = False
    while True:
        if done:
            return ret
        args = {'HostedZoneId': HostedZoneId}
        args.update({'StartRecordName': next_rr_name}) if next_rr_name else None
        # Grrr, can't specify type unless name is set...  We'll do this via filtering later instead
        args.update({'StartRecordType': next_rr_type}) if next_rr_name and next_rr_type else None
        args.update({'StartRecordIdentifier': next_rr_id}) if next_rr_id else None
        try:
            r = conn.list_resource_record_sets(**args)
            rrs = r['ResourceRecordSets']
            next_rr_name = r.get('NextRecordName')
            next_rr_type = r.get('NextRecordType')
            next_rr_id = r.get('NextRecordIdentifier')
            for rr in rrs:
                if StartRecordName and rr['Name'] != StartRecordName:
                    done = True
                    break
                if StartRecordType and rr['Type'] != StartRecordType:
                    if StartRecordName:
                        done = True
                        break
                    else:
                        # We're filtering by type alone, and there might be more later, so...
                        continue
                ret += [rr]
            if not next_rr_name:
                done = True
        except ClientError as e:
            # Try forever on a simple thing like this...
            if e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                continue
            raise e


def change_resource_record_sets(HostedZoneId=None, Name=None,
                                PrivateZone=None, ChangeBatch=None,
                                region=None, key=None, keyid=None, profile=None):
    '''
    Ugh!!!  Not gonna try to reproduce and validatethis mess in here - just pass what we get to AWS
    and let it decide if it's valid or not...

    See the `AWS Route53 API docs`__ as well as the `Boto3 documentation`__ for all the details...

    .. __: https://docs.aws.amazon.com/Route53/latest/APIReference/API_ChangeResourceRecordSets.html
    .. __: http://boto3.readthedocs.io/en/latest/reference/services/route53.html#Route53.Client.change_resource_record_sets

    The syntax for a ChangeBatch parameter is as follows, but note that the permutations of allowed
    parameters and combinations thereof are quite varied, so perusal of the above linked docs is
    highly recommended for any non-trival configurations.

    .. code-block:: json
    ChangeBatch={
        'Comment': 'string',
        'Changes': [
            {
                'Action': 'CREATE'|'DELETE'|'UPSERT',
                'ResourceRecordSet': {
                    'Name': 'string',
                    'Type': 'SOA'|'A'|'TXT'|'NS'|'CNAME'|'MX'|'NAPTR'|'PTR'|'SRV'|'SPF'|'AAAA',
                    'SetIdentifier': 'string',
                    'Weight': 123,
                    'Region': 'us-east-1'|'us-east-2'|'us-west-1'|'us-west-2'|'ca-central-1'|'eu-west-1'|'eu-west-2'|'eu-central-1'|'ap-southeast-1'|'ap-southeast-2'|'ap-northeast-1'|'ap-northeast-2'|'sa-east-1'|'cn-north-1'|'ap-south-1',
                    'GeoLocation': {
                        'ContinentCode': 'string',
                        'CountryCode': 'string',
                        'SubdivisionCode': 'string'
                    },
                    'Failover': 'PRIMARY'|'SECONDARY',
                    'TTL': 123,
                    'ResourceRecords': [
                        {
                            'Value': 'string'
                        },
                    ],
                    'AliasTarget': {
                        'HostedZoneId': 'string',
                        'DNSName': 'string',
                        'EvaluateTargetHealth': True|False
                    },
                    'HealthCheckId': 'string',
                    'TrafficPolicyInstanceId': 'string'
                }
            },
        ]
    }

    CLI Example:

    .. code-block:: bash

        foo='{
               "Name": "my-cname.example.org.",
               "TTL": 600,
               "Type": "CNAME",
               "ResourceRecords": [
                 {
                   "Value": "my-host.example.org"
                 }
               ]
             }'
        foo=`echo $foo`  # Remove newlines
        salt myminion boto3_route53.change_resource_record_sets DomainName=example.org. \
                keyid=A1234567890ABCDEF123 key=xblahblahblah \
                ChangeBatch="{'Changes': [{'Action': 'UPSERT', 'ResourceRecordSet': $foo}]}"
    '''
    if not _exactly_one((HostedZoneId, Name)):
        raise SaltInvocationError('Exactly one of either HostZoneId or Name must be provided.')
    if Name:
        args = {'Name': Name, 'region': region, 'key': key, 'keyid': keyid,
                'profile': profile}
        args.update({'PrivateZone': PrivateZone}) if PrivateZone is not None else None
        zone = find_hosted_zone(**args)
        if not zone:
            log.error("Couldn't resolve domain name %s to a hosted zone ID.", Name)
            return []
        HostedZoneId = zone[0]['HostedZone']['Id']

    args = {'HostedZoneId': HostedZoneId, 'ChangeBatch': ChangeBatch}
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    tries = 20  # A bit more headroom
    while tries:
        try:
            r = conn.change_resource_record_sets(**args)
            return _wait_for_sync(r['ChangeInfo']['Id'], conn, 30)  # And a little extra time here
        except ClientError as e:
            if tries and e.response.get('Error', {}).get('Code') == 'Throttling':
                log.debug('Throttled by AWS API.')
                time.sleep(3)
                tries -= 1
                continue
            log.error('Failed to apply requested changes to the hosted zone %s: %s',
                      Name or HostedZoneId, e)
    return False
