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

    exists = __salt__['boto_vpc.exists'](name=name, tags=tags, region=region,
                                         key=key, keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'VPC {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create'](cidr_block, instance_tenancy,
                                              name, dns_support, dns_hostnames,
                                              tags, region, key, keyid,
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
    ret['comment'] = 'VPC present.'
    return ret


def subnet_present(name, vpc_id, cidr_block, availability_zone=None, tags=None, region=None,
                   key=None, keyid=None, profile=None):
    '''
    Ensure subnet exists.
    .. versionadded:: Beryllium

    name
        Name of the subnet.

    vpc_id
        The ID of the VPC where you want to create the subnet.

    cidr_block
        The range of IPs in CIDR format, for example: 10.0.0.0/24. Block
        size must be between /16 and /28 netmask.


    availability_zone
        The AZ you want the subnet in.

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

    exists = __salt__['boto_vpc.subnet_exists'](name=name, cidr=cidr_block, zones=availability_zone,
                                                tags=tags, region=region, key=key, keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Subnet {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create_subnet'](vpc_id, cidr_block, availability_zone, name,
                                                     tags, region, key, keyid, profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} subnet.'.format(name)
            return ret
        _describe = __salt__['boto_vpc.describe_subnets'](subnet_ids=[created], region=region, key=key, keyid=keyid,
                                                          profile=profile)
        ret['changes']['old'] = {'subnet': None}
        ret['changes']['new'] = {'subnet': _describe}
        ret['comment'] = 'Subnet {0} created.'.format(name)
        return ret
    ret['comment'] = 'Subnet present.'
    return ret


def absent(name, tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure VPC with passed properties is absent.

    name
        Name of the VPC.

    tags
        A list of tags. All tags must match.

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

    vpc_id = __salt__['boto_vpc.get_id'](name=name, tags=tags, region=region,
                                         key=key, keyid=keyid, profile=profile)
    if not vpc_id:
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
    ret['changes']['old'] = {'vpc': vpc_id}
    ret['changes']['new'] = {'vpc': None}
    ret['comment'] = 'VPC {0} deleted.'.format(name)
    return ret


def subnet_present(name, cidr_block, vpc_name=None, vpc_id=None,
                   availability_zone=None, tags=None, region=None,
                   key=None, keyid=None, profile=None):
    '''
    Ensure a subnet exists.

    name
        Name of the subnet.

    cidr_block
        The range if IPs for the subnet, in CIDR format. For example:
        10.0.0.0/24. Block size must be between /16 and /28 netmask.

    vpc_name
        Name of the VPC in which the subnet should be placed. Either
        vpc_name or vpc_id must be provided.

    vpc_id
        Id of the VPC in which the subnet should be placed. Either vpc_name
        or vpc_id must be provided.

    availability_zone
        AZ in which the subnet should be placed.

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

    exists = __salt__['boto_vpc.subnet_exists'](subnet_name=name, tags=tags,
                                                region=region, key=key,
                                                keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Subnet {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create_subnet'](subnet_name=name,
                                                     cidr_block=cidr_block,
                                                     availability_zone=availability_zone,
                                                     vpc_name=vpc_name, vpc_id=vpc_id,
                                                     tags=tags, region=region,
                                                     key=key, keyid=keyid,
                                                     profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create {0} subnet.'.format(name)
            return ret
        ret['changes']['old'] = {'vpc': None}
        ret['changes']['new'] = {'vpc': created}
        ret['comment'] = 'Subnet {0} created.'.format(name)
        return ret
    ret['comment'] = 'Subnet present.'
    return ret



def subnet_absent(name=None, subnet_id=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure subnet with passed properties is absent.
    .. versionadded:: Beryllium

    name
        Name of the subnet.

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

    subnet_id = __salt__['boto_vpc.get_resource_id']('subnet', name=name,
                                                     region=region, key=key,
                                                     keyid=keyid, profile=profile)
    if not subnet_id:
        ret['comment'] = '{0} subnet does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Subnet {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_vpc.delete_subnet'](subnet_name=name,
                                                 region=region, key=key,
                                                 keyid=keyid, profile=profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete {0} subnet.'.format(name)
        return ret
    ret['changes']['old'] = {'subnet': subnet_id}
    ret['changes']['new'] = {'subnet': None}
    ret['comment'] = 'Subnet {0} deleted.'.format(name)
    return ret


def internet_gateway_present(name, vpc_name=None, vpc_id=None,
                             tags=None, region=None, key=None,
                             keyid=None, profile=None):
    '''
    Ensure an internet gateway exists.

    name
        Name of the internet gateway.

    vpc_name
        Name of the VPC to which the internet gateway should be attached.

    vpc_id
        Id of the VPC to which the internet_gateway should be attached.
        Only one of vpc_name or vpc_id may be provided.

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

    exists = __salt__['boto_vpc.resource_exists']('internet_gateway', name=name,
                                                  region=region, key=key,
                                                  keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Internet gateway {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create_internet_gateway'](internet_gateway_name=name,
                                                               vpc_name=vpc_name, vpc_id=vpc_id,
                                                               tags=tags, region=region,
                                                               key=key, keyid=keyid,
                                                               profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create internet gateway {0}.'.format(name)
            return ret

        ret['changes']['old'] = {'internet_gateway': None}
        ret['changes']['new'] = {'internet_gateway': created}
        ret['comment'] = 'Internet gateway {0} created.'.format(name)
        return ret
    ret['comment'] = 'Internet gateway {0} present.'.format(name)
    return ret


def internet_gateway_absent(name, detach=False, region=None,
                            key=None, keyid=None, profile=None):
    '''
    Ensure the named internet gateway is absent.

    name
        Name of the internet gateway.

    detach
        First detach the internet gateway from a VPC, if attached.

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

    igw_id = __salt__['boto_vpc.get_resource_id']('internet_gateway', name=name,
                                                  region=region, key=key,
                                                  keyid=keyid, profile=profile)
    if not igw_id:
        ret['comment'] = 'Internet gateway {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Internet gateway {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_vpc.delete_internet_gateway'](internet_gateway_name=name,
                                                           detach=detach, region=region,
                                                           key=key, keyid=keyid,
                                                           profile=profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete internet gateway {0}.'.format(name)
        return ret
    ret['changes']['old'] = {'internet_gateway': igw_id}
    ret['changes']['new'] = {'internet_gateway': None}
    ret['comment'] = 'Internet gateway {0} deleted.'.format(name)
    return ret


def route_table_present(name, vpc_name=None, vpc_id=None,
                        tags=None, region=None, key=None,
                        keyid=None, profile=None):
    '''
    Ensure the named route table exists.

    name
        Name of the route table.

    vpc_name
        Name of the VPC with which the route table should be associated.

    vpc_id
        Id of the VPC with which the route table should be associated.
        Either vpc_name or vpc_id must be provided.

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

    exists = __salt__['boto_vpc.resource_exists']('route_table', name=name,
                                                  region=region, key=key,
                                                  keyid=keyid, profile=profile)
    if not exists:
        if __opts__['test']:
            ret['comment'] = 'Route table {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create_route_table'](route_table_name=name,
                                                          vpc_name=vpc_name, vpc_id=vpc_id,
                                                          tags=tags, region=region,
                                                          key=key, keyid=keyid,
                                                          profile=profile)
        if not created:
            ret['result'] = False
            ret['comment'] = 'Failed to create route table {0}.'.format(name)
            return ret

        ret['changes']['old'] = {'route_table': None}
        ret['changes']['new'] = {'route_table': created}
        ret['comment'] = 'Route table {0} created.'.format(name)
        return ret
    ret['comment'] = 'Route table {0} present.'.format(name)
    return ret


def route_table_absent(name, detach=False, region=None,
                       key=None, keyid=None, profile=None):
    '''
    Ensure the named route table is absent.

    name
        Name of the route table.

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

    rtbl_id = __salt__['boto_vpc.get_resource_id']('route_table', name=name,
                                                   region=region, key=key,
                                                   keyid=keyid, profile=profile)
    if not rtbl_id:
        ret['comment'] = 'Route table {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Route table {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    deleted = __salt__['boto_vpc.delete_route_table'](route_table_name=name,
                                                      region=region,
                                                      key=key, keyid=keyid,
                                                      profile=profile)
    if not deleted:
        ret['result'] = False
        ret['comment'] = 'Failed to delete route table {0}.'.format(name)
        return ret
    ret['changes']['old'] = {'route_table': rtbl_id}
    ret['changes']['new'] = {'route_table': None}
    ret['comment'] = 'Route table {0} deleted.'.format(name)
    return ret
