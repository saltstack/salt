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
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import difflib
import logging

# Import Salt libs
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


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
        profile=None,
):
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
    ret = {
        'name': name,
        'result': True,
        'comment': [],
        'changes': {},
    }

    r = __salt__['boto_sqs.exists'](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'].append(r['error'])
        return ret

    if r['result']:
        ret['comment'].append('SQS queue {0} present.'.format(name))
    else:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'].append(
                'SQS queue {0} is set to be created.'.format(name),
            )
            ret['pchanges'] = {'old': None, 'new': name}
            return ret

        r = __salt__['boto_sqs.create'](
            name,
            attributes=attributes,
            region=region,
            key=key,
            keyid=keyid,
            profile=profile,
        )
        if 'error' in r:
            ret['result'] = False
            ret['comment'].append(
                'Failed to create SQS queue {0}: {1}'.format(name, r['error']),
            )
            return ret

        ret['comment'].append('SQS queue {0} created.'.format(name))
        ret['changes']['old'] = None
        ret['changes']['new'] = name
        # Return immediately, as the create call also set all attributes
        return ret

    if not attributes:
        return ret

    r = __salt__['boto_sqs.get_attributes'](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'].append(
            'Failed to get queue attributes: {0}'.format(r['error']),
        )
        return ret
    current_attributes = r['result']

    attrs_to_set = {}
    for attr, val in six.iteritems(attributes):
        _val = current_attributes.get(attr, None)
        if attr == 'Policy':
            # Normalize by brute force
            if isinstance(_val, six.string_types):
                _val = salt.utils.json.loads(_val)
            if isinstance(val, six.string_types):
                val = salt.utils.json.loads(val)
            if _val != val:
                log.debug('Policies differ:\n%s\n%s', _val, val)
                attrs_to_set[attr] = salt.utils.json.dumps(val, sort_keys=True)
        elif six.text_type(_val) != six.text_type(val):
            log.debug('Attributes differ:\n%s\n%s', _val, val)
            attrs_to_set[attr] = val
    attr_names = ', '.join(attrs_to_set)

    if not attrs_to_set:
        ret['comment'].append('Queue attributes already set correctly.')
        return ret

    final_attributes = current_attributes.copy()
    final_attributes.update(attrs_to_set)

    def _yaml_safe_dump(attrs):
        '''
        Safely dump YAML using a readable flow style
        '''
        dumper = __utils__['yaml.get_dumper']('IndentedSafeOrderedDumper')
        return __utils__['yaml.dump'](
            attrs,
            default_flow_style=False,
            Dumper=dumper)

    attributes_diff = ''.join(difflib.unified_diff(
        _yaml_safe_dump(current_attributes).splitlines(True),
        _yaml_safe_dump(final_attributes).splitlines(True),
    ))

    if __opts__['test']:
        ret['result'] = None
        ret['comment'].append(
            'Attribute(s) {0} set to be updated:\n{1}'.format(
                attr_names,
                attributes_diff,
            )
        )
        ret['pchanges'] = {'attributes': {'diff': attributes_diff}}
        return ret

    r = __salt__['boto_sqs.set_attributes'](
        name,
        attrs_to_set,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'].append(
            'Failed to set queue attributes: {0}'.format(r['error']),
        )
        return ret

    ret['comment'].append(
        'Updated SQS queue attribute(s) {0}.'.format(attr_names),
    )
    ret['changes']['attributes'] = {'diff': attributes_diff}
    return ret


def absent(
        name,
        region=None,
        key=None,
        keyid=None,
        profile=None,
):
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

    r = __salt__['boto_sqs.exists'](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = six.text_type(r['error'])
        return ret

    if not r['result']:
        ret['comment'] = 'SQS queue {0} does not exist in {1}.'.format(
            name,
            region,
        )
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'SQS queue {0} is set to be removed.'.format(name)
        ret['pchanges'] = {'old': name, 'new': None}
        return ret

    r = __salt__['boto_sqs.delete'](
        name,
        region=region,
        key=key,
        keyid=keyid,
        profile=profile,
    )
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = six.text_type(r['error'])
        return ret

    ret['comment'] = 'SQS queue {0} was deleted.'.format(name)
    ret['changes']['old'] = name
    ret['changes']['new'] = None
    return ret
