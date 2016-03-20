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
from __future__ import absolute_import

# Import Salt Libs
from salt.utils import SaltInvocationError


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_route53' if 'boto_route53.get_record' in __salt__ else False


def present(
        name,
        value,
        zone,
        record_type,
        ttl=None,
        identifier=None,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        wait_for_sync=True,
        split_dns=False,
        private_zone=False):
    '''
    Ensure the Route53 record is present.

    name
        Name of the record.

    value
        Value of the record.

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

    # If a list is passed in for value, change it to a comma-separated string
    # So it will work with subsequent boto module calls and string functions
    if isinstance(value, list):
        value = ','.join(value)

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
        if ttl and str(ttl) != str(record['ttl']):
            need_to_update = True
        if need_to_update:
            if __opts__['test']:
                msg = 'Route53 record {0} set to be updated.'.format(name)
                ret['comment'] = msg
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
                msg = 'Failed to update {0} Route53 record.'.format(name)
                ret['comment'] = msg
        else:
            ret['comment'] = '{0} exists.'.format(name)
    return ret


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
            msg = 'Route53 record {0} set to be deleted.'.format(name)
            ret['comment'] = msg
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
            msg = 'Failed to delete {0} Route53 record.'.format(name)
            ret['comment'] = msg
    else:
        ret['comment'] = '{0} does not exist.'.format(name)
    return ret
