# -*- coding: utf-8 -*-
'''
Manage VPCs
=================

.. versionadded:: 2014.7.1

Create and destroy VPCs. Be aware that this interacts with Amazon's services,
and so may incur charges.

This module uses ``boto``, which can be installed via package, or pip.

This module accepts explicit vpc credentials but can also utilize
IAM roles assigned to the instance through Instance Profiles. Dynamic
credentials are then automatically obtained from AWS API and no further
configuration is necessary. More information available `here
<http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html>`_.

If IAM roles are not used you need to specify them either in a pillar file or
in the minion's config file:

.. code-block:: yaml

    vpc.keyid: GKTADJGHEIQSXMKKRBJ08H
    vpc.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

It's also possible to specify ``key``, ``keyid`` and ``region`` via a profile,
either passed in as a dict, or as a string to pull from pillars or minion
config:

.. code-block:: yaml

    myprofile:
        keyid: GKTADJGHEIQSXMKKRBJ08H
        key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

.. code-block:: yaml

    Ensure VPC exists:
        boto_vpc.present:
            - name: myvpc
            - cidr_block: 10.10.11.0/24
            - dns_hostnames: True
            - region: us-east-1
            - keyid: GKTADJGHEIQSXMKKRBJ08H
            - key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''
from salt.exceptions import SaltInvocationError
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if boto is available.
    '''
    return 'boto_vpc' if 'boto_vpc.exists' in __salt__ else False


def present(name, cidr_block, instance_tenancy=None, dns_support=None,
            dns_hostnames=None, tags=None, region=None, key=None, keyid=None,
            profile=None):
    '''
    Ensure VPC exists.

    name
        Name of the VPC.

    cidr_block
        The range of IPs in CIDR format, for example: 10.0.0.0/24. Block
        size must be between /16 and /28 netmask.

    instance_tenancy
        Instances launched in this VPC will be ingle-tenant or dedicated
        hardware.

    dns_support
        Indicates whether the DNS resolution is supported for the VPC.

    dns_hostnames
        Indicates whether the instances launched in the VPC get DNS hostnames.

    tags
        A list of tags.

    region
        Region to connect to.

    key
        Secret key to be used.

    keyid
        Access key to be used.

    profile
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    _id = {'salt_id': name}
    if tags:
        _tags = tags.update(_id)
    else:
        _tags = _id
    exists = __salt__['boto_vpc.exists'](tags=_id, region=region, key=key,
                                         keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'VPC {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create'](cidr_block, instance_tenancy,
                                              name, dns_support, dns_hostnames,
                                              _tags, region, key, keyid,
                                              profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} VPC.'.format(name)
            return ret
        _describe = __salt__['boto_vpc.describe'](created, region, key,
                                                  keyid, profile)
        ret['changes']['old'] = {'vpc': None}
        ret['changes']['new'] = {'vpc': _describe}
        ret['comment'] = 'VPC {0} created.'.format(name)
    return ret


def absent(name, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    _id = {'salt_id': name}
    if tags:
        _tags = tags.update(_id)
    else:
        _tags = _id
    exists = __salt__['boto_vpc.exists'](tags=_id, region=region, key=key,
                                         keyid=keyid, profile=profile)
    if not exists:
        ret['comment'] = '{0} VPC does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'VPC {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_vpc.delete'](name=name, tags=tags,
                                          region=region, key=key,
                                          keyid=keyid, profile=profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete {0} VPC.'.format(name)
        return ret
    ret['changes']['old'] = {'vpc': name}
    ret['changes']['new'] = {'vpc': None}
    ret['comment'] = 'VPC {0} deleted.'.format(name)
    return ret
