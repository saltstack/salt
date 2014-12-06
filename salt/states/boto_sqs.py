# -*- coding: utf-8 -*-
'''
Manage SQS Queues

.. versionadded:: 2014.7.0

Create and destroy SQS queues. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit SQS credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    sqs.keyid: GKTADJGHEIQSXMKKRBJ08H
    sqs.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile, either
passed in as a dict, or as a string to pull from pillars or minion config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        region: us-east-1

.. code-block:: yaml

    myqueue:
        boto_sqs.present:
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            - attributes:
                ReceiveMessageWaitTimeSeconds: 20

    # Using a profile from pillars
    myqueue:
        boto_sqs.present:
            - region: us-east-1
            - profile: mysqsprofile

    # Passing in a profile
    myqueue:
        boto_sqs.present:
            - region: us-east-1
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''
from __future__ import absolute_import
import salt.ext.six as six


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_sqs' if 'boto_sqs.exists' in __salt__ else False


def present(
        name,
        attributes=None,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the SQS queue exists.

    name
        Name of the SQS queue.

    attributes
        A dict of key/value SQS attributes.

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

    is_present = __salt__['boto_sqs.exists'](name, region, key, keyid, profile)

    if not is_present:
        if __opts__['test']:
            msg = 'AWS SQS queue {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['boto_sqs.create'](name, region, key, keyid,
                                              profile)
        if created:
            ret['changes']['old'] = None
            ret['changes']['new'] = {'queue': name}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} AWS queue'.format(name)
            return ret
    else:
        ret['comment'] = '{0} present.'.format(name)
    attrs_to_set = {}
    _attributes = __salt__['boto_sqs.get_attributes'](name, region, key, keyid,
                                                      profile)
    if attributes:
        for attr, val in six.iteritems(attributes):
            _val = _attributes.get(attr, None)
            if str(_val) != str(val):
                attrs_to_set[attr] = val
    attr_names = ','.join(attrs_to_set)
    if attrs_to_set:
        if __opts__['test']:
            ret['comment'] = 'Attribute(s) {0} to be set on {1}.'.format(
                attr_names, name)
            ret['result'] = None
            return ret
        msg = (' Setting {0} attribute(s).'.format(attr_names))
        ret['comment'] = ret['comment'] + msg
        if 'new' in ret['changes']:
            ret['changes']['new']['attributes_set'] = []
        else:
            ret['changes']['new'] = {'attributes_set': []}
        for attr, val in six.iteritems(attrs_to_set):
            set_attr = __salt__['boto_sqs.set_attributes'](name, {attr: val},
                                                           region, key, keyid,
                                                           profile)
            if not set_attr:
                ret['result'] = False
            msg = 'Set attribute {0}.'.format(attr)
            ret['changes']['new']['attributes_set'].append(attr)
    else:
        ret['comment'] = ret['comment'] + ' Attributes set.'
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the named sqs queue is deleted.

    name
        Name of the SQS queue.

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

    is_present = __salt__['boto_sqs.exists'](name, region, key, keyid, profile)

    if is_present:
        if __opts__['test']:
            ret['comment'] = 'AWS SQS queue {0} is set to be removed.'.format(
                name)
            ret['result'] = None
            return ret
        deleted = __salt__['boto_sqs.delete'](name, region, key, keyid,
                                              profile)
        if deleted:
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to delete {0} sqs queue.'.format(name)
    else:
        ret['comment'] = '{0} does not exist in {1}.'.format(name, region)

    return ret
