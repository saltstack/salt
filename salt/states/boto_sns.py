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
from __future__ import absolute_import


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_sns' if 'boto_sns.exists' in __salt__ else False


def present(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the SNS topic exists.

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
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['boto_sns.exists'](name, region, key, keyid, profile)
    if is_present:
        ret['comment'] = 'AWS SNS topic {0} present.'.format(name)
    else:
        if __opts__['test']:
            msg = 'AWS SNS topic {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret

        created = __salt__['boto_sns.create'](name, region, key, keyid,
                                              profile)
        if created:
            msg = 'AWS SNS topic {0} created.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = {'topic': name}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} AWS SNS topic'.format(name)
            return ret

    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
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
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_present = __salt__['boto_sns.exists'](name, region, key, keyid, profile)

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'AWS SNS topic {0} is set to be removed.'.format(
                name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_sns.delete'](name, region, key, keyid,
                                              profile)
        if deleted:
            ret['comment'] = 'AWS SNS topic {0} does not exist.'.format(name)
            ret['changes']['old'] = {'topic': name}
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} AWS SNS topic.'.format(name)
    else:
        ret['comment'] = 'AWS SNS topic {0} does not exist.'.format(name)

    return ret
