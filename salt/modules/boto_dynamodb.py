"""
Connection module for Amazon DynamoDB

.. versionadded:: 2015.5.0

:configuration: This module accepts explicit DynamoDB credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
"""

# keep lint from choking on _get_conn and _cache_id
# pylint: disable=E0602

import logging
import time

import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)
logging.getLogger("boto").setLevel(logging.INFO)


try:
    # pylint: disable=unused-import
    import boto
    import boto3  # pylint: disable=unused-import
    import boto.dynamodb2
    import botocore

    # pylint: enable=unused-import
    from boto.dynamodb2.fields import (
        AllIndex,
        GlobalAllIndex,
        GlobalIncludeIndex,
        GlobalKeysOnlyIndex,
        HashKey,
        RangeKey,
    )
    from boto.dynamodb2.table import Table
    from boto.exception import JSONResponseError

    logging.getLogger("boto").setLevel(logging.INFO)

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

log = logging.getLogger(__name__)

__deprecated__ = (
    3009,
    "boto",
    "https://github.com/salt-extensions/saltext-boto",
)


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto.assign_funcs"](__name__, "dynamodb2", pack=__salt__)
    return has_boto_reqs


def list_tags_of_resource(
    resource_arn, region=None, key=None, keyid=None, profile=None
):
    """
    Returns a dictionary of all tags currently attached to a given resource.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.list_tags_of_resource \
              resource_arn=arn:aws:dynamodb:us-east-1:012345678901:table/my-table

    .. versionadded:: 3006.0
    """
    conn3 = __utils__["boto3.get_connection"](
        "dynamodb", region=region, key=key, keyid=keyid, profile=profile
    )
    retries = 10
    sleep = 6
    tags = []
    while retries:
        try:
            log.debug("Garnering tags of resource %s", resource_arn)
            marker = ""
            while marker is not None:
                ret = conn3.list_tags_of_resource(
                    ResourceArn=resource_arn, NextToken=marker
                )
                tags += ret.get("Tags", [])
                marker = ret.get("NextToken")
            return {tag["Key"]: tag["Value"] for tag in tags}
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get("Error", {}).get("Code") == "Throttling":
                retries -= 1
                log.debug("Throttled by AWS API, retrying in %s seconds...", sleep)
                time.sleep(sleep)
                continue
            log.error(
                "Failed to list tags for resource %s: %s", resource_arn, err.message
            )
            return False


def tag_resource(resource_arn, tags, region=None, key=None, keyid=None, profile=None):
    """
    Sets given tags (provided as list or dict) on the given resource.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.tag_resource \
              resource_arn=arn:aws:dynamodb:us-east-1:012345678901:table/my-table \
              tags='{Name: my-table, Owner: Ops}'

    .. versionadded:: 3006.0
    """
    conn3 = __utils__["boto3.get_connection"](
        "dynamodb", region=region, key=key, keyid=keyid, profile=profile
    )
    retries = 10
    sleep = 6
    if isinstance(tags, dict):
        tags = [{"Key": key, "Value": val} for key, val in tags.items()]
    while retries:
        try:
            log.debug("Setting tags on resource %s", resource_arn)
            conn3.tag_resource(ResourceArn=resource_arn, Tags=tags)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get("Error", {}).get("Code") == "Throttling":
                retries -= 1
                log.debug("Throttled by AWS API, retrying in %s seconds...", sleep)
                time.sleep(sleep)
                continue
            log.error(
                "Failed to set tags on resource %s: %s", resource_arn, err.message
            )
            return False


def untag_resource(
    resource_arn, tag_keys, region=None, key=None, keyid=None, profile=None
):
    """
    Removes given tags (provided as list) from the given resource.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.untag_resource \
              resource_arn=arn:aws:dynamodb:us-east-1:012345678901:table/my-table \
              tag_keys='[Name, Owner]'

    .. versionadded:: 3006.0
    """
    conn3 = __utils__["boto3.get_connection"](
        "dynamodb", region=region, key=key, keyid=keyid, profile=profile
    )
    retries = 10
    sleep = 6
    while retries:
        try:
            log.debug("Removing tags from resource %s", resource_arn)
            ret = conn3.untag_resource(ResourceArn=resource_arn, TagKeys=tag_keys)
            return True
        except botocore.exceptions.ParamValidationError as err:
            raise SaltInvocationError(str(err))
        except botocore.exceptions.ClientError as err:
            if retries and err.response.get("Error", {}).get("Code") == "Throttling":
                retries -= 1
                log.debug("Throttled by AWS API, retrying in %s seconds...", sleep)
                time.sleep(sleep)
                continue
            log.error(
                "Failed to remove tags from resource %s: %s", resource_arn, err.message
            )
            return False


def create_table(
    table_name,
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
    global_indexes=None,
):
    """
    Creates a DynamoDB table.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.create_table table_name /
        region=us-east-1 /
        hash_key=id /
        hash_key_data_type=N /
        range_key=created_at /
        range_key_data_type=N /
        read_capacity_units=1 /
        write_capacity_units=1
    """
    schema = []
    primary_index_fields = []
    primary_index_name = ""
    if hash_key:
        hash_key_obj = HashKey(hash_key, data_type=hash_key_data_type)
        schema.append(hash_key_obj)
        primary_index_fields.append(hash_key_obj)
        primary_index_name += hash_key
    if range_key:
        range_key_obj = RangeKey(range_key, data_type=range_key_data_type)
        schema.append(range_key_obj)
        primary_index_fields.append(range_key_obj)
        primary_index_name += "_"
        primary_index_name += range_key
    primary_index_name += "_index"
    throughput = {"read": read_capacity_units, "write": write_capacity_units}
    local_table_indexes = []
    if local_indexes:
        for index in local_indexes:
            local_table_indexes.append(extract_index(index))
    global_table_indexes = []
    if global_indexes:
        for index in global_indexes:
            global_table_indexes.append(extract_index(index, global_index=True))

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    Table.create(
        table_name,
        schema=schema,
        throughput=throughput,
        indexes=local_table_indexes,
        global_indexes=global_table_indexes,
        connection=conn,
    )

    # Table creation can take several seconds to propagate.
    # We will check MAX_ATTEMPTS times.
    MAX_ATTEMPTS = 30
    for i in range(MAX_ATTEMPTS):
        if exists(table_name, region, key, keyid, profile):
            return True
        else:
            time.sleep(1)  # sleep for one second and try again
    return False


def exists(table_name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if a table exists.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.exists table_name region=us-east-1
    """
    try:
        conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
        conn.describe_table(table_name)
    except JSONResponseError as e:
        if e.error_code == "ResourceNotFoundException":
            return False
        raise

    return True


def delete(table_name, region=None, key=None, keyid=None, profile=None):
    """
    Delete a DynamoDB table.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.delete table_name region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    table = Table(table_name, connection=conn)
    table.delete()

    # Table deletion can take several seconds to propagate.
    # We will retry MAX_ATTEMPTS times.
    MAX_ATTEMPTS = 30
    for i in range(MAX_ATTEMPTS):
        if not exists(table_name, region, key, keyid, profile):
            return True
        else:
            time.sleep(1)  # sleep for one second and try again
    return False


def update(
    table_name,
    throughput=None,
    global_indexes=None,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Update a DynamoDB table.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.update table_name region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    table = Table(table_name, connection=conn)
    return table.update(throughput=throughput, global_indexes=global_indexes)


def create_global_secondary_index(
    table_name, global_index, region=None, key=None, keyid=None, profile=None
):
    """
    Creates a single global secondary index on a DynamoDB table.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.create_global_secondary_index table_name /
        index_name
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    table = Table(table_name, connection=conn)
    return table.create_global_secondary_index(global_index)


def update_global_secondary_index(
    table_name, global_indexes, region=None, key=None, keyid=None, profile=None
):
    """
    Updates the throughput of the given global secondary indexes.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.update_global_secondary_index table_name /
        indexes
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    table = Table(table_name, connection=conn)
    return table.update_global_secondary_index(global_indexes)


def describe(table_name, region=None, key=None, keyid=None, profile=None):
    """
    Describe a DynamoDB table.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.describe table_name region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    table = Table(table_name, connection=conn)
    return table.describe()


def extract_index(index_data, global_index=False):
    """
    Instantiates and returns an AllIndex object given a valid index
    configuration

    CLI Example:

    .. code-block:: bash

        salt myminion boto_dynamodb.extract_index index
    """
    parsed_data = {}
    keys = []

    for key, value in index_data.items():
        for item in value:
            for field, data in item.items():
                if field == "hash_key":
                    parsed_data["hash_key"] = data
                elif field == "hash_key_data_type":
                    parsed_data["hash_key_data_type"] = data
                elif field == "range_key":
                    parsed_data["range_key"] = data
                elif field == "range_key_data_type":
                    parsed_data["range_key_data_type"] = data
                elif field == "name":
                    parsed_data["name"] = data
                elif field == "read_capacity_units":
                    parsed_data["read_capacity_units"] = data
                elif field == "write_capacity_units":
                    parsed_data["write_capacity_units"] = data
                elif field == "includes":
                    parsed_data["includes"] = data
                elif field == "keys_only":
                    parsed_data["keys_only"] = True

    if parsed_data["hash_key"]:
        keys.append(
            HashKey(
                parsed_data["hash_key"], data_type=parsed_data["hash_key_data_type"]
            )
        )
    if parsed_data.get("range_key"):
        keys.append(
            RangeKey(
                parsed_data["range_key"], data_type=parsed_data["range_key_data_type"]
            )
        )
    if (
        global_index
        and parsed_data["read_capacity_units"]
        and parsed_data["write_capacity_units"]
    ):
        parsed_data["throughput"] = {
            "read": parsed_data["read_capacity_units"],
            "write": parsed_data["write_capacity_units"],
        }
    if parsed_data["name"] and keys:
        if global_index:
            if parsed_data.get("keys_only") and parsed_data.get("includes"):
                raise SaltInvocationError(
                    "Only one type of GSI projection can be used."
                )

            if parsed_data.get("includes"):
                return GlobalIncludeIndex(
                    parsed_data["name"],
                    parts=keys,
                    throughput=parsed_data["throughput"],
                    includes=parsed_data["includes"],
                )
            elif parsed_data.get("keys_only"):
                return GlobalKeysOnlyIndex(
                    parsed_data["name"],
                    parts=keys,
                    throughput=parsed_data["throughput"],
                )
            else:
                return GlobalAllIndex(
                    parsed_data["name"],
                    parts=keys,
                    throughput=parsed_data["throughput"],
                )
        else:
            return AllIndex(parsed_data["name"], parts=keys)
