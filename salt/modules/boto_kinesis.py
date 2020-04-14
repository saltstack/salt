# -*- coding: utf-8 -*-
"""
Connection module for Amazon Kinesis

.. versionadded:: 2017.7.0

:configuration: This module accepts explicit Kinesis credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        kinesis.keyid: GKTADJGHEIQSXMKKRBJ08H
        kinesis.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        kinesis.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

    .. code-block:: yaml

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto3

"""
# keep lint from choking on _get_conn
# pylint: disable=E0602

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import random
import sys
import time

import salt.utils.versions

# Import Salt libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import third party libs
# pylint: disable=unused-import
try:
    import boto3
    import botocore

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=unused-import

log = logging.getLogger(__name__)

__virtualname__ = "boto_kinesis"


def __virtual__():
    """
    Only load if boto3 libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto3.assign_funcs"](__name__, "kinesis")
        return __virtualname__
    return has_boto_reqs


def _get_basic_stream(stream_name, conn):
    """
    Stream info from AWS, via describe_stream
    Only returns the first "page" of shards (up to 100); use _get_full_stream() for all shards.

    CLI example::

        salt myminion boto_kinesis._get_basic_stream my_stream existing_conn
    """
    return _execute_with_retries(conn, "describe_stream", StreamName=stream_name)


def _get_full_stream(stream_name, region=None, key=None, keyid=None, profile=None):
    """
    Get complete stream info from AWS, via describe_stream, including all shards.

    CLI example::

        salt myminion boto_kinesis._get_full_stream my_stream region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = {}
    stream = _get_basic_stream(stream_name, conn)["result"]
    full_stream = stream

    # iterate through if there are > 100 shards (max that AWS will return from describe_stream)
    while stream["StreamDescription"]["HasMoreShards"]:
        stream = _execute_with_retries(
            conn,
            "describe_stream",
            StreamName=stream_name,
            ExclusiveStartShardId=stream["StreamDescription"]["Shards"][-1]["ShardId"],
        )
        stream = stream["result"]
        full_stream["StreamDescription"]["Shards"] += stream["StreamDescription"][
            "Shards"
        ]

    r["result"] = full_stream
    return r


def get_stream_when_active(
    stream_name, region=None, key=None, keyid=None, profile=None
):
    """
    Get complete stream info from AWS, returning only when the stream is in the ACTIVE state.
    Continues to retry when stream is updating or creating.
    If the stream is deleted during retries, the loop will catch the error and break.

    CLI example::

        salt myminion boto_kinesis.get_stream_when_active my_stream region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    stream_status = None
    # only get basic stream until it's active,
    # so we don't pull the full list of shards repeatedly (in case of very large stream)
    attempt = 0
    max_retry_delay = 10
    while stream_status != "ACTIVE":
        time.sleep(_jittered_backoff(attempt, max_retry_delay))
        attempt += 1
        stream_response = _get_basic_stream(stream_name, conn)
        if "error" in stream_response:
            return stream_response
        stream_status = stream_response["result"]["StreamDescription"]["StreamStatus"]

    # now it's active, get the full stream if necessary
    if stream_response["result"]["StreamDescription"]["HasMoreShards"]:
        stream_response = _get_full_stream(stream_name, region, key, keyid, profile)

    return stream_response


def exists(stream_name, region=None, key=None, keyid=None, profile=None):
    """
    Check if the stream exists. Returns False and the error if it does not.

    CLI example::

        salt myminion boto_kinesis.exists my_stream region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = {}

    stream = _get_basic_stream(stream_name, conn)
    if "error" in stream:
        r["result"] = False
        r["error"] = stream["error"]
    else:
        r["result"] = True

    return r


def create_stream(
    stream_name, num_shards, region=None, key=None, keyid=None, profile=None
):
    """
    Create a stream with name stream_name and initial number of shards num_shards.

    CLI example::

        salt myminion boto_kinesis.create_stream my_stream N region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(
        conn, "create_stream", ShardCount=num_shards, StreamName=stream_name
    )
    if "error" not in r:
        r["result"] = True
    return r


def delete_stream(stream_name, region=None, key=None, keyid=None, profile=None):
    """
    Delete the stream with name stream_name. This cannot be undone! All data will be lost!!

    CLI example::

        salt myminion boto_kinesis.delete_stream my_stream region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(conn, "delete_stream", StreamName=stream_name)
    if "error" not in r:
        r["result"] = True
    return r


def increase_stream_retention_period(
    stream_name, retention_hours, region=None, key=None, keyid=None, profile=None
):
    """
    Increase stream retention period to retention_hours

    CLI example::

        salt myminion boto_kinesis.increase_stream_retention_period my_stream N region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(
        conn,
        "increase_stream_retention_period",
        StreamName=stream_name,
        RetentionPeriodHours=retention_hours,
    )
    if "error" not in r:
        r["result"] = True
    return r


def decrease_stream_retention_period(
    stream_name, retention_hours, region=None, key=None, keyid=None, profile=None
):
    """
    Decrease stream retention period to retention_hours

    CLI example::

        salt myminion boto_kinesis.decrease_stream_retention_period my_stream N region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(
        conn,
        "decrease_stream_retention_period",
        StreamName=stream_name,
        RetentionPeriodHours=retention_hours,
    )
    if "error" not in r:
        r["result"] = True
    return r


def enable_enhanced_monitoring(
    stream_name, metrics, region=None, key=None, keyid=None, profile=None
):
    """
    Enable enhanced monitoring for the specified shard-level metrics on stream stream_name

    CLI example::

        salt myminion boto_kinesis.enable_enhanced_monitoring my_stream ["metrics", "to", "enable"] region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(
        conn,
        "enable_enhanced_monitoring",
        StreamName=stream_name,
        ShardLevelMetrics=metrics,
    )

    if "error" not in r:
        r["result"] = True
    return r


def disable_enhanced_monitoring(
    stream_name, metrics, region=None, key=None, keyid=None, profile=None
):
    """
    Disable enhanced monitoring for the specified shard-level metrics on stream stream_name

    CLI example::

        salt myminion boto_kinesis.disable_enhanced_monitoring my_stream ["metrics", "to", "disable"] region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = _execute_with_retries(
        conn,
        "disable_enhanced_monitoring",
        StreamName=stream_name,
        ShardLevelMetrics=metrics,
    )

    if "error" not in r:
        r["result"] = True
    return r


def get_info_for_reshard(stream_details):
    """
    Collect some data: number of open shards, key range, etc.
    Modifies stream_details to add a sorted list of OpenShards.
    Returns (min_hash_key, max_hash_key, stream_details)

    CLI example::

        salt myminion boto_kinesis.get_info_for_reshard existing_stream_details
    """
    min_hash_key = 0
    max_hash_key = 0
    stream_details["OpenShards"] = []
    for shard in stream_details["Shards"]:
        shard_id = shard["ShardId"]
        if "EndingSequenceNumber" in shard["SequenceNumberRange"]:
            # EndingSequenceNumber is null for open shards, so this shard must be closed
            log.debug("skipping closed shard %s", shard_id)
            continue
        stream_details["OpenShards"].append(shard)
        shard["HashKeyRange"]["StartingHashKey"] = long_int(
            shard["HashKeyRange"]["StartingHashKey"]
        )
        shard["HashKeyRange"]["EndingHashKey"] = long_int(
            shard["HashKeyRange"]["EndingHashKey"]
        )
        if shard["HashKeyRange"]["StartingHashKey"] < min_hash_key:
            min_hash_key = shard["HashKeyRange"]["StartingHashKey"]
        if shard["HashKeyRange"]["EndingHashKey"] > max_hash_key:
            max_hash_key = shard["HashKeyRange"]["EndingHashKey"]
    stream_details["OpenShards"].sort(
        key=lambda shard: long_int(shard["HashKeyRange"]["StartingHashKey"])
    )
    return min_hash_key, max_hash_key, stream_details


def long_int(hash_key):
    """
    The hash key is a 128-bit int, sent as a string.
    It's necessary to convert to int/long for comparison operations.
    This helper method handles python 2/3 incompatibility

    CLI example::

        salt myminion boto_kinesis.long_int some_MD5_hash_as_string

    :return: long object if python 2.X, int object if python 3.X
    """
    if sys.version_info < (3,):
        return long(hash_key)  # pylint: disable=incompatible-py3-code
    else:
        return int(hash_key)


def reshard(
    stream_name,
    desired_size,
    force=False,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Reshard a kinesis stream.  Each call to this function will wait until the stream is ACTIVE,
    then make a single split or merge operation. This function decides where to split or merge
    with the assumption that the ultimate goal is a balanced partition space.

    For safety, user must past in force=True; otherwise, the function will dry run.

    CLI example::

        salt myminion boto_kinesis.reshard my_stream N True region=us-east-1

    :return: True if a split or merge was found/performed, False if nothing is needed
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    r = {}

    stream_response = get_stream_when_active(stream_name, region, key, keyid, profile)
    if "error" in stream_response:
        return stream_response

    stream_details = stream_response["result"]["StreamDescription"]
    min_hash_key, max_hash_key, stream_details = get_info_for_reshard(stream_details)

    log.debug(
        "found %s open shards, min_hash_key %s max_hash_key %s",
        len(stream_details["OpenShards"]),
        min_hash_key,
        max_hash_key,
    )

    # find the first open shard that doesn't match the desired pattern. When we find it,
    # either split or merge (depending on if it's too big or too small), and then return.
    for shard_num, shard in enumerate(stream_details["OpenShards"]):
        shard_id = shard["ShardId"]
        if "EndingSequenceNumber" in shard["SequenceNumberRange"]:
            # something went wrong, there's a closed shard in our open shard list
            log.debug("this should never happen! closed shard %s", shard_id)
            continue

        starting_hash_key = shard["HashKeyRange"]["StartingHashKey"]
        ending_hash_key = shard["HashKeyRange"]["EndingHashKey"]
        # this weird math matches what AWS does when you create a kinesis stream
        # with an initial number of shards.
        expected_starting_hash_key = (
            max_hash_key - min_hash_key
        ) / desired_size * shard_num + shard_num
        expected_ending_hash_key = (max_hash_key - min_hash_key) / desired_size * (
            shard_num + 1
        ) + shard_num
        # fix an off-by-one at the end
        if expected_ending_hash_key > max_hash_key:
            expected_ending_hash_key = max_hash_key

        log.debug(
            "Shard %s (%s) should start at %s: %s",
            shard_num,
            shard_id,
            expected_starting_hash_key,
            starting_hash_key == expected_starting_hash_key,
        )
        log.debug(
            "Shard %s (%s) should end at %s: %s",
            shard_num,
            shard_id,
            expected_ending_hash_key,
            ending_hash_key == expected_ending_hash_key,
        )

        if starting_hash_key != expected_starting_hash_key:
            r["error"] = "starting hash keys mismatch, don't know what to do!"
            return r

        if ending_hash_key == expected_ending_hash_key:
            continue

        if ending_hash_key > expected_ending_hash_key + 1:
            # split at expected_ending_hash_key
            if force:
                log.debug(
                    "%s should end at %s, actual %s, splitting",
                    shard_id,
                    expected_ending_hash_key,
                    ending_hash_key,
                )
                r = _execute_with_retries(
                    conn,
                    "split_shard",
                    StreamName=stream_name,
                    ShardToSplit=shard_id,
                    NewStartingHashKey=str(expected_ending_hash_key + 1),
                )  # future lint: disable=blacklisted-function
            else:
                log.debug(
                    "%s should end at %s, actual %s would split",
                    shard_id,
                    expected_ending_hash_key,
                    ending_hash_key,
                )

            if "error" not in r:
                r["result"] = True
            return r
        else:
            # merge
            next_shard_id = _get_next_open_shard(stream_details, shard_id)
            if not next_shard_id:
                r["error"] = "failed to find next shard after {0}".format(shard_id)
                return r
            if force:
                log.debug(
                    "%s should continue past %s, merging with %s",
                    shard_id,
                    ending_hash_key,
                    next_shard_id,
                )
                r = _execute_with_retries(
                    conn,
                    "merge_shards",
                    StreamName=stream_name,
                    ShardToMerge=shard_id,
                    AdjacentShardToMerge=next_shard_id,
                )
            else:
                log.debug(
                    "%s should continue past %s, would merge with %s",
                    shard_id,
                    ending_hash_key,
                    next_shard_id,
                )

            if "error" not in r:
                r["result"] = True
            return r

    log.debug("No split or merge action necessary")
    r["result"] = False
    return r


def list_streams(region=None, key=None, keyid=None, profile=None):
    """
    Return a list of all streams visible to the current account

    CLI example:

    .. code-block:: bash

        salt myminion boto_kinesis.list_streams
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    streams = []
    exclusive_start_stream_name = ""
    while exclusive_start_stream_name is not None:
        args = (
            {"ExclusiveStartStreamName": exclusive_start_stream_name}
            if exclusive_start_stream_name
            else {}
        )
        ret = _execute_with_retries(conn, "list_streams", **args)
        if "error" in ret:
            return ret
        ret = ret["result"] if ret and ret.get("result") else {}
        streams += ret.get("StreamNames", [])
        exclusive_start_stream_name = (
            streams[-1] if ret.get("HasMoreStreams", False) in (True, "true") else None
        )
    return {"result": streams}


def _get_next_open_shard(stream_details, shard_id):
    """
    Return the next open shard after shard_id

    CLI example::

        salt myminion boto_kinesis._get_next_open_shard existing_stream_details shard_id
    """
    found = False
    for shard in stream_details["OpenShards"]:
        current_shard_id = shard["ShardId"]
        if current_shard_id == shard_id:
            found = True
            continue
        if found:
            return current_shard_id


def _execute_with_retries(conn, function, **kwargs):
    """
    Retry if we're rate limited by AWS or blocked by another call.
    Give up and return error message if resource not found or argument is invalid.

    conn
        The connection established by the calling method via _get_conn()

    function
        The function to call on conn. i.e. create_stream

    **kwargs
        Any kwargs required by the above function, with their keywords
        i.e. StreamName=stream_name

    Returns:
        The result dict with the HTTP response and JSON data if applicable
        as 'result', or an error as 'error'

    CLI example::

        salt myminion boto_kinesis._execute_with_retries existing_conn function_name function_kwargs

    """
    r = {}
    max_attempts = 18
    max_retry_delay = 10
    for attempt in range(max_attempts):
        log.info("attempt: %s function: %s", attempt, function)
        try:
            fn = getattr(conn, function)
            r["result"] = fn(**kwargs)
            return r
        except botocore.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            if (
                "LimitExceededException" in error_code
                or "ResourceInUseException" in error_code
            ):
                # could be rate limited by AWS or another command is blocking,
                # retry with exponential backoff
                log.debug("Retrying due to AWS exception", exc_info=True)
                time.sleep(_jittered_backoff(attempt, max_retry_delay))
            else:
                # ResourceNotFoundException or InvalidArgumentException
                r["error"] = e.response["Error"]
                log.error(r["error"])
                r["result"] = None
                return r

    r["error"] = "Tried to execute function {0} {1} times, but was unable".format(
        function, max_attempts
    )
    log.error(r["error"])
    return r


def _jittered_backoff(attempt, max_retry_delay):
    """
    Basic exponential backoff

    CLI example::

        salt myminion boto_kinesis._jittered_backoff current_attempt_number max_delay_in_seconds
    """
    return min(random.random() * (2 ** attempt), max_retry_delay)
