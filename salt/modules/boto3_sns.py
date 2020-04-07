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

:depends: boto3
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
# pylint: disable=unused-import
try:
    import botocore
    import boto3
    import jmespath

    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=unused-import


def __virtual__():
    """
    Only load if boto libraries exist.
    """
    has_boto_reqs = salt.utils.versions.check_boto_reqs()
    if has_boto_reqs is True:
        __utils__["boto3.assign_funcs"](__name__, "sns")
    return has_boto_reqs


def list_topics(region=None, key=None, keyid=None, profile=None):
    """
    Returns a list of the requester's topics

    CLI example::

        salt myminion boto3_sns.list_topics
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    res = {}
    NextToken = ""
    while NextToken is not None:
        ret = conn.list_topics(NextToken=NextToken)
        NextToken = ret.get("NextToken", None)
        arns = jmespath.search("Topics[*].TopicArn", ret)
        for t in arns:
            short_name = t.split(":")[-1]
            res[short_name] = t
    return res


def describe_topic(name, region=None, key=None, keyid=None, profile=None):
    """
    Returns details about a specific SNS topic, specified by name or ARN.

    CLI example::

        salt my_favorite_client boto3_sns.describe_topic a_sns_topic_of_my_choice
    """
    topics = list_topics(region=region, key=key, keyid=keyid, profile=profile)
    ret = {}
    for topic, arn in topics.items():
        if name in (topic, arn):
            ret = {"TopicArn": arn}
            ret["Subscriptions"] = list_subscriptions_by_topic(
                arn, region=region, key=key, keyid=keyid, profile=profile
            )
            ret["Attributes"] = get_topic_attributes(
                arn, region=region, key=key, keyid=keyid, profile=profile
            )
    return ret


def topic_exists(name, region=None, key=None, keyid=None, profile=None):
    """
    Check to see if an SNS topic exists.

    CLI example::

        salt myminion boto3_sns.topic_exists mytopic region=us-east-1
    """
    topics = list_topics(region=region, key=key, keyid=keyid, profile=profile)
    return name in list(topics.values() + topics.keys())


def create_topic(Name, region=None, key=None, keyid=None, profile=None):
    """
    Create an SNS topic.

    CLI example::

        salt myminion boto3_sns.create_topic mytopic region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        ret = conn.create_topic(Name=Name)
        log.info("SNS topic %s created with ARN %s", Name, ret["TopicArn"])
        return ret["TopicArn"]
    except botocore.exceptions.ClientError as e:
        log.error("Failed to create SNS topic %s: %s", Name, e)
        return None
    except KeyError:
        log.error("Failed to create SNS topic %s", Name)
        return None


def delete_topic(TopicArn, region=None, key=None, keyid=None, profile=None):
    """
    Delete an SNS topic.

    CLI example::

        salt myminion boto3_sns.delete_topic mytopic region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.delete_topic(TopicArn=TopicArn)
        log.info("SNS topic %s deleted", TopicArn)
        return True
    except botocore.exceptions.ClientError as e:
        log.error("Failed to delete SNS topic %s: %s", name, e)
        return False


def get_topic_attributes(TopicArn, region=None, key=None, keyid=None, profile=None):
    """
    Returns all of the properties of a topic.  Topic properties returned might differ based on the
    authorization of the user.

    CLI example::

        salt myminion boto3_sns.get_topic_attributes someTopic region=us-west-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        return conn.get_topic_attributes(TopicArn=TopicArn).get("Attributes")
    except botocore.exceptions.ClientError as e:
        log.error("Failed to garner attributes for SNS topic %s: %s", TopicArn, e)
        return None


def set_topic_attributes(
    TopicArn,
    AttributeName,
    AttributeValue,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Set an attribute of a topic to a new value.

    CLI example::

        salt myminion boto3_sns.set_topic_attributes someTopic DisplayName myDisplayNameValue
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.set_topic_attributes(
            TopicArn=TopicArn,
            AttributeName=AttributeName,
            AttributeValue=AttributeValue,
        )
        log.debug(
            "Set attribute %s=%s on SNS topic %s",
            AttributeName,
            AttributeValue,
            TopicArn,
        )
        return True
    except botocore.exceptions.ClientError as e:
        log.error(
            "Failed to set attribute %s=%s for SNS topic %s: %s",
            AttributeName,
            AttributeValue,
            TopicArn,
            e,
        )
        return False


def list_subscriptions_by_topic(
    TopicArn, region=None, key=None, keyid=None, profile=None
):
    """
    Returns a list of the subscriptions to a specific topic

    CLI example::

        salt myminion boto3_sns.list_subscriptions_by_topic mytopic region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    NextToken = ""
    res = []
    try:
        while NextToken is not None:
            ret = conn.list_subscriptions_by_topic(
                TopicArn=TopicArn, NextToken=NextToken
            )
            NextToken = ret.get("NextToken", None)
            subs = ret.get("Subscriptions", [])
            res += subs
    except botocore.exceptions.ClientError as e:
        log.error("Failed to list subscriptions for SNS topic %s: %s", TopicArn, e)
        return None
    return res


def list_subscriptions(region=None, key=None, keyid=None, profile=None):
    """
    Returns a list of the requester's topics

    CLI example::

        salt myminion boto3_sns.list_subscriptions region=us-east-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    NextToken = ""
    res = []
    try:
        while NextToken is not None:
            ret = conn.list_subscriptions(NextToken=NextToken)
            NextToken = ret.get("NextToken", None)
            subs = ret.get("Subscriptions", [])
            res += subs
    except botocore.exceptions.ClientError as e:
        log.error("Failed to list SNS subscriptions: %s", e)
        return None
    return res


def get_subscription_attributes(
    SubscriptionArn, region=None, key=None, keyid=None, profile=None
):
    """
    Returns all of the properties of a subscription.

    CLI example::

        salt myminion boto3_sns.get_subscription_attributes somesubscription region=us-west-1
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        ret = conn.get_subscription_attributes(SubscriptionArn=SubscriptionArn)
        return ret["Attributes"]
    except botocore.exceptions.ClientError as e:
        log.error(
            "Failed to list attributes for SNS subscription %s: %s", SubscriptionArn, e
        )
        return None
    except KeyError:
        log.error("Failed to list attributes for SNS subscription %s", SubscriptionArn)
        return None


def set_subscription_attributes(
    SubscriptionArn,
    AttributeName,
    AttributeValue,
    region=None,
    key=None,
    keyid=None,
    profile=None,
):
    """
    Set an attribute of a subscription to a new value.

    CLI example::

        salt myminion boto3_sns.set_subscription_attributes someSubscription RawMessageDelivery jsonStringValue
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.set_subscription_attributes(
            SubscriptionArn=SubscriptionArn,
            AttributeName=AttributeName,
            AttributeValue=AttributeValue,
        )
        log.debug(
            "Set attribute %s=%s on SNS subscription %s",
            AttributeName,
            AttributeValue,
            SubscriptionArn,
        )
        return True
    except botocore.exceptions.ClientError as e:
        log.error(
            "Failed to set attribute %s=%s for SNS subscription %s: %s",
            AttributeName,
            AttributeValue,
            SubscriptionArn,
            e,
        )
        return False


def subscribe(
    TopicArn, Protocol, Endpoint, region=None, key=None, keyid=None, profile=None
):
    """
    Subscribe to a Topic.

    CLI example::

        salt myminion boto3_sns.subscribe mytopic https https://www.example.com/sns-endpoint
    """
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        ret = conn.subscribe(TopicArn=TopicArn, Protocol=Protocol, Endpoint=Endpoint)
        log.info(
            "Subscribed %s %s to topic %s with SubscriptionArn %s",
            Protocol,
            Endpoint,
            TopicArn,
            ret["SubscriptionArn"],
        )
        return ret["SubscriptionArn"]
    except botocore.exceptions.ClientError as e:
        log.error("Failed to create subscription to SNS topic %s: %s", TopicArn, e)
        return None
    except KeyError:
        log.error("Failed to create subscription to SNS topic %s", TopicArn)
        return None


def unsubscribe(SubscriptionArn, region=None, key=None, keyid=None, profile=None):
    """
    Unsubscribe a specific SubscriptionArn of a topic.

    CLI Example:

    .. code-block:: bash

        salt myminion boto3_sns.unsubscribe my_subscription_arn region=us-east-1
    """
    subs = list_subscriptions(region=region, key=key, keyid=keyid, profile=profile)
    sub = [s for s in subs if s.get("SubscriptionArn") == SubscriptionArn]
    if not sub:
        log.error("Subscription ARN %s not found", SubscriptionArn)
        return False
    TopicArn = sub[0]["TopicArn"]
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    try:
        conn.unsubscribe(SubscriptionArn=SubscriptionArn)
        log.info("Deleted subscription %s from SNS topic %s", SubscriptionArn, TopicArn)
        return True
    except botocore.exceptions.ClientError as e:
        log.error("Failed to delete subscription %s: %s", SubscriptionArn, e)
        return False
