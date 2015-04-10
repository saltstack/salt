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


def route_table_present(name, vpc_name=None, vpc_id=None, routes=None, subnets=None, tags=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Ensure route table with routes exists and is associated to a VPC.
    .. versionadded:: Beryllium

    name
        Name of the route table.

    vpc_name
        Name of the VPC with which the route table should be associated.

    vpc_id
        Id of the VPC with which the route table should be associated.
        Either vpc_name or vpc_id must be provided.

    routes
        A list of route lists; example:
            [
                ['172.31.0.0/16', 'local', 'None', 'None'],
                ['0.0.0.0/0', 'igw-0add326b', 'None', 'None']
            ]

    subnets
        A list of subnets lists; example:
            [
                ['test1', 'None'],
                ['None', 'subnet-7102a3e0']
            ]

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

    _ret = _route_table_present(name=name, vpc_id=vpc_id, tags=tags, region=region, key=key,
                                keyid=keyid, profile=profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _routes_present(route_table_name=name, routes=routes, tags=tags, region=region, key=key,
                           keyid=keyid, profile=profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _subnets_present(route_table_name=name, subnets=subnets, tags=tags, region=region, key=key,
                            keyid=keyid, profile=profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    return ret


def _route_table_present(name, vpc_name=None, vpc_id=None, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    exists = __salt__['boto_vpc.resource_exists'](resource='route_table', name=name, region=region, key=key, keyid=keyid,
                                                  profile=profile)
    if not exists:
        if __opts__['test']:
            msg = 'Route table {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        created = __salt__['boto_vpc.create_route_table'](route_table_name=name, vpc_name=vpc_name, vpc_id=vpc_id, tags=tags,
                                                          region=region, key=key, keyid=keyid, profile=profile)
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


def _routes_present(route_table_name, routes, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': route_table_name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    route_table = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region,
                                                            key=key, keyid=keyid, profile=profile)
    if not route_table:
        msg = 'Could not retrieve configuration for route table {0}.'.format(route_table_name)
        ret['comment'] = msg
        ret['result'] = False
        return ret
    if not routes:
        routes = []
    else:
        route_keys = ['gateway_id', 'instance_id', 'destination_cidr_block', 'interface_id']
        for route in routes:
            for r_key in route_keys:
                route.setdefault(r_key, None)
    to_delete = []
    to_create = []
    for route in routes:
        if dict(route) not in route_table['routes']:
            to_create.append(dict(route))
    for route in route_table['routes']:
        if route not in routes:
            if route['gateway_id'] != 'local':
                to_delete.append(route)
    if to_create or to_delete:
        if __opts__['test']:
            msg = 'Route table {0} set to have routes modified.'.format(route_table_name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            for r in to_delete:
                deleted = __salt__['boto_vpc.delete_route'](route_table['id'], r['destination_cidr_block'], region, key, keyid,
                                                            profile)
                if not deleted:
                    msg = 'Failed to delete route {0} from route table {1}.'.format(r['destination_cidr_block'],
                                                                                    route_table_name)
                    ret['comment'] = msg
                    ret['result'] = False
                ret['comment'] = 'Deleted route {0} from route table {1}.'.format(r['destination_cidr_block'], route_table_name)
        if to_create:
            for r in to_create:
                created = __salt__['boto_vpc.create_route'](route_table_id=route_table['id'], region=region, key=key,
                                                            keyid=keyid, profile=profile, **r)
                if not created:
                    msg = 'Failed to create route {0} in route table {1}.'.format(r['destination_cidr_block'], route_table_name)
                    ret['comment'] = msg
                    ret['result'] = False
                ret['comment'] = 'Created route {0} in route table {1}.'.format(r['destination_cidr_block'], route_table_name)
        ret['changes']['old'] = {'routes': route_table['routes']}
        route = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region, key=key,
                                                          keyid=keyid, profile=profile)
        ret['changes']['new'] = {'routes': route['routes']}
    return ret


def _subnets_present(route_table_name, subnets, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': route_table_name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    # Describe routing table
    route_table = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region,
                                                            key=key, keyid=keyid, profile=profile)
    if not route_table:
        msg = 'Could not retrieve configuration for route table {0}.'.format(route_table_name)
        ret['comment'] = msg
        ret['result'] = False
        return ret
    # Describe all subnets
    all_subnets = __salt__['boto_vpc.describe_subnets'](region=region, key=key, keyid=keyid, profile=profile)
    if not all_subnets:
        msg = 'Could not retrieve subnets.'
        ret['comment'] = msg
        ret['result'] = False
        return ret
    # Build subnets list with default keys from Salt
    if not subnets:
        subnets = []
    else:
        subnet_keys = ['name', 'id', 'subnet_id']
        for subnet in subnets:
            for s_key in subnet_keys:
                subnet.setdefault(s_key, None)
    # Build subnets list which are associated with route table
    route_subnets = []
    for assoc in route_table['associations']:
        for subnet in all_subnets:
            if subnet['id'] == assoc['subnet_id']:
                route_subnets.append({'id': assoc['id'], 'subnet_id': assoc['subnet_id'], 'name': subnet['tags']['Name']})
    # Build list of subnets to be associated
    to_create = filter(lambda x: not any(set(dict(x).items()) & set(dict(f).items()) for f in route_subnets), subnets)
    # Update list of subnets to be associated (add subnet_id if missing)
    for item in to_create:
        if item['subnet_id'] is None:
            for subnet in all_subnets:
                if subnet['tags']['Name'] == item['name']:
                    item['subnet_id'] = subnet['id']
    # Build list of subnets to be disassociated
    to_delete = filter(lambda x: not any(set(x.items()) & set(dict(f).items()) for f in subnets), route_subnets)
    if to_create or to_delete:
        if __opts__['test']:
            msg = 'Subnet associations for route table {0} set to be modified.'.format(route_table_name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            for s in to_delete:
                for rs in route_subnets:
                    if rs['subnet_id'] == s['subnet_id']:
                        r_asc = rs['id']
                deleted = __salt__['boto_vpc.disassociate_route_table'](r_asc, region, key, keyid, profile)
                if not deleted:
                    msg = 'Failed to dissociate {0} from route table {1}.'.format(r_asc, route_table_name)
                    ret['comment'] = msg
                    ret['result'] = False
                ret['comment'] = 'Dissociated subnet {0} from route table {1}.'.format(r_asc, route_table_name)
        if to_create:
            for r in to_create:
                created = __salt__['boto_vpc.associate_route_table'](route_table_id=route_table['id'],
                                                                     subnet_id=r['subnet_id'], region=region, key=key,
                                                                     keyid=keyid, profile=profile)
                if not created:
                    msg = 'Failed to associate subnet {0} with route table {1}.'.format(r['name'], route_table_name)
                    ret['comment'] = msg
                    ret['result'] = False
                ret['comment'] = 'Assiciated subnet {0} with route table {1}.'.format(r['name'], route_table_name)
        ret['changes']['old'] = {'subnets_associations': route_table['associations']}
        new_sub = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region, key=key,
                                                            keyid=keyid, profile=profile)
        ret['changes']['new'] = {'subnets_associations': new_sub['associations']}
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
