# -*- coding: utf-8 -*-
'''
Connection module for Amazon SNS

:configuration: This module accepts explicit sns credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles. Dynamic
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
'''
# keep lint from choking on _get_conn and _cache_id
#pylint: disable=E0602

from __future__ import absolute_import

import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    #pylint: disable=unused-import
    import boto
    import boto.sns
    #pylint: enable=unused-import
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    __utils__['boto.assign_funcs'](__name__, 'sns', pack=__salt__)
    return True


def get_all_topics(region=None, key=None, keyid=None, profile=None):
    '''
    Returns a list of the all topics..

    CLI example::

        salt myminion boto_sns.get_all_topics
    '''
    cache_key = _cache_get_key()
    try:
        return __context__[cache_key]
    except KeyError:
        pass

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    __context__[cache_key] = {}
    # TODO: support >100 SNS topics (via NextToken)
    topics = conn.get_all_topics()
    for t in topics['ListTopicsResponse']['ListTopicsResult']['Topics']:
        short_name = t['TopicArn'].split(':')[-1]
        __context__[cache_key][short_name] = t['TopicArn']
    return __context__[cache_key]


def exists(name, region=None, key=None, keyid=None, profile=None):
    '''
    Check to see if an SNS topic exists.

    CLI example::

        salt myminion boto_sns.exists mytopic region=us-east-1
    '''
    topics = get_all_topics(region=region, key=key, keyid=keyid,
                            profile=profile)
    if name.startswith('arn:aws:sns:'):
        return name in list(topics.values())
    else:
        return name in list(topics.keys())


def create(name, region=None, key=None, keyid=None, profile=None):
    '''
    Create an SNS topic.

    CLI example to create a topic::

        salt myminion boto_sns.create mytopic region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    conn.create_topic(name)
    log.info('Created SNS topic {0}'.format(name))
    _invalidate_cache()
    return True


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an SNS topic.

    CLI example to delete a topic::

        salt myminion boto_sns.delete mytopic region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    conn.delete_topic(get_arn(name, region, key, keyid, profile))
    log.info('Deleted SNS topic {0}'.format(name))
    _invalidate_cache()
    return True


def get_all_subscriptions_by_topic(name, region=None, key=None, keyid=None, profile=None):
    '''
    Get list of all subscriptions to a specific topic.

    CLI example to delete a topic::

        salt myminion boto_sns.get_all_subscriptions_by_topic mytopic region=us-east-1
    '''
    cache_key = _subscriptions_cache_key(name)
    try:
        return __context__[cache_key]
    except KeyError:
        pass

    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    ret = conn.get_all_subscriptions_by_topic(get_arn(name, region, key, keyid, profile))
    __context__[cache_key] = ret['ListSubscriptionsByTopicResponse']['ListSubscriptionsByTopicResult']['Subscriptions']
    return __context__[cache_key]


def subscribe(topic, protocol, endpoint, region=None, key=None, keyid=None, profile=None):
    '''
    Subscribe to a Topic.

    CLI example to delete a topic::

        salt myminion boto_sns.subscribe mytopic https https://www.example.com/sns-endpoint region=us-east-1
    '''
    conn = _get_conn(region=region, key=key, keyid=keyid, profile=profile)
    conn.subscribe(get_arn(topic, region, key, keyid, profile), protocol, endpoint)
    log.info('Subscribe {0} {1} to {2} topic'.format(protocol, endpoint, topic))
    try:
        del __context__[_subscriptions_cache_key(topic)]
    except KeyError:
        pass
    return True


def get_arn(name, region=None, key=None, keyid=None, profile=None):
    '''
    Returns the full ARN for a given topic name.

    CLI example::

        salt myminion boto_sns.get_arn mytopic
    '''
    if name.startswith('arn:aws:sns:'):
        return name

    account_id = __salt__['boto_iam.get_account_id'](
        region=region, key=key, keyid=keyid, profile=profile
    )
    return 'arn:aws:sns:{0}:{1}:{2}'.format(_get_region(region, profile),
                                            account_id, name)


def _get_region(region=None, profile=None):
    if profile and 'region' in profile:
        return profile['region']
    if not region and __salt__['config.option']('sns.region'):
        region = __salt__['config.option']('sns.region')
    if not region:
        region = 'us-east-1'
    return region


def _subscriptions_cache_key(name):
    return '{0}_{1}_subscriptions'.format(_cache_get_key(), name)


def _invalidate_cache():
    try:
        del __context__[_cache_get_key()]
    except KeyError:
        pass


def _cache_get_key():
    return 'boto_sns.topics_cache'
