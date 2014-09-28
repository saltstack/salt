# -*- coding: utf-8 -*-
'''
Connection module for Amazon VPC

.. versionadded:: Helium

:configuration: This module accepts explicit autoscale credentials but can also
    utilize IAM roles assigned to the instance trough Instance Profiles.
    Dynamic credentials are then automatically obtained from AWS API and no
    further configuration is necessary. More Information available at::

       http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file::

        asg.keyid: GKTADJGHEIQSXMKKRBJ08H
        asg.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A region may also be specified in the configuration::

        asg.region: us-east-1

    If a region is not specified, the default is us-east-1.

    It's also possible to specify key, keyid and region via a profile, either
    as a passed in dict, or as a string to pull from pillars or minion config:

        myprofile:
            keyid: GKTADJGHEIQSXMKKRBJ08H
            key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
            region: us-east-1

:depends: boto

'''

# Import Python libs
import logging
from distutils.version import LooseVersion as _LooseVersion

log = logging.getLogger(__name__)

# Import third party libs
try:
    import boto
    import boto.vpc

    logging.getLogger('boto').setLevel(logging.CRITICAL)
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt._compat import string_types


def __virtual__():
    '''
    Only load if boto libraries exist and if boto libraries are greater than
    a given version.
    '''
    required_boto_version = '2.8.0'
    # the boto_vpc execution module relies on the connect_to_region() method
    # which was added in boto 2.8.0
    # https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
    if not HAS_BOTO:
        return False
    elif _LooseVersion(boto.__version__) < _LooseVersion(required_boto_version):
        return False
    else:
        return True


def get_subnet_association(subnets, region=None, key=None, keyid=None,
                           profile=None):
    '''
    Given a subnet (aka: a vpc zone identifier) or list of subnets, returns
    vpc association.

    Returns a VPC ID if the given subnets are associated with the same VPC ID.
    Returns False on an error or if the given subnets are associated with
    different VPC IDs.

    CLI Examples::

    .. code-block:: bash

        salt myminion boto_vpc.get_subnet_association subnet-61b47516

    .. code-block:: bash

        salt myminion boto_vpc.get_subnet_association ['subnet-61b47516','subnet-2cb9785b']

    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        # subnet_ids=subnets can accept either a string or a list
        subnets = conn.get_all_subnets(subnet_ids=subnets)
    except boto.exception.BotoServerError as e:
        log.debug(e)
        return False
    # using a set to store vpc_ids - the use of set prevents duplicate
    # vpc_id values
    vpc_ids = set()
    for subnet in subnets:
        log.debug('examining subnet id: {0} for vpc_id'.format(subnet.id))
        if subnet in subnets:
            log.debug('subnet id: {0} is associated with vpc id: {1}'
                      .format(subnet.id, subnet.vpc_id))
            vpc_ids.add(subnet.vpc_id)
    if len(vpc_ids) == 1:
        vpc_id = vpc_ids.pop()
        log.info('all subnets are associated with vpc id: {0}'.format(vpc_id))
        return vpc_id
    else:
        log.info('given subnets are associated with fewer than 1 or greater'
                  ' than 1 subnets')
        return False


def exists(vpc_id, region=None, key=None, keyid=None, profile=None):
    '''
    Given a VPC ID, check to see if the given VPC ID exists.

    Returns True if the given VPC ID exists and returns False if the given
    VPC ID does not exist.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.exists myvpc

    '''
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.get_all_vpcs(vpc_ids=[vpc_id])
        return True
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def create(cidr_block, instance_tenancy=None, region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid CIDR block, create a VPC.

    An optional instance_tenancy argument can be provided. If provided, the valid values are 'default' or 'dedicated'

    Returns True if the VPC was created and returns False if the VPC was not created.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.create '10.0.0.0/24'

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        vpc = conn.create_vpc(cidr_block, instance_tenancy=instance_tenancy)

        log.debug('The newly created VPC id is {0}'.format(vpc.id))

        return True
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def delete(vpc_id, region=None, key=None, keyid=None, profile=None):
    '''
    Given a VPC ID, delete the VPC.

    Returns True if the VPC was deleted and returns False if the VPC was not deleted.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.delete 'vpc-6b1fe402'

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        if conn.delete_vpc(vpc_id):
            log.debug('VPC {0} was deleted.'.format(vpc_id))

            return True
        else:
            log.debug('VPC {0} was not deleted.'.format(vpc_id))

            return False
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def create_subnet(vpc_id, cidr_block, availability_zone=None, region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid VPC ID and a CIDR block, create a subnet for the VPC.

    An optional availability zone argument can be provided.

    Returns True if the VPC subnet was created and returns False if the VPC subnet was not created.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.create_subnet 'vpc-6b1fe402' '10.0.0.0/25'

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        vpc_subnet = conn.create_subnet(vpc_id, cidr_block, availability_zone=availability_zone)

        log.debug('A VPC subnet {0} with {1} available ips on VPC {2}'.format(vpc_subnet.id,
                                                                              vpc_subnet.available_ip_address_count,
                                                                              vpc_id))

        return True
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def delete_subnet(subnet_id, region=None, key=None, keyid=None, profile=None):
    '''
    Given a subnet ID, delete the subnet.

    Returns True if the subnet was deleted and returns False if the subnet was not deleted.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.delete_subnet 'subnet-6a1fe403'

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        if conn.delete_subnet(subnet_id):
            log.debug('Subnet {0} was deleted.'.format(subnet_id))

            return True
        else:
            log.debug('Subnet {0} was not deleted.'.format(subnet_id))

            return False
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def create_customer_gateway(vpn_connection_type, ip_address, bgp_asn, region=None, key=None, keyid=None, profile=None):
    '''
    Given a valid VPN connection type, a static IP address and a customer gateway’s Border Gateway Protocol (BGP) Autonomous System Number, create a customer gateway.

    Returns True if the customer gateway was created and returns False if the customer gateway was not created.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.create_customer_gateway 'ipsec.1', '12.1.2.3', 65534

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        customer_gateway = conn.create_customer_gateway(vpn_connection_type, ip_address, bgp_asn)

        log.info('A customer gateway with id {0} was created'.format(customer_gateway.id))
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def delete_customer_gateway(customer_gateway_id, region=None, key=None, keyid=None, profile=None):
    '''
    Given a customer gateway ID, delete the customer gateway.

    Returns True if the customer gateway was deleted and returns False if the customer gateway was not deleted.

    CLI example::

    .. code-block:: bash

        salt myminion boto_vpc.delete_customer_gateway 'cgw-b6a247df'

    '''

    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        if conn.delete_customer_gateway(customer_gateway_id):
            log.info('Customer gateway {0} was deleted.'.format(customer_gateway_id))

            return True
        else:
            log.info('Customer gateway {0} was not deleted.'.format(customer_gateway_id))

            return False
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def create_dhcp_options(domain_name=None, domain_name_servers=None, ntp_servers=None,
                        netbios_name_servers=None, netbios_node_type=None,
                        region=None, key=None, keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False

    try:
        dhcp_options = _create_dhcp_options(conn, domain_name=domain_name, domain_name_servers=domain_name_servers,
                                            ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                                            netbios_node_type=netbios_node_type)
        log.info('DHCP options with id {0} were created'.format(dhcp_options.id))
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def associate_dhcp_options_to_vpc(dhcp_options_id, vpc_id, region=None, key=None, keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        conn.associate_dhcp_options(dhcp_options_id, vpc_id)
        log.info('DHCP options with id {0} were associated with VPC {1}'.format(dhcp_options_id, vpc_id))

        return True
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def associate_new_dhcp_options_to_vpc(vpc_id, domain_name=None, domain_name_servers=None, ntp_servers=None,
                                      netbios_name_servers=None, netbios_node_type=None,
                                      region=None, key=None, keyid=None, profile=None):
    conn = _get_conn(region, key, keyid, profile)
    if not conn:
        return False
    try:
        dhcp_options = _create_dhcp_options(conn, domain_name=domain_name, domain_name_servers=domain_name_servers,
                                            ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                                            netbios_node_type=netbios_node_type)
        conn.associate_dhcp_options(dhcp_options.id, vpc_id)
        log.info('DHCP options with id {0} were created and associated with VPC {1}'.format(dhcp_options.id, vpc_id))
        return True
    except boto.exception.BotoServerError as e:
        log.error(e)
        return False


def _get_conn(region, key, keyid, profile):
    '''
    Get a boto connection to vpc.
    '''
    if profile:
        if isinstance(profile, string_types):
            _profile = __salt__['config.option'](profile)
        elif isinstance(profile, dict):
            _profile = profile
        key = _profile.get('key', None)
        keyid = _profile.get('keyid', None)
        region = _profile.get('region', None)

    if not region and __salt__['config.option']('vpc.region'):
        region = __salt__['config.option']('vpc.region')

    if not region:
        region = 'us-east-1'

    if not key and __salt__['config.option']('vpc.key'):
        key = __salt__['config.option']('vpc.key')
    if not keyid and __salt__['config.option']('vpc.keyid'):
        keyid = __salt__['config.option']('vpc.keyid')

    try:
        conn = boto.vpc.connect_to_region(region, aws_access_key_id=keyid,
                                          aws_secret_access_key=key)
    except boto.exception.NoAuthHandlerFound:
        log.error('No authentication credentials found when attempting to'
                  ' make boto autoscale connection.')
        return None
    return conn


def _create_dhcp_options(conn, domain_name=None, domain_name_servers=None, ntp_servers=None, netbios_name_servers=None,
                         netbios_node_type=None):
    return conn.create_dhcp_options(domain_name=domain_name, domain_name_servers=domain_name_servers,
                                    ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                                    netbios_node_type=netbios_node_type)
