# -*- coding: utf-8 -*-
'''
Manage DynamoDB Tables
======================

.. versionadded:: 2015.5.0

Create and destroy DynamoDB tables. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit DynamoDB credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    keyid: GKTADJGHEIQSXMKKRBJ08H
    key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
    region: us-east-1

It's also possible to specify ``key``, ``keyid`` and ``region`` via a
profile, either passed in as a dict, or as a string to pull from
pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure DynamoDB table does not exist:
      boto_dynamodb.absent:
        - table_name: new_table
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1

    Ensure DynamoDB table exists:
      boto_dynamodb.present:
        - table_name: new_table
        - read_capacity_units: 1
        - write_capacity_units: 2
        - hash_key: primary_id
        - hash_key_data_type: N
        - range_key: start_timestamp
        - range_key_data_type: N
        - keyid: GKTADJGHEIQSXMKKRBJ08H
        - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        - region: us-east-1
        - local_indexes:
            - index:
                - name: "primary_id_end_timestamp_index"
                - hash_key: primary_id
                - hash_key_data_type: N
                - range_key: end_timestamp
                - range_key_data_type: N
        - global_indexes:
            - index:
                - name: "name_end_timestamp_index"
                - hash_key: name
                - hash_key_data_type: S
                - range_key: end_timestamp
                - range_key_data_type: N
                - read_capacity_units: 3
                - write_capacity_units: 4
'''
# Import Python libs
from __future__ import absolute_import
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    stream=sys.stdout
)
log = logging.getLogger()


def __virtual__():
    '''
    Only load if boto_dynamodb is available.
    '''
    ret = 'boto_dynamodb' if 'boto_dynamodb.exists' in __salt__ else False
    return ret


def present(table_name,
            region=None,
            key=None,
            keyid=None,
            profile=None,
            read_capacity_units=None,
            write_capacity_units=None,
            hash_key=None,
            hash_key_data_type=None,
            range_key=None,
            range_key_data_type=None,
            local_indexes=None,
            global_indexes=None):
    '''
    Ensure the DynamoDB table exists.  Note: all properties of the table
    can only be set during table creation.  Adding or changing
    indexes or key schema cannot be done after table creation

    table_name
        Name of the DynamoDB table

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    read_capacity_units
        The read throughput for this table

    write_capacity_units
        The write throughput for this table

    hash_key
        The name of the attribute that will be used as the hash key
        for this table

    hash_key_data_type
        The DynamoDB datatype of the hash key

    range_key
        The name of the attribute that will be used as the range key
        for this table

    range_key_data_type
        The DynamoDB datatype of the range key

    local_indexes
        The local indexes you would like to create

    global_indexes
        The local indexes you would like to create
    '''
    ret = {'name': table_name, 'result': None, 'comment': '', 'changes': {}}
    exists = __salt__['boto_dynamodb.exists'](
        table_name,
        region,
        key,
        keyid,
        profile
    )
    if exists:
        ret['comment'] = 'DynamoDB table {0} already exists. \
                         Nothing to change.'.format(table_name)
        ret['result'] = True
        return ret

    if __opts__['test']:
        ret['comment'] = 'DynamoDB table {0} is set to be created \
                        '.format(table_name)
        return ret

    is_created = __salt__['boto_dynamodb.create_table'](
        table_name,
        region,
        key,
        keyid,
        profile,
        read_capacity_units,
        write_capacity_units,
        hash_key,
        hash_key_data_type,
        range_key,
        range_key_data_type,
        local_indexes,
        global_indexes
    )
    ret['result'] = is_created

    if is_created:
        ret['comment'] = 'DynamoDB table {0} created successfully \
                             '.format(table_name)
        ret['changes'].setdefault('old', None)
        changes = {}
        changes['table'] = table_name
        changes['read_capacity_units'] = read_capacity_units,
        changes['write_capacity_units'] = write_capacity_units,
        changes['hash_key'] = hash_key,
        changes['hash_key_data_type'] = hash_key_data_type
        changes['range_key'] = range_key,
        changes['range_key_data_type'] = range_key_data_type,
        changes['local_indexes'] = local_indexes,
        changes['global_indexes'] = global_indexes
        ret['changes']['new'] = changes
    else:
        ret['comment'] = 'Failed to create table {0}'.format(table_name)
    return ret


def absent(table_name,
           region=None,
           key=None,
           keyid=None,
           profile=None):
    '''
    Ensure the DynamoDB table does not exist.

    table_name
        Name of the DynamoDB table.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': table_name, 'result': None, 'comment': '', 'changes': {}}
    exists = __salt__['boto_dynamodb.exists'](
        table_name,
        region,
        key,
        keyid,
        profile
    )
    if not exists:
        ret['comment'] = 'DynamoDB table {0} does not exist'.format(table_name)
        ret['result'] = True
        return ret

    if __opts__['test']:
        ret['comment'] = 'DynamoDB table {0} is set to be deleted \
                         '.format(table_name)
        ret['result'] = None
        return ret

    is_deleted = __salt__['boto_dynamodb.delete'](table_name, region, key, keyid, profile)
    if is_deleted:
        ret['comment'] = 'Deleted DynamoDB table {0}'.format(table_name)
        ret['changes'].setdefault('old', 'Table {0} exists'.format(table_name))
        ret['changes'].setdefault('new', 'Table {0} deleted'.format(table_name))
        ret['result'] = True
    else:
        ret['comment'] = 'Failed to delete DynamoDB table {0} \
                         '.format(table_name)
        ret['result'] = False
    return ret
