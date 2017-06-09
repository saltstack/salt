# -*- coding: utf-8 -*-
'''
Manage SNS Topics


Create and destroy SNS topics. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit AWS credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    sns.keyid: GKTADJGHEIQSXMKKRBJ08H
    sns.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    mytopic:
        boto3_sns.topic_present:
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars
    mytopic:
        boto3_sns.topic_present:
            - region: us-east-1
            - profile: mysnsprofile

    # Passing in a profile
    mytopic:
        boto3_sns.topic_present:
            - region: us-east-1
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''
from __future__ import absolute_import

import re
import logging
import json
import copy
import salt.ext.six as six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto3_sns' if 'boto3_sns.topic_exists' in __salt__ else False


def topic_present(name, subscriptions=None, attributes=None,
                  region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the SNS topic exists.

    name
        Name of the SNS topic.

    subscriptions
        List of SNS subscriptions.

        Each subscription is a dictionary with a protocol and endpoint key:

        .. code-block:: yaml

            subscriptions:
            - Protocol: https
              Endpoint: https://www.example.com/sns-endpoint
            - Protocol: sqs
              Endpoint: arn:aws:sqs:us-west-2:123456789012:MyQueue

    attributes
        Dictionary of attributes to set on the SNS topic
        Valid attribute keys are:
          - Policy:  the JSON serialization of the topic's access control policy
          - DisplayName:  the human-readable name used in the "From" field for notifications
                to email and email-json endpoints
          - DeliveryPolicy:  the JSON serialization of the topic's delivery policy

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
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    something_changed = False
    current = __salt__['boto3_sns.describe_topic'](name, region, key, keyid, profile)
    if current:
        ret['comment'] = 'AWS SNS topic {0} present.'.format(name)
        TopicArn = current['TopicArn']
    else:
        if __opts__['test']:
            ret['comment'] = 'AWS SNS topic {0} would be created.'.format(name)
            ret['result'] = None
            return ret
        else:
            TopicArn = __salt__['boto3_sns.create_topic'](name, region=region, key=key,
                                                          keyid=keyid, profile=profile)
            if TopicArn:
                ret['comment'] = 'AWS SNS topic {0} created with ARN {1}.'.format(name, TopicArn)
                something_changed = True
            else:
                ret['comment'] = 'Failed to create AWS SNS topic {0}'.format(name)
                log.error(ret['comment'])
                ret['result'] = False
                return ret

    ### Update any explicitly defined attributes
    want_attrs = attributes if attributes else {}
    # Freshen these in case we just created it above
    current_attrs = __salt__['boto3_sns.get_topic_attributes'](TopicArn, region=region, key=key,
                                                               keyid=keyid, profile=profile)
    for attr in ['DisplayName', 'Policy', 'DeliveryPolicy']:
        curr_val = current_attrs.get(attr)
        want_val = want_attrs.get(attr)
        # Some get default values if not set, so it's not safe to enforce absense if they're
        # not provided at all.  This implies that if you want to clear a value, you must explicitly
        # set it to an empty string.
        if want_val is None:
            continue
        if _json_objs_equal(want_val, curr_val):
            continue
        if __opts__['test']:
            ret['comment'] += '  Attribute {0} would be updated on topic {1}.'.format(attr, TopicArn)
            ret['result'] = None
            continue
        want_val = want_val if isinstance(want_val, six.string_types) else json.dumps(want_val)
        if __salt__['boto3_sns.set_topic_attributes'](TopicArn, attr, want_val, region=region,
                                                      key=key, keyid=keyid, profile=profile):
            ret['comment'] += '  Attribute {0} set to {1} on topic {2}.'.format(attr, want_val,
                                                                                   TopicArn)
            something_changed = True
        else:
            ret['comment'] += '  Failed to update {0} on topic {1}.'.format(attr, TopicArn)
            ret['result'] = False
            return ret

    ### Add / remove subscriptions
    want_subs = subscriptions if subscriptions else []
    obfuscated_subs = []
    current_subs = current.get('Subscriptions', [])
    current_slim = [{'Protocol': s['Protocol'], 'Endpoint': s['Endpoint']} for s in current_subs]
    subscribe = []
    unsubscribe = []
    for sub in want_subs:
        # If the subscription contains inline digest auth, AWS will obfuscate the password with
        # '****'.  Thus we need to do the same with ours to permit 1-to-1 comparison.
        # Example: https://user:****@my.endpoiint.com/foo/bar
        endpoint = sub['Endpoint']
        matches = re.search(r'https://(?P<user>\w+):(?P<pass>\w+)@', endpoint)
        if matches is not None:
            sub['Endpoint'] = endpoint.replace(':' + matches.groupdict()['pass'], ':****')
        obfuscated_subs += [copy.deepcopy(sub)]
        # Now set it back...
        if sub not in current_slim:
            sub['Endpoint'] = endpoint
            subscribe += [sub]
    for sub in current_subs:
        minimal = {'Protocol': sub['Protocol'], 'Endpoint': sub['Endpoint']}
        if minimal not in obfuscated_subs:
            unsubscribe += [sub['SubscriptionArn']]
    for sub in subscribe:
        prot = sub['Protocol']
        endp = sub['Endpoint']
        if __opts__['test']:
            msg = ' Subscription {0}:{1} would be set on topic {2}.'.format(prot, endp, TopicArn)
            ret['comment'] += msg
            ret['result'] = None
            continue
        subbed = __salt__['boto3_sns.subscribe'](TopicArn, prot, endp, region=region, key=key,
                                                 keyid=keyid, profile=profile)
        if subbed:
            msg = ' Subscription {0}:{1} set on topic {2}.'.format(prot, endp, TopicArn)
            ret['comment'] += msg
            something_changed = True
        else:
            msg = ' Failed to set subscription {0}:{1} on topic {2}.'.format(prot, endp, TopicArn)
            ret['comment'] += msg
            ret['result'] = False
            return ret
    for sub in unsubscribe:
        if __opts__['test']:
            msg = '  Subscription {0} would be removed from topic {1}.'.format(sub, TopicArn)
            ret['comment'] += msg
            ret['result'] = None
            continue
        unsubbed = __salt__['boto3_sns.unsubscribe'](sub, region=region, key=key, keyid=keyid,
                                                     profile=profile)
        if unsubbed:
            ret['comment'] += '  Subscription {0} removed from topic {1}.'.format(sub, TopicArn)
            something_changed = True
        else:
            msg = '  Failed to remove subscription {0} from topic {1}.'.format(sub, TopicArn)
            ret['comment'] += msg
            ret['result'] = False
            return ret
    if something_changed:
        ret['changes']['old'] = current
        ret['changes']['new'] = __salt__['boto3_sns.describe_topic'](name, region, key, keyid, profile)
    return ret


def topic_absent(name, unsubscribe=False, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the named sns topic is deleted.

    name
        Name of the SNS topic.

    unsubscribe
        If True, unsubscribe all subcriptions to the SNS topic before
        deleting the SNS topic

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
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    something_changed = False
    current = __salt__['boto3_sns.describe_topic'](name, region, key, keyid, profile)
    if not current:
        ret['comment'] = 'AWS SNS topic {0} absent.'.format(name)
    else:
        TopicArn = current['TopicArn']
        if __opts__['test']:
            ret['comment'] = 'AWS SNS topic {0} would be removed.'.format(TopicArn)
            if unsubscribe:
                ret['comment'] += '  {0} subscription(s) would be removed.'.format(
                        len(current['Subscriptions']))
            ret['result'] = None
            return ret
        if unsubscribe:
            for sub in current['Subscriptions']:
                if sub['SubscriptionArn'] == 'PendingConfirmation':
                    # The API won't let you delete subscriptions in pending status...
                    log.warning('Ignoring PendingConfirmation subscription {0} {1} on topic '
                                '{2}'.format(sub['Protocol'], sub['Endpoint'], sub['TopicArn']))
                    continue
                if __salt__['boto3_sns.unsubscribe'](sub['SubscriptionArn'], region=region, key=key,
                                                     keyid=keyid, profile=profile):
                    log.debug('Deleted subscription {0} for SNS topic {1}'.format(sub, TopicArn))
                    something_changed = True
                else:
                    ret['comment'] = 'Failed to delete subscription {0} for SNS topic {1}'.format(
                            sub, TopicArn)
                    ret['result'] = False
                    return ret
        if not __salt__['boto3_sns.delete_topic'](TopicArn, region=region, key=key, keyid=keyid,
                                                  profile=profile):
            ret['comment'] = 'Failed to delete SNS topic {0}'.format(TopicArn)
            log.error(ret['comment'])
            ret['result'] = False
        else:
            ret['comment'] = 'AWS SNS topic {0} deleted.'.format(TopicArn)
            if unsubscribe:
                ret['comment'] += '  '.join(['Subscription {0} deleted'.format(s)
                                              for s in current['Subscriptions']])
            something_changed = True

    if something_changed:
        ret['changes']['old'] = current
        ret['changes']['new'] = __salt__['boto3_sns.describe_topic'](name, region, key, keyid, profile)
    return ret


def _json_objs_equal(left, right):
    left = __utils__['boto3.ordered'](json.loads(left) if isinstance(left, six.string_types) else left)
    right = __utils__['boto3.ordered'](json.loads(right) if isinstance(right, six.string_types) else right)
    return left == right
