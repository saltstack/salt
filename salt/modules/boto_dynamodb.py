# -*- coding: utf-8 -*-
'''
Connection module for Amazon DynamoDB

.. versionadded:: 2015.5.0

:configuration: This module accepts explicit DynamoDB credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::


        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config::

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''

# Import Python libs
import logging
import time

logger = logging.getLogger(__name__)
logging.getLogger('boto').setLevel(logging.INFO)

# Import third party libs
try:
    import boto
    import boto.dynamodb2
    from boto.dynamodb2.fields import HashKey, RangeKey
    from boto.dynamodb2.fields import AllIndex, GlobalAllIndex
    from boto.dynamodb2.table import Table
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt._compat import string_types


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def _create_connection(region=None, key=None, keyid=None, profile=None):
    '''
    Get a boto connection to DynamoDB.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('dynamodb.region'):
        region = __salt__['config.option']('dynamodb.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('dynamodb.key'):
        key = __salt__['config.option']('dynamodb.key')
    if not keyid and __salt__['config.option']('dynamodb.keyid'):
        keyid = __salt__['config.option']('dynamodb.keyid')

    try:
        conn = boto.dynamodb2.connect_to_region(
            region,
            aws_access_key_id=keyid,
            aws_secret_access_key=key
        )
    except boto.exception.NoAuthHandlerFound:
        logger.error('No authentication credentials found when attempting to'
                     ' make boto dynamodb connection.')
        return None
    return conn


def create_table(table_name, region=None, key=None, keyid=None, profile=None,
                 read_capacity_units=None, write_capacity_units=None,
                 hash_key=None, hash_key_data_type=None, range_key=None,
                 range_key_data_type=None, local_indexes=None,
                 global_indexes=None):
    '''
    Creates a DynamoDB table.

    CLI example::

        salt myminion boto_dynamodb.create_table table_name /
        region=us-east-1 /
        hash_key=id /
        hash_key_data_type=N /
        range_key=created_at /
        range_key_data_type=N /
        read_capacity_units=1 /
        write_capacity_units=1
    '''
    schema = []
    primary_index_fields = []
    primary_index_name = ''
    if hash_key:
        hash_key_obj = HashKey(hash_key, data_type=hash_key_data_type)
        schema.append(hash_key_obj)
        primary_index_fields.append(hash_key_obj)
        primary_index_name += hash_key
    if range_key:
        range_key_obj = RangeKey(range_key, data_type=range_key_data_type)
        schema.append(range_key_obj)
        primary_index_fields.append(range_key_obj)
        primary_index_name += '_'
        primary_index_name += range_key
    primary_index_name += '_index'
    throughput = {
        'read':     read_capacity_units,
        'write':    write_capacity_units
    }
    local_table_indexes = []
    # Add the table's key
    local_table_indexes.append(
        AllIndex(primary_index_name, parts=primary_index_fields)
    )
    if local_indexes:
        for index in local_indexes:
            local_table_indexes.append(_extract_index(index))
    global_table_indexes = []
    if global_indexes:
        for index in global_indexes:
            global_table_indexes.append(
                _extract_index(index, global_index=True)
            )

    conn = _create_connection(region, key, keyid, profile)
    Table.create(
        table_name,
        schema=schema,
        throughput=throughput,
        indexes=local_table_indexes,
        global_indexes=global_table_indexes,
        connection=conn
    )

    # Table creation can take several seconds to propagate.
    # We will check MAX_ATTEMPTS times.
    MAX_ATTEMPTS = 30
    for i in range(MAX_ATTEMPTS):
        if exists(
            table_name,
            region,
            key,
            keyid,
            profile
        ):
            return True
        else:
            time.sleep(1)   # sleep for one second and try again
    return False


def exists(table_name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if a table exists.

    CLI example::

        salt myminion boto_dynamodb.exists table_name region=us-east-1
    '''
    conn = _create_connection(region, key, keyid, profile)
    tables = conn.list_tables()
    return tables and table_name in tables['TableNames']


def delete(table_name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete a DynamoDB table.

    CLI example::

        salt myminion boto_dynamodb.delete table_name region=us-east-1
    '''
    conn = _create_connection(region, key, keyid, profile)
    table = Table(table_name, connection=conn)
    table.delete()

    # Table deletion can take several seconds to propagate.
    # We will retry MAX_ATTEMPTS times.
    MAX_ATTEMPTS = 30
    for i in range(MAX_ATTEMPTS):
        if not exists(table_name, region, key, keyid, profile):
            return True
        else:
            time.sleep(1)   # sleep for one second and try again
    return False


def _extract_index(index_data, global_index=False):
    '''
    Instantiates and returns an AllIndex object given a valid index
    configuration
    '''
    parsed_data = {}
    keys = []

    for key, value in index_data.iteritems():
        for item in value:
            for field, data in item.iteritems():
                if field == 'hash_key':
                    parsed_data['hash_key'] = data
                elif field == 'hash_key_data_type':
                    parsed_data['hash_key_data_type'] = data
                elif field == 'range_key':
                    parsed_data['range_key'] = data
                elif field == 'range_key_data_type':
                    parsed_data['range_key_data_type'] = data
                elif field == 'name':
                    parsed_data['name'] = data
                elif field == 'read_capacity_units':
                    parsed_data['read_capacity_units'] = data
                elif field == 'write_capacity_units':
                    parsed_data['write_capacity_units'] = data

    if parsed_data['hash_key']:
        keys.append(
            HashKey(
                parsed_data['hash_key'],
                data_type=parsed_data['hash_key_data_type']
            )
        )
    if parsed_data['range_key']:
        keys.append(
            RangeKey(
                parsed_data['range_key'],
                data_type=parsed_data['range_key_data_type']
            )
        )
    if (
            global_index and
            parsed_data['read_capacity_units'] and
            parsed_data['write_capacity_units']):
        parsed_data['throughput'] = {
            'read':     parsed_data['read_capacity_units'],
            'write':    parsed_data['write_capacity_units']
        }
    if parsed_data['name'] and len(keys) > 0:
        if global_index:
            return GlobalAllIndex(
                parsed_data['name'],
                parts=keys,
                throughput=parsed_data['throughput']
            )
        else:
            return AllIndex(
                parsed_data['name'],
                parts=keys
            )
