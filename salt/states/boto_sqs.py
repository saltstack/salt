# -*- coding: utf-8 -*-
'''
Manage SQS Queues
=================

.. versionadded:: Helium

Create and destroy SQS queues. Be aware that this interacts with Amazon's
services, and so may incur charges.

This module uses boto, which can be installed via package, or pip.

This module accepts explicit sqs credentials but can also utilize
IAM roles assigned to the instance trough Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More Information available at::

   http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

If IAM roles are not used you need to specify them either in a pillar or
in the minion's config file::

    sqs.keyid: GKTADJGHEIQSXMKKRBJ08H
    sqs.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify key, keyid and region via a profile, either
as a passed in dict, or as a string to pull from pillars or minion config:

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    myqueue:
        aws_sqs.exists:
            - region: us-east-1
            - key: GKTADJGHEIQSXMKKRBJ08H
            - keyid: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            - attributes:
                ReceiveMessageWaitTimeSeconds: 20

    # Using a profile from pillars
    myqueue:
        aws_sqs.exists:
            - region: us-east-1
            - profile: mysqsprofile

    # Passing in a profile
    myqueue:
        aws_sqs.exists:
            - region: us-east-1
            - profile:
                key: GKTADJGHEIQSXMKKRBJ08H
                keyid: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''


def __virtual__():
    '''
    Only load if aws is available.
    '''
    return 'boto_sqs' if 'boto_sqs.exists' in __salt__ else False


def created(
        name,
        attributes={},
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Ensure the SQS queue exists.

    name
        Name of the SQS queue.

    region
        Region to create the queue

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_created = __salt__['boto_sqs.exists'](name, region, key, keyid, profile)

    if not is_created:
        ret['comment'] = 'AWS SQS queue {0} is set to be created.'.format(name)
        if __opts__['test']:
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
    for attr, val in attributes.iteritems():
        _val = _attributes.get(attr, None)
        if str(_val) != str(val):
            attrs_to_set[attr] = val
    attr_names = ','.join(attrs_to_set.keys())
    if attrs_to_set:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Attribute(s) {0} to be set on {1}.'.format(
                attr_names, name)
            return ret
        msg = (' Setting {0} attribute(s).'.format(attr_names))
        ret['comment'] = ret['comment'] + msg
        ret['result'] = True
        if 'new' in ret['changes']:
            ret['changes']['new']['attributes_set'] = []
        else:
            ret['changes']['new'] = {'attributes_set': []}
        for attr, val in attrs_to_set.iteritems():
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


def deleted(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None):
    '''
    Delete the named SQS queue if it exists.

    name
        Name of the SQS queue.

    region
        Region to remove the queue from

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string)
        that contains a dict with region, key and keyid.
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    is_created = __salt__['boto_sqs.exists'](name, region, key, keyid, profile)

    if is_created:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'AWS SQS queue {0} is set to be removed.'.format(
                name)
            return ret
        deleted = __salt__['boto_sqs.delete'](name, region, key, keyid,
                                              profile)
        if deleted:
            ret['result'] = True
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to remove {0} sqs queue.'.format(name)
    else:
        ret['comment'] = '{0} does not exist in {1}.'.format(name, region)

    return ret
