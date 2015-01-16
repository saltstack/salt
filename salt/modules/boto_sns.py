# -*- coding: utf-8 -*-
'''
Connection module for Amazon SNS

:configuration: This module accepts explicit sns credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles. Dynamic
    credentials are then automatically obtained from AWS API and no further
    configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        sns.keyid: GKTADJGHEIQSXMKKRBJ08H
        sns.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        sns.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto
'''
from __future__ import absolute_import

import logging

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.sns
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six import string_types


def __virtual__():
    '''
    Only load if boto libraries exist.
    '''
    if not HAS_BOTO:
        return False
    return True


def get_all_topics(region=None, key=None, keyid=None, profile=None):
    '''
    Returns a list of the all topics..

    CLI example::

        salt myminion boto_sns.get_all_topics
    '''
    cache_key = 'boto_sns.topics_cache'
    try:
        return __context__[cache_key]
    except KeyError:
        pass

    conn = _get_conn(region, key, keyid, profile)
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
        return name in topics.values()
    else:
        return name in topics.keys()


def create(name, region=None, key=None, keyid=None, profile=None):
    '''
    Create an SNS topic.

    CLI example to create a topic::

        salt myminion boto_sns.create mytopic region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    conn.create_topic(name)
    log.info('Created SNS topic {0}'.format(name))
    return True


def delete(name, region=None, key=None, keyid=None, profile=None):
    '''
    Delete an SNS topic.

    CLI example to delete a topic::

        salt myminion boto_sns.delete mytopic region=us-east-1
    '''
    conn = _get_conn(region, key, keyid, profile)
    conn.delete_topic(get_arn(name, region, key, keyid, profile))
    log.info('Deleted SNS topic {0}'.format(name))
    return True


def get_arn(name, region=None, key=None, keyid=None, profile=None):
    '''
    Returns the full ARN for a given topic name.

    CLI example::

        salt myminion boto_sns.get_arn mytopic
    '''
    if name.startswith('arn:aws:sns:'):
        return name
    account_id = __salt__['boto_iam.get_account_id']()
    return 'arn:aws:sns:{0}:{1}:{2}'.format(_get_region(region), account_id,
                                            name)


def _get_region(region=None):
    if not region and __salt__['config.option']('sns.region'):
        region = __salt__['config.option']('sns.region')
    if not region:
        region = 'us-east-1'
    return region


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to SNS.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    region = _get_region(region)

    if not key and __salt__['config.option']('sns.key'):
        key = __salt__['config.option']('sns.key')
    if not keyid and __salt__['config.option']('sns.keyid'):
        keyid = __salt__['config.option']('sns.keyid')

    conn = boto.sns.connect_to_region(region,
                                      aws_access_key_id=keyid,
                                      aws_secret_access_key=key)
    return conn
