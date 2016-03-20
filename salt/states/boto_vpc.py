# -*- coding: utf-8 -*-
'''
Manage VPCs
=================

.. versionadded:: 2015.8.0

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

    aws:
        region:
            us-east-1:
                profile:
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

    Ensure subnet exists:
        boto_vpc.subnet_present:
            - name: mysubnet
            - vpc_id: vpc-123456
            - cidr_block: 10.0.0.0/16
            - region: us-east-1
            - profile: myprofile

    {% set profile = salt['pillar.get']('aws:region:us-east-1:profile' ) %}
    Ensure internet gateway exists:
        boto_vpc.internet_gateway_present:
            - name: myigw
            - vpc_name: myvpc
            - profile: {{ profile }}

    Ensure route table exists:
        boto_vpc.route_table_present:
            - name: my_route_table
            - vpc_id: vpc-123456
            - routes:
              - destination_cidr_block: 0.0.0.0/0
                instance_id: i-123456
            - subnet_names:
              - subnet1
              - subnet2
            - region: us-east-1
            - profile:
                keyid: GKTADJGHEIQSXMKKRBJ08H
                key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.dictupdate as dictupdate

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

    r = __salt__['boto_vpc.exists'](name=name, tags=tags, region=region,
                                    key=key, keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create VPC: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'VPC {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_vpc.create'](cidr_block, instance_tenancy=instance_tenancy, vpc_name=name,
                                        enable_dns_support=dns_support, enable_dns_hostnames=dns_hostnames,
                                        tags=tags, region=region, key=key, keyid=keyid,
                                        profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create VPC: {0}.'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_vpc.describe'](vpc_id=r['id'], region=region, key=key,
                                                  keyid=keyid, profile=profile)
        ret['changes']['old'] = {'vpc': None}
        ret['changes']['new'] = _describe
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

    r = __salt__['boto_vpc.get_id'](name=name, tags=tags, region=region,
                                    key=key, keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete VPC: {0}.'.format(r['error']['message'])
        return ret

    _id = r.get('id')
    if not _id:
        ret['comment'] = '{0} VPC does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'VPC {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_vpc.delete'](vpc_name=name, tags=tags,
                                    region=region, key=key,
                                    keyid=keyid, profile=profile)
    if not r['deleted']:
        ret['result'] = False
        ret['comment'] = 'Failed to delete VPC: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'vpc': _id}
    ret['changes']['new'] = {'vpc': None}
    ret['comment'] = 'VPC {0} deleted.'.format(name)
    return ret


def dhcp_options_present(name, dhcp_options_id=None, vpc_name=None, vpc_id=None,
                         domain_name=None, domain_name_servers=None, ntp_servers=None,
                         netbios_name_servers=None, netbios_node_type=None,
                         tags=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure a set of DHCP options with the given settings exist.
    Note that the current implementation only SETS values during option set
    creation.  It is unable to update option sets in place, and thus merely
    verifies the set exists via the given name and/or dhcp_options_id param.

    name
        (string)
        Name of the DHCP options.

    vpc_name
        (string)
        Name of a VPC to which the options should be associated.  Either
        vpc_name or vpc_id must be provided.

    vpc_id
        (string)
        Id of a VPC to which the options should be associated.  Either
        vpc_name or vpc_id must be provided.

    domain_name
        (string)
        Domain name to be assiciated with this option set.

    domain_name_servers
        (list of strings)
        The IP address(es) of up to four domain name servers.

    ntp_servers
        (list of strings)
        The IP address(es) of up to four desired NTP servers.

    netbios_name_servers
        (list of strings)
        The IP address(es) of up to four NetBIOS name servers.

    netbios_node_type
        (string)
        The NetBIOS node type (1, 2, 4, or 8).  For more information about
        the allowed values, see RFC 2132.  The recommended is 2 at this
        time (broadcast and multicast are currently not supported).

    tags
        (dict of key:value pairs)
        A set of tags to be added.

    region
        (string)
        Region to connect to.

    key
        (string)
        Secret key to be used.

    keyid
        (string)
        Access key to be used.

    profile
        (various)
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    .. versionadded:: 2016.3.0
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }
    _new = {'domain_name': domain_name,
            'domain_name_servers': domain_name_servers,
            'ntp_servers': ntp_servers,
            'netbios_name_servers': netbios_name_servers,
            'netbios_node_type': netbios_node_type
           }

    # boto provides no "update_dhcp_options()" functionality, and you can't delete it if
    # it's attached, and you can't detach it if it's the only one, so just check if it's
    # there or not, and make no effort to validate it's actual settings... :(
    ### TODO - add support for multiple sets of DHCP options, and then for "swapping out"
    ###        sets by creating new, mapping, then deleting the old.
    r = __salt__['boto_vpc.dhcp_options_exists'](dhcp_options_id=dhcp_options_id,
                                                 dhcp_options_name=name,
                                                 region=region, key=key, keyid=keyid,
                                                 profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to validate DHCP options: {0}.'.format(r['error']['message'])
        return ret

    if r.get('exists'):
        ret['comment'] = 'DHCP options already present.'
        return ret
    else:
        if __opts__['test']:
            ret['comment'] = 'DHCP options {0} are set to be created.'.format(name)
            ret['result'] = None
            return ret

        r = __salt__['boto_vpc.create_dhcp_options'](domain_name=domain_name,
                                                     domain_name_servers=domain_name_servers,
                                                     ntp_servers=ntp_servers,
                                                     netbios_name_servers=netbios_name_servers,
                                                     netbios_node_type=netbios_node_type,
                                                     dhcp_options_name=name, tags=tags,
                                                     vpc_id=vpc_id, vpc_name=vpc_name,
                                                     region=region, key=key, keyid=keyid,
                                                     profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create DHCP options: {1}'.format(r['error']['message'])
            return ret

        ret['changes']['old'] = {'dhcp_options': None}
        ret['changes']['new'] = {'dhcp_options': _new}
        ret['comment'] = 'DHCP options {0} created.'.format(name)
        return ret


def dhcp_options_absent(name=None, dhcp_options_id=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure a set of DHCP options with the given settings exist.

    name
        (string)
        Name of the DHCP options set.

    dhcp_options_id
        (string)
        Id of the DHCP options set.

    region
        (string)
        Region to connect to.

    key
        (string)
        Secret key to be used.

    keyid
        (string)
        Access key to be used.

    profile
        (various)
        A dict with region, key and keyid, or a pillar key (string) that
        contains a dict with region, key and keyid.

    .. versionadded:: 2016.3.0
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_vpc.get_resource_id']('dhcp_options', name=name,
                                             region=region, key=key,
                                             keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete DHCP options: {0}.'.format(r['error']['message'])
        return ret

    _id = r.get('id')

    if not _id:
        ret['comment'] = 'DHCP options {0} do not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'DHCP options {0} are set to be deleted.'.format(name)
        ret['result'] = None
        return ret

    r = __salt__['boto_vpc.delete_dhcp_options'](dhcp_options_id=r['id'], region=region,
                                                 key=key, keyid=keyid, profile=profile)
    if not r.get('deleted'):
        ret['result'] = False
        ret['comment'] = 'Failed to delete DHCP options: {0}'.format(r['error']['message'])
        return ret

    ret['changes']['old'] = {'dhcp_options': _id}
    ret['changes']['new'] = {'dhcp_options': None}
    ret['comment'] = 'DHCP options {0} deleted.'.format(name)
    return ret


def subnet_present(name, cidr_block, vpc_name=None, vpc_id=None,
                   availability_zone=None, tags=None,
                   region=None, key=None,
                   keyid=None, profile=None,
                   route_table_id=None, route_table_name=None):

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

    route_table_id
        A route table ID to explicitly associate the subnet with.  If both route_table_id
        and route_table_name are specified, route_table_id will take precedence.

        .. versionadded:: Carbon

    route_table_name
        A route table name to explicitly associate the subnet with.  If both route_table_id
        and route_table_name are specified, route_table_id will take precedence.

        .. versionadded:: Carbon

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

    r = __salt__['boto_vpc.subnet_exists'](subnet_name=name, tags=tags,
                                           region=region, key=key,
                                           keyid=keyid, profile=profile)

    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create subnet: {0}.'.format(r['error']['message'])
        return ret

    route_table_desc = None
    _describe = None
    rtid = None
    if route_table_id or route_table_name:
        rt = None
        route_table_found = False
        if route_table_id:
            rtid = route_table_id
            rt = __salt__['boto_vpc.route_table_exists'](route_table_id=route_table_id,
                                                         region=region, key=key, keyid=keyid,
                                                         profile=profile)
        elif route_table_name:
            rtid = route_table_name
            rt = __salt__['boto_vpc.route_table_exists'](route_table_name=route_table_name,
                                                         region=region, key=key, keyid=keyid,
                                                         profile=profile)
        if rt:
            if 'exists' in rt:
                if rt['exists']:
                    if route_table_id:
                        route_table_found = True
                        route_table_desc = __salt__['boto_vpc.describe_route_table'](route_table_id=route_table_id,
                                                                                     region=region, key=key, keyid=keyid,
                                                                                     profile=profile)
                    elif route_table_name:
                        route_table_found = True
                        route_table_desc = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name,
                                                                                     region=region, key=key, keyid=keyid,
                                                                                     profile=profile)
        if not route_table_found:
            ret['result'] = False
            ret['comment'] = 'The specified route table {0} could not be found.'.format(rtid)
            return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Subnet {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_vpc.create_subnet'](subnet_name=name,
                                               cidr_block=cidr_block,
                                               availability_zone=availability_zone,
                                               vpc_name=vpc_name, vpc_id=vpc_id,
                                               tags=tags, region=region,
                                               key=key, keyid=keyid,
                                               profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create subnet: {0}'.format(r['error']['message'])
            return ret
        _describe = __salt__['boto_vpc.describe_subnet'](subnet_id=r['id'], region=region, key=key,
                                                         keyid=keyid, profile=profile)
        ret['changes']['old'] = {'subnet': None}
        ret['changes']['new'] = _describe
        ret['comment'] = 'Subnet {0} created.'.format(name)
    else:
        ret['comment'] = 'Subnet present.'

    if route_table_desc:
        if not _describe:
            _describe = __salt__['boto_vpc.describe_subnet'](subnet_name=name, region=region,
                                                             key=key, keyid=keyid, profile=profile)
        if not _verify_subnet_association(route_table_desc, _describe['subnet']['id']):
            if __opts__['test']:
                msg = 'Subnet is set to be associated with route table {0}'.format(rtid)
                ret['comment'] = ' '.join([ret['comment'], msg])
                ret['result'] = None
                return ret
            if 'explicit_route_table_association_id' in _describe['subnet']:
                log.debug('Need to disassociate from existing route table')
                drt_ret = __salt__['boto_vpc.disassociate_route_table'](_describe['subnet']['explicit_route_table_association_id'],
                                                                        region=region, key=key, keyid=keyid, profile=profile)
                if not drt_ret['disassociated']:
                    msg = 'Unable to disassociate subnet {0} with its current route table.'.format(name)
                    ret['comment'] = ' '.join([ret['comment'], msg])
                    ret['result'] = False
                    return ret
            if 'old' not in ret['changes']:
                ret['changes']['old'] = _describe
            art_ret = __salt__['boto_vpc.associate_route_table'](route_table_id=route_table_desc['id'],
                                                                 subnet_name=name, region=region,
                                                                 key=key, keyid=keyid, profile=profile)
            if 'error' in art_ret:
                msg = 'Failed to associate subnet {0} with route table {1}: {2}.'.format(name, rtid,
                                                                                         art_ret['error']['message'])
                ret['comment'] = ' '.join([ret['comment'], msg])
                ret['result'] = False
                return ret
            else:
                msg = 'Subnet successfully associated with route table {0}.'.format(rtid)
                ret['comment'] = ' '.join([ret['comment'], msg])
                if 'new' not in ret['changes']:
                    ret['changes']['new'] = __salt__['boto_vpc.describe_subnet'](subnet_name=name, region=region,
                                                                                 key=key, keyid=keyid, profile=profile)
                else:
                    ret['changes']['new']['subnet']['explicit_route_table_association_id'] = art_ret['association_id']
        else:
            ret['comment'] = ' '.join([ret['comment'],
                                      'Subnet is already associated with route table {0}'.format(rtid)])
    return ret


def _verify_subnet_association(route_table_desc, subnet_id):
    '''
    Helper function verify a subnet's route table association

    route_table_desc
        the description of a route table, as returned from boto_vpc.describe_route_table

    subnet_id
        the subnet id to verify

    .. versionadded:: Carbon
    '''
    if route_table_desc:
        if 'associations' in route_table_desc:
            for association in route_table_desc['associations']:
                if association['subnet_id'] == subnet_id:
                    return True
    return False


def subnet_absent(name=None, subnet_id=None, region=None, key=None, keyid=None, profile=None):
    '''
    Ensure subnet with passed properties is absent.

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

    r = __salt__['boto_vpc.get_resource_id']('subnet', name=name,
                                             region=region, key=key,
                                             keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete subnet: {0}.'.format(r['error']['message'])
        return ret

    _id = r.get('id')

    if not _id:
        ret['comment'] = '{0} subnet does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Subnet {0} ({1}) is set to be removed.'.format(name, r['id'])
        ret['result'] = None
        return ret

    r = __salt__['boto_vpc.delete_subnet'](subnet_name=name,
                                           region=region, key=key,
                                           keyid=keyid, profile=profile)
    if not r.get('deleted'):
        ret['result'] = False
        ret['comment'] = 'Failed to delete subnet: {0}'.format(r['error']['message'])
        return ret

    ret['changes']['old'] = {'subnet': _id}
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

    r = __salt__['boto_vpc.resource_exists']('internet_gateway', name=name,
                                             region=region, key=key,
                                             keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create internet gateway: {0}.'.format(r['error']['message'])
        return ret

    if not r.get('exists'):
        if __opts__['test']:
            ret['comment'] = 'Internet gateway {0} is set to be created.'.format(name)
            ret['result'] = None
            return ret
        r = __salt__['boto_vpc.create_internet_gateway'](internet_gateway_name=name,
                                                         vpc_name=vpc_name, vpc_id=vpc_id,
                                                         tags=tags, region=region,
                                                         key=key, keyid=keyid,
                                                         profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create internet gateway: {0}'.format(r['error']['message'])
            return ret

        ret['changes']['old'] = {'internet_gateway': None}
        ret['changes']['new'] = {'internet_gateway': r['id']}
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

    r = __salt__['boto_vpc.get_resource_id']('internet_gateway', name=name,
                                             region=region, key=key,
                                             keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete internet gateway: {0}.'.format(r['error']['message'])
        return ret

    igw_id = r['id']
    if not igw_id:
        ret['comment'] = 'Internet gateway {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Internet gateway {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret
    r = __salt__['boto_vpc.delete_internet_gateway'](internet_gateway_name=name,
                                                     detach=detach, region=region,
                                                     key=key, keyid=keyid,
                                                     profile=profile)
    if not r.get('deleted'):
        ret['result'] = False
        ret['comment'] = 'Failed to delete internet gateway: {0}.'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'internet_gateway': igw_id}
    ret['changes']['new'] = {'internet_gateway': None}
    ret['comment'] = 'Internet gateway {0} deleted.'.format(name)
    return ret


def route_table_present(name, vpc_name=None, vpc_id=None, routes=None,
                        subnet_ids=None, subnet_names=None, tags=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Ensure route table with routes exists and is associated to a VPC.

    This function requires boto3 to be installed if nat gatewyas are specified.

    Example:

    .. code-block:: yaml

        boto_vpc.route_table_present:
            - name: my_route_table
            - vpc_id: vpc-123456
            - routes:
              - destination_cidr_block: 0.0.0.0/0
                internet_gateway_name: InternetGateway
              - destination_cidr_block: 10.10.11.0/24
                instance_id: i-123456
              - destination_cidr_block: 10.10.12.0/24
                interface_id: eni-123456
              - destination_cidr_block: 10.10.13.0/24
                instance_name: mygatewayserver
            - subnet_names:
              - subnet1
              - subnet2

    name
        Name of the route table.

    vpc_name
        Name of the VPC with which the route table should be associated.

    vpc_id
        Id of the VPC with which the route table should be associated.
        Either vpc_name or vpc_id must be provided.

    routes
        A list of routes.  Each route has a cidr and a target.

    subnet_ids
        A list of subnet ids to associate

    subnet_names
        A list of subnet names to associate

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

    _ret = _route_table_present(name=name, vpc_name=vpc_name, vpc_id=vpc_id,
                                tags=tags, region=region, key=key,
                                keyid=keyid, profile=profile)
    ret['changes'] = _ret['changes']
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _routes_present(route_table_name=name, routes=routes, tags=tags,
                           region=region, key=key, keyid=keyid, profile=profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    _ret = _subnets_present(route_table_name=name, subnet_ids=subnet_ids,
                            subnet_names=subnet_names, tags=tags, region=region,
                            key=key, keyid=keyid, profile=profile)
    ret['changes'] = dictupdate.update(ret['changes'], _ret['changes'])
    ret['comment'] = ' '.join([ret['comment'], _ret['comment']])
    if not _ret['result']:
        ret['result'] = _ret['result']
        if ret['result'] is False:
            return ret
    return ret


def _route_table_present(name, vpc_name=None, vpc_id=None, tags=None, region=None,
                         key=None, keyid=None, profile=None):
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    r = __salt__['boto_vpc.get_resource_id'](resource='route_table', name=name,
                                             region=region, key=key, keyid=keyid,
                                             profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to create route table: {0}.'.format(r['error']['message'])
        return ret

    _id = r.get('id')

    if not _id:
        if __opts__['test']:
            msg = 'Route table {0} is set to be created.'.format(name)
            ret['comment'] = msg
            ret['result'] = None
            return ret

        r = __salt__['boto_vpc.create_route_table'](route_table_name=name,
                                                    vpc_name=vpc_name,
                                                    vpc_id=vpc_id, tags=tags,
                                                    region=region, key=key,
                                                    keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create route table: {0}.'.format(r['error']['message'])
            return ret

        ret['changes']['old'] = {'route_table': None}
        ret['changes']['new'] = {'route_table': r['id']}
        ret['comment'] = 'Route table {0} created.'.format(name)
        return ret
    ret['comment'] = 'Route table {0} ({1}) present.'.format(name, _id)
    return ret


def _routes_present(route_table_name, routes, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': route_table_name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    route_table = __salt__['boto_vpc.describe_route_tables'](route_table_name=route_table_name, tags=tags,
                                                            region=region, key=key, keyid=keyid, profile=profile)
    if 'error' in route_table:
        msg = 'Could not retrieve configuration for route table {0}: {1}`.'.format(route_table_name,
                                                                                   route_table['error']['message'])
        ret['comment'] = msg
        ret['result'] = False
        return ret

    route_table = route_table[0]
    _routes = []
    if routes:
        route_keys = set(('gateway_id', 'instance_id', 'destination_cidr_block', 'interface_id', 'vpc_peering_connection_id', 'nat_gateway_id'))
        for i in routes:
            #_r = {k:i[k] for k in i if k in route_keys}
            _r = {}
            for k, v in i.iteritems():
                if k in route_keys:
                    _r[k] = i[k]
            if i.get('internet_gateway_name'):
                r = __salt__['boto_vpc.get_resource_id']('internet_gateway', name=i['internet_gateway_name'],
                                                         region=region, key=key, keyid=keyid, profile=profile)
                if 'error' in r:
                    msg = 'Error looking up id for internet gateway {0}: {1}'.format(i.get('internet_gateway_name'),
                                                                                     r['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                if r['id'] is None:
                    msg = 'Internet gateway {0} does not exist.'.format(i)
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                _r['gateway_id'] = r['id']
            if i.get('vpc_peering_connection_name'):
                r = __salt__['boto_vpc.get_resource_id']('vpc_peering_connection', name=i['vpc_peering_connection_name'],
                                                         region=region, key=key, keyid=keyid, profile=profile)
                if 'error' in r:
                    msg = 'Error looking up id for VPC peering connection {0}: {1}'.format(i.get('vpc_peering_connection_name'),
                                                                                     r['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                if r['id'] is None:
                    msg = 'VPC peering connection {0} does not exist.'.format(i)
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                _r['vpc_peering_connection_id'] = r['id']
            if i.get('instance_name'):
                running_states = ('pending', 'rebooting', 'running', 'stopping', 'stopped')
                r = __salt__['boto_ec2.get_id'](name=i['instance_name'], region=region,
                                                key=key, keyid=keyid, profile=profile,
                                                in_states=running_states)
                if r is None:
                    msg = 'Instance {0} does not exist.'.format(i['instance_name'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                _r['instance_id'] = r
            if i.get('nat_gateway_subnet_name'):
                r = __salt__['boto_vpc.describe_nat_gateways'](subnet_name=i['nat_gateway_subnet_name'],
                                                         region=region, key=key, keyid=keyid, profile=profile)
                if not r:
                    msg = 'Nat gateway does not exist.'
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                _r['nat_gateway_id'] = r[0]['NatGatewayId']
            _routes.append(_r)

    to_delete = []
    to_create = []
    for route in _routes:
        if route not in route_table['routes']:
            to_create.append(dict(route))
    for route in route_table['routes']:
        if route not in _routes:
            if route.get('gateway_id') != 'local':
                to_delete.append(route)
    if to_create or to_delete:
        if __opts__['test']:
            msg = 'Route table {0} set to have routes modified.'.format(route_table_name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            for r in to_delete:
                res = __salt__['boto_vpc.delete_route'](route_table_id=route_table['id'],
                                                        destination_cidr_block=r['destination_cidr_block'],
                                                        region=region, key=key, keyid=keyid,
                                                        profile=profile)
                if not res['deleted']:
                    msg = 'Failed to delete route {0} from route table {1}: {2}.'.format(r['destination_cidr_block'],
                                                                                         route_table_name, res['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                ret['comment'] = 'Deleted route {0} from route table {1}.'.format(r['destination_cidr_block'], route_table_name)
        if to_create:
            for r in to_create:
                res = __salt__['boto_vpc.create_route'](route_table_id=route_table['id'], region=region, key=key,
                                                        keyid=keyid, profile=profile, **r)
                if not res['created']:
                    msg = 'Failed to create route {0} in route table {1}: {2}.'.format(r['destination_cidr_block'], route_table_name,
                                                                                       res['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                ret['comment'] = 'Created route {0} in route table {1}.'.format(r['destination_cidr_block'], route_table_name)
        ret['changes']['old'] = {'routes': route_table['routes']}
        route = __salt__['boto_vpc.describe_route_tables'](route_table_name=route_table_name, tags=tags, region=region, key=key,
                                                          keyid=keyid, profile=profile)
        ret['changes']['new'] = {'routes': route[0]['routes']}
    return ret


def _subnets_present(route_table_name, subnet_ids=None, subnet_names=None, tags=None, region=None, key=None, keyid=None, profile=None):
    ret = {'name': route_table_name,
           'result': True,
           'comment': '',
           'changes': {}
           }

    if not subnet_ids:
        subnet_ids = []

    # Look up subnet ids
    if subnet_names:
        for i in subnet_names:
            r = __salt__['boto_vpc.get_resource_id']('subnet', name=i, region=region,
                                                     key=key, keyid=keyid, profile=profile)

            if 'error' in r:
                msg = 'Error looking up subnet ids: {0}'.format(r['error']['message'])
                ret['comment'] = msg
                ret['result'] = False
                return ret
            if r['id'] is None:
                msg = 'Subnet {0} does not exist.'.format(i)
                ret['comment'] = msg
                ret['result'] = False
                return ret
            subnet_ids.append(r['id'])

    # Describe routing table
    route_table = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region,
                                                            key=key, keyid=keyid, profile=profile)
    if not route_table:
        msg = 'Could not retrieve configuration for route table {0}.'.format(route_table_name)
        ret['comment'] = msg
        ret['result'] = False
        return ret

    assoc_ids = [x['subnet_id'] for x in route_table['associations']]

    to_create = [x for x in subnet_ids if x not in assoc_ids]
    to_delete = []
    for x in route_table['associations']:
        # Don't remove the main route table association
        if x['subnet_id'] not in subnet_ids and x['subnet_id'] is not None:
            to_delete.append(x['id'])

    if to_create or to_delete:
        if __opts__['test']:
            msg = 'Subnet associations for route table {0} set to be modified.'.format(route_table_name)
            ret['comment'] = msg
            ret['result'] = None
            return ret
        if to_delete:
            for r_asc in to_delete:
                r = __salt__['boto_vpc.disassociate_route_table'](r_asc, region, key, keyid, profile)
                if 'error' in r:
                    msg = 'Failed to dissociate {0} from route table {1}: {2}.'.format(r_asc, route_table_name,
                                                                                       r['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                ret['comment'] = 'Dissociated subnet {0} from route table {1}.'.format(r_asc, route_table_name)
        if to_create:
            for sn in to_create:
                r = __salt__['boto_vpc.associate_route_table'](route_table_id=route_table['id'],
                                                               subnet_id=sn,
                                                               region=region, key=key,
                                                               keyid=keyid, profile=profile)
                if 'error' in r:
                    msg = 'Failed to associate subnet {0} with route table {1}: {2}.'.format(sn, route_table_name,
                                                                                             r['error']['message'])
                    ret['comment'] = msg
                    ret['result'] = False
                    return ret
                ret['comment'] = 'Associated subnet {0} with route table {1}.'.format(sn, route_table_name)
        ret['changes']['old'] = {'subnets_associations': route_table['associations']}
        new_sub = __salt__['boto_vpc.describe_route_table'](route_table_name=route_table_name, tags=tags, region=region, key=key,
                                                            keyid=keyid, profile=profile)
        ret['changes']['new'] = {'subnets_associations': new_sub['associations']}
    return ret


def route_table_absent(name, region=None,
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

    r = __salt__['boto_vpc.get_resource_id']('route_table', name=name,
                                             region=region, key=key,
                                             keyid=keyid, profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = r['error']['message']
        return ret

    rtbl_id = r['id']

    if not rtbl_id:
        ret['comment'] = 'Route table {0} does not exist.'.format(name)
        return ret

    if __opts__['test']:
        ret['comment'] = 'Route table {0} is set to be removed.'.format(name)
        ret['result'] = None
        return ret

    r = __salt__['boto_vpc.delete_route_table'](route_table_name=name,
                                                region=region,
                                                key=key, keyid=keyid,
                                                profile=profile)
    if 'error' in r:
        ret['result'] = False
        ret['comment'] = 'Failed to delete route table: {0}'.format(r['error']['message'])
        return ret
    ret['changes']['old'] = {'route_table': rtbl_id}
    ret['changes']['new'] = {'route_table': None}
    ret['comment'] = 'Route table {0} deleted.'.format(name)
    return ret


def nat_gateway_present(name, subnet_name=None, subnet_id=None,
                        region=None, key=None, keyid=None, profile=None):
    '''
    Ensure a nat gateway exists within the specified subnet

    This function requires boto3.

    .. versionadded:: Carbon

    Example:

    .. code-block:: yaml

        boto_vpc.nat_gateway_present:
            - subnet_name: my-subnet

    name
        Name of the state

    subnet_name
        Name of the subnet within which the nat gateway should exist

    subnet_id
        Id of the subnet within which the nat gateway should exist.
        Either subnet_name or subnet_id must be provided.

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

    r = __salt__['boto_vpc.describe_nat_gateways'](subnet_name=subnet_name,
                                             subnet_id=subnet_id,
                                             region=region, key=key, keyid=keyid,
                                             profile=profile)
    if not r:
        if __opts__['test']:
            msg = 'Nat gateway is set to be created.'
            ret['comment'] = msg
            ret['result'] = None
            return ret

        r = __salt__['boto_vpc.create_nat_gateway'](subnet_name=subnet_name,
                                                    subnet_id=subnet_id,
                                                    region=region, key=key,
                                                    keyid=keyid, profile=profile)
        if not r.get('created'):
            ret['result'] = False
            ret['comment'] = 'Failed to create nat gateway: {0}.'.format(r['error']['message'])
            return ret

        ret['changes']['old'] = {'nat_gateway': None}
        ret['changes']['new'] = {'nat_gateway': r['id']}
        ret['comment'] = 'Nat gateway created.'
        return ret

    inst = r[0]
    _id = inst.get('NatGatewayId')
    ret['comment'] = 'Nat gateway {0} present.'.format(_id)
    return ret


def nat_gateway_absent(name=None, subnet_name=None, subnet_id=None,
                       region=None, key=None, keyid=None, profile=None):
    '''
    Ensure the nat gateway in the named subnet is absent.

    This function requires boto3.

    .. versionadded:: Carbon

    name
        Name of the state.

    subnet_name
        Name of the subnet within which the nat gateway should exist

    subnet_id
        Id of the subnet within which the nat gateway should exist.
        Either subnet_name or subnet_id must be provided.

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

    r = __salt__['boto_vpc.describe_nat_gateways'](subnet_name=subnet_name,
                                             subnet_id=subnet_id,
                                             region=region, key=key, keyid=keyid,
                                             profile=profile)
    if not r:
        ret['comment'] = 'Nat gateway does not exist.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'Nat gateway is set to be removed.'
        ret['result'] = None
        return ret

    for gw in r:
        rtbl_id = gw.get('NatGatewayId')
        r = __salt__['boto_vpc.delete_nat_gateway'](nat_gateway_id=rtbl_id,
                                                release_eips=True,
                                                region=region,
                                                key=key, keyid=keyid,
                                                profile=profile)
        if 'error' in r:
            ret['result'] = False
            ret['comment'] = 'Failed to delete nat gateway: {0}'.format(r['error']['message'])
            return ret
        ret['comment'] = ', '.join((ret['comment'], 'Nat gateway {0} deleted.'.format(rtbl_id)))
    ret['changes']['old'] = {'nat_gateway': rtbl_id}
    ret['changes']['new'] = {'nat_gateway': None}
    return ret
