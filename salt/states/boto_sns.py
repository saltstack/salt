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
        boto_sns.present:
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    # Using a profile from pillars
    mytopic:
        boto_sns.present:
            - region: us-east-1
            - profile: mysnsprofile

    # Passing in a profile
    mytopic:
        boto_sns.present:
            - region: us-east-1
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''
from __future__ import absolute_import, print_function, unicode_literals

# Standard Libs
import re


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_sns' if 'boto_sns.exists' in __salt__ else False


def present(
        name,
        subscriptions=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the SNS topic exists.

    name
        Name of the SNS topic.

    subscriptions
        List of SNS subscriptions.

        Each subscription is a dictionary with a protocol and endpoint key:

        .. code-block:: python

            [
            {'protocol': 'https', 'endpoint': 'https://www.example.com/sns-endpoint'},
            {'protocol': 'sqs', 'endpoint': 'arn:aws:sqs:us-west-2:123456789012:MyQueue'}
            ]

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
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    is_present = __salt__['boto_sns.exists'](
        name, region=region, key=key, keyid=keyid, profile=profile
    )
    if is_present:
        ret['result'] = True
        ret['comment'] = 'AWS SNS topic {0} present.'.format(name)
    else:
        if __opts__['test']:
            msg = 'AWS SNS topic {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret

        created = __salt__['boto_sns.create'](
            name, region=region, key=key, keyid=keyid, profile=profile
        )
        if created:
            msg = 'AWS SNS topic {0} created.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = {'topic': name, 'subscriptions': []}
            ret['result'] = True
        else:
            ret['comment'] = 'Failed to create {0} AWS SNS topic'.format(name)
            ret['result'] = False
            return ret

    if not subscriptions:
        return ret

    # Get current subscriptions
    _subscriptions = __salt__['boto_sns.get_all_subscriptions_by_topic'](
        name, region=region, key=key, keyid=keyid, profile=profile
    )

    # Convert subscriptions into a data strucure we can compare against
    _subscriptions = [
        {'protocol': s['Protocol'], 'endpoint': s['Endpoint']}
        for s in _subscriptions
    ]

    for subscription in subscriptions:
        # If the subscription contains inline digest auth, AWS will *** the
        # password. So we need to do the same with ours if the regex matches
        # Example: https://user:****@my.endpoiint.com/foo/bar
        _endpoint = subscription['endpoint']
        matches = re.search(
            r'https://(?P<user>\w+):(?P<pass>\w+)@',
            _endpoint)

        # We are using https and have auth creds - the password will be starred out,
        # so star out our password so we can still match it
        if matches is not None:
            subscription['endpoint'] = _endpoint.replace(
                matches.groupdict()['pass'],
                '****')

        if subscription not in _subscriptions:
            # Ensure the endpoint is set back to it's original value,
            # incase we starred out a password
            subscription['endpoint'] = _endpoint

            if __opts__['test']:
                msg = ' AWS SNS subscription {0}:{1} to be set on topic {2}.'\
                    .format(
                        subscription['protocol'],
                        subscription['endpoint'],
                        name)
                ret['comment'] += msg
                ret['result'] = None
                continue

            created = __salt__['boto_sns.subscribe'](
                name, subscription['protocol'], subscription['endpoint'],
                region=region, key=key, keyid=keyid, profile=profile)
            if created:
                msg = ' AWS SNS subscription {0}:{1} set on topic {2}.'\
                      .format(subscription['protocol'],
                              subscription['endpoint'],
                              name)
                ret['comment'] += msg
                ret['changes'].setdefault('old', None)
                ret['changes']\
                    .setdefault('new', {})\
                    .setdefault('subscriptions', [])\
                    .append(subscription)
                ret['result'] = True
            else:
                ret['result'] = False
                return ret
        else:
            msg = ' AWS SNS subscription {0}:{1} already set on topic {2}.'\
                .format(
                    subscription['protocol'],
                    subscription['endpoint'],
                    name)
            ret['comment'] += msg
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None,
        unsubscribe=False):
    '''
    Ensure the named sns topic is deleted.

    name
        Name of the SNS topic.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.

    unsubscribe
        If True, unsubscribe all subcriptions to the SNS topic before
        deleting the SNS topic

        .. versionadded:: 2016.11.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['boto_sns.exists'](
        name, region=region, key=key, keyid=keyid, profile=profile
    )

    if is_present:
        subscriptions = __salt__['boto_sns.get_all_subscriptions_by_topic'](
            name, region=region, key=key, keyid=keyid, profile=profile
        ) if unsubscribe else []
        failed_unsubscribe_subscriptions = []

        if __opts__.get('test'):
            ret['comment'] = (
                'AWS SNS topic {0} is set to be removed.  '
                '{1} subscription(s) will be removed.'.format(name, len(subscriptions))
            )
            ret['result'] = None
            return ret

        for subscription in subscriptions:
            unsubscribed = __salt__['boto_sns.unsubscribe'](
                name, subscription['SubscriptionArn'], region=region,
                key=key, keyid=keyid, profile=profile
            )
            if unsubscribed is False:
                failed_unsubscribe_subscriptions.append(subscription)

        deleted = __salt__['boto_sns.delete'](
            name, region=region, key=key, keyid=keyid, profile=profile)
        if deleted:
            ret['comment'] = 'AWS SNS topic {0} deleted.'.format(name)
            ret['changes']['new'] = None
            if unsubscribe is False:
                ret['changes']['old'] = {'topic': name}
            else:
                ret['changes']['old'] = {'topic': name, 'subscriptions': subscriptions}
                if failed_unsubscribe_subscriptions:
                    ret['changes']['new'] = {'subscriptions': failed_unsubscribe_subscriptions}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} AWS SNS topic.'.format(name)
    else:
        ret['comment'] = 'AWS SNS topic {0} does not exist.'.format(name)

    return ret
