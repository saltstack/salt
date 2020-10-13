# -*- coding: utf-8 -*-
"""
Connection module for Amazon SNS

:configuration: This module accepts explicit sns credentials but can also
    utilize IAM roles assigned to the instance through Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at:

    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

    .. code-block:: yaml

        sns.keyid: GKTADJGHEIQSXMKKRBJ08H
        sns.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration:

    .. code-block:: yaml

        sns.region: us-east-1

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

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.versions

log = logging.getLogger(__name__)

# Import third party libs
try:
    # pylint: disable=unused-import
    import boto3

    # pylint: enable=unused-import
    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    return salt.utils.versions.check_boto_reqs(check_boto=False)


def __init__(opts):
    if HAS_BOTO3:
        __utils__["boto3.assign_funcs"](__name__, "sns")


def get_all_topics(region=None, key=None, keyid=None, profile=None):
    """
    Returns a list of the all topics..

    CLI example::

        salt myminion boto_sns.get_all_topics
    """
    cache_key = _cache_get_key()
    try:
        return __context__[cache_key]
    except KeyError:
        pass

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    __context__[cache_key] = {}


    resp = conn.list_topics()
    for t in resp["Topics"]:
        short_name = t["TopicArn"].split(":")[-1]
        __context__[cache_key][short_name] = t["TopicArn"]

    while "NextToken" in resp:
        resp = conn.list_topics(NextToken=resp["NextToken"])
        for t in resp["Topics"]:
            short_name = t["TopicArn"].split(":")[-1]
            __context__[cache_key][short_name] = t["TopicArn"]

    return __context__[cache_key]


def exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if an SNS topic exists.

    CLI example::

        salt myminion boto_sns.exists mytopic region=us-east-1
    """
    topics = get_all_topics(region=region, key=key, keyid=keyid, profile=profile)
    if name.startswith("arn:aws:sns:"):
        return name in list(topics.values())
    else:
        return name in list(topics.keys())


def create(name, region=None, key=None, keyid=None, profile=None):
    """
    Create an SNS topic.

    CLI example to create a topic::

        salt myminion boto_sns.create mytopic region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    conn.create_topic(Name=name)
    log.info("Created SNS topic %s", name)
    _invalidate_cache()
    return True


def delete(name, region=None, key=None, keyid=None, profile=None):
    """
    Delete an SNS topic.

    CLI example to delete a topic::

        salt myminion boto_sns.delete mytopic region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.delete_topic(TopicArn=get_arn(name, region, key, keyid, profile))
        log.info("Deleted SNS topic %s", name)
        _invalidate_cache()
        return True
    except conn.exceptions.NotFoundException:
        return True
    return False


def get_all_subscriptions_by_topic(
    name, region=None, key=None, keyid=None, profile=None
):
    """
    Get list of all subscriptions to a specific topic.

    CLI example to delete a topic::

        salt myminion boto_sns.get_all_subscriptions_by_topic mytopic region=us-east-1
    """
    cache_key = _subscriptions_cache_key(name)
    try:
        return __context__[cache_key]
    except KeyError:
        pass

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    topic_arn = get_arn(name, region, key, keyid, profile)
    resp = conn.list_subscriptions_by_topic(TopicArn=topic_arn)
    __context__[cache_key] = resp["Subscriptions"]
    while "NextToken" in resp:
        resp = conn.list_subscriptions_by_topic(
            TopicArn=topic_arn, NextToken=resp["NextToken"]
        )
        __context__[cache_key].extend(resp["Subscriptions"])
    return __context__[cache_key]


def subscribe(
    topic, protocol, endpoint, region=None, key=None, keyid=None, profile=None
):
    """
    Subscribe to a Topic.

    CLI example to delete a topic::

        salt myminion boto_sns.subscribe mytopic https https://www.example.com/sns-endpoint region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        conn.subscribe(
            TopicArn=get_arn(topic, region, key, keyid, profile),
            Protocol=protocol,
            Endpoint=endpoint,
        )
        log.info("Subscribe %s %s to %s topic", protocol, endpoint, topic)
    except conn.exceptions.NotFoundException as e:
        log.error(e)
        return False

    try:
        del __context__[_subscriptions_cache_key(topic)]
    except KeyError:
        pass
    return True


def unsubscribe(
    topic, subscription_arn, region=None, key=None, keyid=None, profile=None
):
    """
    Unsubscribe a specific SubscriptionArn of a topic.

    CLI Example:

    .. code-block:: bash

        salt myminion boto_sns.unsubscribe my_subscription_arn region=us-east-1

    .. versionadded:: 2016.11.0
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)

    try:
        if subscription_arn not in get_all_subscriptions_by_topic(
            topic, region, key, keyid, profile
        ):
            return True
    except conn.exceptions.NotFoundException as e:
        return False

    try:
        conn.unsubscribe(SubscriptionArn=subscription_arn)
        log.info("Unsubscribe %s", subscription_arn)
        return True
    except (KeyError, conn.exceptions.NotFoundException) as e:
        log.debug("Unsubscribe Error", exc_info=True)
        return False


def get_arn(name, region=None, key=None, keyid=None, profile=None):
    """
    Returns the full ARN for a given topic name.

    CLI example::

        salt myminion boto_sns.get_arn mytopic
    """
    if name.startswith("arn:aws:sns:"):
        return name

    account_id = __salt__["boto_iam.get_account_id"](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return "arn:aws:sns:{0}:{1}:{2}".format(
        _get_region(region, profile), account_id, name
    )


def _get_region(region=None, profile=None):
    if profile and "region" in profile:
        return profile["region"]
    if not region and __salt__["config.option"](profile):
        _profile = __salt__["config.option"](profile)
        region = _profile.get("region", None)
    if not region and __salt__["config.option"]("sns.region"):
        region = __salt__["config.option"]("sns.region")
    if not region:
        region = "us-east-1"
    return region


def _subscriptions_cache_key(name):
    return "{0}_{1}_subscriptions".format(_cache_get_key(), name)


def _invalidate_cache():
    try:
        del __context__[_cache_get_key()]
    except KeyError:
        pass


def _cache_get_key():
    return "boto_sns.topics_cache"
