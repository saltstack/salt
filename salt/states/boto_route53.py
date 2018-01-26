# -*- coding: utf-8 -*-
'''
Manage Route53 records

.. versionadded:: 2014.7.0

Create and delete Route53 records. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit route53 credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    route53.keyid: GKTADJGHEIQSXMKKRBJ08H
    route53.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
      keyid: GKTADJGHEIQSXMKKRBJ08H
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      region: us-east-1

.. code-block:: yaml

    mycnamerecord:
      boto_route53.present:
        - name: test.example.com.
        - value: my-elb.us-east-1.elb.amazonaws.com.
        - zone: example.com.
        - ttl: 60
        - record_type: CNAME
        - region: us-east-1
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars
    myarecord:
      boto_route53.present:
        - name: test.example.com.
        - value: 1.1.1.1
        - zone: example.com.
        - ttl: 60
        - record_type: A
        - region: us-east-1
        - profile: myprofile

    # Passing in a profile
    myarecord:
      boto_route53.present:
        - name: test.example.com.
        - value: 1.1.1.1
        - zone: example.com.
        - ttl: 60
        - record_type: A
        - region: us-east-1
        - profile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import uuid

# Import Salt Libs
import salt.utils.data
import salt.utils.json
from salt.ext import six
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_route53' if 'boto_route53.get_record' in __salt__ else False


def rr_present(*args, **kwargs):
    return present(*args, **kwargs)


def present(name, value, zone, record_type, ttl=None, identifier=None, region=None, key=None,
            keyid=None, profile=None, wait_for_sync=True, split_dns=False, private_zone=False):
    '''
    Ensure the Route53 record is present.

    name
        Name of the record.

    value
        Value of the record.  As a special case, you can pass in:
            `private:<Name tag>` to have the function autodetermine the private IP
            `public:<Name tag>` to have the function autodetermine the public IP

    zone
        The zone to create the record in.

    record_type
        The record type (A, NS, MX, TXT, etc.)

    ttl
        The time to live for the record.

    identifier
        The unique identifier to use for this record.

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that contains a dict
        with region, key and keyid.

    wait_for_sync
        Wait for an INSYNC change status from Route53 before returning success.

    split_dns
        Route53 supports parallel public and private DNS zones with the same name.

    private_zone
        If using split_dns, specify if this is the private zone.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # If a list is passed in for value, change it to a comma-separated string
    # So it will work with subsequent boto module calls and string functions
    if isinstance(value, list):
        value = ','.join(value)
    elif value.startswith('private:') or value.startswith('public:'):
        name_tag = value.split(':', 1)[1]
        in_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')
        r = __salt__['boto_ec2.find_instances'](name=name_tag,
                                                return_objs=True,
                                                in_states=in_states,
                                                profile=profile)
        if len(r) < 1:
            ret['comment'] = 'Error: instance with Name tag {0} not found'.format(name_tag)
            ret['result'] = False
            return ret
        if len(r) > 1:
            ret['comment'] = 'Error: Name tag {0} matched more than one instance'.format(name_tag)
            ret['result'] = False
            return ret
        instance = r[0]
        private_ip = getattr(instance, 'private_ip_address', None)
        public_ip = getattr(instance, 'ip_address', None)
        if value.startswith('private:'):
            value = private_ip
            log.info('Found private IP %s for instance %s', private_ip, name_tag)
        else:
            if public_ip is None:
                ret['comment'] = 'Error: No Public IP assigned to instance with Name {0}'.format(name_tag)
                ret['result'] = False
                return ret
            value = public_ip
            log.info('Found public IP %s for instance %s', public_ip, name_tag)

    try:
        record = __salt__['boto_route53.get_record'](name, zone, record_type,
                                                     False, region, key, keyid,
                                                     profile, split_dns,
                                                     private_zone, identifier)
    except SaltInvocationError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        ret['result'] = False
        return ret

    if isinstance(record, dict) and not record:
        if __opts__['test']:
            ret['comment'] = 'Route53 record {0} set to be added.'.format(name)
            ret['result'] = None
            return ret
        added = __salt__['boto_route53.add_record'](name, value, zone,
                                                    record_type, identifier,
                                                    ttl, region, key, keyid,
                                                    profile, wait_for_sync,
                                                    split_dns, private_zone)
        if added:
            ret['changes']['old'] = None
            ret['changes']['new'] = {'name': name,
                                     'value': value,
                                     'record_type': record_type,
                                     'ttl': ttl,
                                     'identifier': identifier}
            ret['comment'] = 'Added {0} Route53 record.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to add {0} Route53 record.'.format(name)
            return ret
    elif record:
        need_to_update = False
        # Values can be a comma separated list and some values will end with a
        # period (even if we set it without one). To easily check this we need
        # to split and check with the period stripped from the input and what's
        # in route53.
        # TODO: figure out if this will cause us problems with some records.
        _values = [x.rstrip('.') for x in value.split(',')]
        _r_values = [x.rstrip('.') for x in record['value'].split(',')]
        _values.sort()
        _r_values.sort()
        if _values != _r_values:
            need_to_update = True
        if identifier and identifier != record['identifier']:
            need_to_update = True
        if ttl and six.text_type(ttl) != six.text_type(record['ttl']):
            need_to_update = True
        if need_to_update:
            if __opts__['test']:
                ret['comment'] = 'Route53 record {0} set to be updated.'.format(name)
                ret['result'] = None
                return ret
            updated = __salt__['boto_route53.update_record'](name, value, zone,
                                                             record_type,
                                                             identifier, ttl,
                                                             region, key,
                                                             keyid, profile,
                                                             wait_for_sync,
                                                             split_dns,
                                                             private_zone)
            if updated:
                ret['changes']['old'] = record
                ret['changes']['new'] = {'name': name,
                                         'value': value,
                                         'record_type': record_type,
                                         'ttl': ttl,
                                         'identifier': identifier}
                ret['comment'] = 'Updated {0} Route53 record.'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to update {0} Route53 record.'.format(name)
        else:
            ret['comment'] = '{0} exists.'.format(name)
    return ret


def rr_absent(*args, **kwargs):
    return absent(*args, **kwargs)


def absent(
        name,
        zone,
        record_type,
        identifier=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        wait_for_sync=True,
        split_dns=False,
        private_zone=False):
    '''
    Ensure the Route53 record is deleted.

    name
        Name of the record.

    zone
        The zone to delete the record from.

    record_type
        The record type (A, NS, MX, TXT, etc.)

    identifier
        An identifier to match for deletion.

    region
        The region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    wait_for_sync
        Wait for an INSYNC change status from Route53.

    split_dns
        Route53 supports a public and private DNS zone with the same
        names.

    private_zone
        If using split_dns, specify if this is the private zone.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    record = __salt__['boto_route53.get_record'](name, zone, record_type,
                                                 False, region, key, keyid,
                                                 profile, split_dns,
                                                 private_zone, identifier)
    if record:
        if __opts__['test']:
            ret['comment'] = 'Route53 record {0} set to be deleted.'.format(name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_route53.delete_record'](name, zone,
                                                         record_type,
                                                         identifier, False,
                                                         region, key, keyid,
                                                         profile,
                                                         wait_for_sync,
                                                         split_dns,
                                                         private_zone)
        if deleted:
            ret['changes']['old'] = record
            ret['changes']['new'] = None
            ret['comment'] = 'Deleted {0} Route53 record.'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} Route53 record.'.format(name)
    else:
        ret['comment'] = '{0} does not exist.'.format(name)
    return ret


def hosted_zone_present(name, domain_name=None, private_zone=False, caller_ref=None, comment='',
                        vpc_id=None, vpc_name=None, vpc_region=None, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Ensure a hosted zone exists with the given attributes.  Note that most things cannot be
    modified once a zone is created - it must be deleted and re-spun to update these attributes.
    If you need the ability to update these attributes, please use the newer boto3_route53
    module instead:
        - private_zone (AWS API limitation).
        - comment (the appropriate call exists in the AWS API and in boto3, but has not, as of
          this writing, been added to boto2).
        - vpc_id (boto3 only)
        - vpc_name (really just a pointer to vpc_id anyway).
        - vpc_region (again, supported in boto3 but not boto2).

    name
        The name of the state definition.

    domain_name
        The name of the domain. This must be fully-qualified, terminating with a period.  This is
        the name you have registered with your domain registrar.  It is also the name you will
        delegate from your registrar to the Amazon Route 53 delegation servers returned in response
        to this request.  Defaults to the value of name if not provided.

    private_zone
        Set True if creating a private hosted zone.

    caller_ref
        A unique string that identifies the request and that allows create_hosted_zone() calls to be
        retried without the risk of executing the operation twice.  This helps ensure idempotency
        across state calls, but can cause issues if a zone is deleted and then an attempt is made
        to recreate it with the same caller_ref.  If not provided, a unique UUID will be generated
        at each state run, which avoids the risk of the above (transient) error.  This option is
        generally not needed.  Maximum length of 128.

    comment
        Any comments you want to include about the hosted zone.

    vpc_id
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with vpe_name.  Ignored when creating a non-private zone.

    vpc_name
        When creating a private hosted zone, either the VPC ID or VPC Name to associate with is
        required.  Exclusive with vpe_id.  Ignored when creating a non-private zone.

    vpc_region
        When creating a private hosted zone, the region of the associated VPC is required.  If not
        provided, an effort will be made to determine it from vpc_id or vpc_name, where possible.
        If this fails, you'll need to provide an explicit value for this option.  Ignored when
        creating a non-private zone.
    '''
    domain_name = domain_name if domain_name else name

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # First translaste vpc_name into a vpc_id if possible
    if private_zone:
        if not salt.utils.data.exactly_one((vpc_name, vpc_id)):
            raise SaltInvocationError('Either vpc_name or vpc_id is required when creating a '
                                      'private zone.')
        vpcs = __salt__['boto_vpc.describe_vpcs'](
                vpc_id=vpc_id, name=vpc_name, region=region, key=key,
                keyid=keyid, profile=profile).get('vpcs', [])
        if vpc_region and vpcs:
            vpcs = [v for v in vpcs if v['region'] == vpc_region]
        if not vpcs:
            msg = 'Private zone requested but a VPC matching given criteria not found.'
            log.error(msg)
            ret['comment'] = msg
            ret['result'] = False
            return ret
        if len(vpcs) > 1:
            log.error(
                'Private zone requested but multiple VPCs matching given '
                'criteria found: %s', [v['id'] for v in vpcs]
            )
            return None
        vpc = vpcs[0]
        if vpc_name:
            vpc_id = vpc['id']
        if not vpc_region:
            vpc_region = vpc['region']

    # Next, see if it (or they) exist at all, anywhere?
    deets = __salt__['boto_route53.describe_hosted_zones'](
          domain_name=domain_name, region=region, key=key, keyid=keyid,
          profile=profile)

    create = False
    if not deets:
        create = True
    else:  # Something exists - now does it match our criteria?
        if (salt.utils.json.loads(deets['HostedZone']['Config']['PrivateZone']) !=
                private_zone):
            create = True
        else:
            if private_zone:
                for v, d in deets.get('VPCs', {}).items():
                    if (d['VPCId'] == vpc_id
                            and d['VPCRegion'] == vpc_region):
                        create = False
                        break
                    else:
                        create = True
        if not create:
            ret['comment'] = 'Hostd Zone {0} already in desired state'.format(
                    domain_name)
        else:
            # Until we get modifies in place with boto3, the best option is to
            # attempt creation and let route53 tell us if we're stepping on
            # toes.  We can't just fail, because some scenarios (think split
            # horizon DNS) require zones with identical names but different
            # settings...
            log.info('A Hosted Zone with name %s already exists, but with '
                     'different settings.  Will attempt to create the one '
                     'requested on the assumption this is what is desired.  '
                     'This may fail...', domain_name)

    if create:
        if caller_ref is None:
            caller_ref = six.text_type(uuid.uuid4())
        if __opts__['test']:
            ret['comment'] = 'Route53 Hosted Zone {0} set to be added.'.format(
                    domain_name)
            ret['result'] = None
            return ret
        res = __salt__['boto_route53.create_hosted_zone'](domain_name=domain_name,
                caller_ref=caller_ref, comment=comment, private_zone=private_zone,
                vpc_id=vpc_id, vpc_region=vpc_region, region=region, key=key,
                keyid=keyid, profile=profile)
        if res:
            msg = 'Hosted Zone {0} successfully created'.format(domain_name)
            log.info(msg)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = res
        else:
            ret['comment'] = 'Creating Hosted Zone {0} failed'.format(
                    domain_name)
            ret['result'] = False

    return ret


def hosted_zone_absent(name, domain_name=None, region=None, key=None,
                       keyid=None, profile=None):
    '''
    Ensure the Route53 Hostes Zone described is absent

    name
        The name of the state definition.

    domain_name
        The FQDN (including final period) of the zone you wish absent.  If not
        provided, the value of name will be used.

    '''
    domain_name = domain_name if domain_name else name

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    deets = __salt__['boto_route53.describe_hosted_zones'](
          domain_name=domain_name, region=region, key=key, keyid=keyid,
          profile=profile)
    if not deets:
        ret['comment'] = 'Hosted Zone {0} already absent'.format(domain_name)
        log.info(ret['comment'])
        return ret
    if __opts__['test']:
        ret['comment'] = 'Route53 Hosted Zone {0} set to be deleted.'.format(
                domain_name)
        ret['result'] = None
        return ret
    # Not entirely comfortable with this - no safety checks around pub/priv, VPCs
    # or anything else.  But this is all the module function exposes, so hmph.
    # Inclined to put it on the "wait 'til we port to boto3" pile in any case :)
    if __salt__['boto_route53.delete_zone'](
            zone=domain_name, region=region, key=key, keyid=keyid,
            profile=profile):
        ret['comment'] = 'Route53 Hosted Zone {0} deleted'.format(domain_name)
        log.info(ret['comment'])
        ret['changes']['old'] = deets
        ret['changes']['new'] = None

    return ret
