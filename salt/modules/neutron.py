# -*- coding: utf-8 -*-
"""
Module for handling OpenStack Neutron calls

:depends:   - neutronclient Python module
:configuration: This module is not usable until the user, password, tenant, and
    auth URL are specified either in a pillar or in the minion's config file.
    For example::

        keystone.user: 'admin'
        keystone.password: 'password'
        keystone.tenant: 'admin'
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
        keystone.region_name: 'RegionOne'
        keystone.service_type: 'network'

    If configuration for multiple OpenStack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: 'admin'
          keystone.password: 'password'
          keystone.tenant: 'admin'
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'
          keystone.region_name: 'RegionOne'
          keystone.service_type: 'network'

        openstack2:
          keystone.user: 'admin'
          keystone.password: 'password'
          keystone.tenant: 'admin'
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'
          keystone.region_name: 'RegionOne'
          keystone.service_type: 'network'

    With this configuration in place, any of the neutron functions
    can make use of a configuration profile by declaring it explicitly.
    For example::

        salt '*' neutron.network_list profile=openstack1

    To use keystoneauth1 instead of keystoneclient, include the `use_keystoneauth`
    option in the pillar or minion config.

    .. note:: this is required to use keystone v3 as for authentication.

    .. code-block:: yaml

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.auth_url: 'http://127.0.0.1:5000/v3/'
        keystone.region_name: 'RegionOne'
        keystone.service_type: 'network'
        keystone.use_keystoneauth: true
        keystone.verify: '/path/to/custom/certs/ca-bundle.crt'


    Note: by default the neutron module will attempt to verify its connection
    utilizing the system certificates. If you need to verify against another bundle
    of CA certificates or want to skip verification altogether you will need to
    specify the `verify` option. You can specify True or False to verify (or not)
    against system certificates, a path to a bundle or CA certs to check against, or
    None to allow keystoneauth to search for the certificates on its own.(defaults to True)
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
try:
    import salt.utils.openstack.neutron as suoneu

    HAS_NEUTRON = True
except NameError as exc:
    HAS_NEUTRON = False

# Get logging started
log = logging.getLogger(__name__)

# Function alias to not shadow built-ins
__func_alias__ = {"list_": "list"}


def __virtual__():
    """
    Only load this module if neutron
    is installed on this minion.
    """
    return HAS_NEUTRON


__opts__ = {}


def _auth(profile=None):
    """
    Set up neutron credentials
    """
    if profile:
        credentials = __salt__["config.option"](profile)
        user = credentials["keystone.user"]
        password = credentials["keystone.password"]
        tenant = credentials["keystone.tenant"]
        auth_url = credentials["keystone.auth_url"]
        region_name = credentials.get("keystone.region_name", None)
        service_type = credentials.get("keystone.service_type", "network")
        os_auth_system = credentials.get("keystone.os_auth_system", None)
        use_keystoneauth = credentials.get("keystone.use_keystoneauth", False)
        verify = credentials.get("keystone.verify", True)
    else:
        user = __salt__["config.option"]("keystone.user")
        password = __salt__["config.option"]("keystone.password")
        tenant = __salt__["config.option"]("keystone.tenant")
        auth_url = __salt__["config.option"]("keystone.auth_url")
        region_name = __salt__["config.option"]("keystone.region_name")
        service_type = __salt__["config.option"]("keystone.service_type")
        os_auth_system = __salt__["config.option"]("keystone.os_auth_system")
        use_keystoneauth = __salt__["config.option"]("keystone.use_keystoneauth")
        verify = __salt__["config.option"]("keystone.verify")

    if use_keystoneauth is True:
        project_domain_name = credentials["keystone.project_domain_name"]
        user_domain_name = credentials["keystone.user_domain_name"]

        kwargs = {
            "username": user,
            "password": password,
            "tenant_name": tenant,
            "auth_url": auth_url,
            "region_name": region_name,
            "service_type": service_type,
            "os_auth_plugin": os_auth_system,
            "use_keystoneauth": use_keystoneauth,
            "verify": verify,
            "project_domain_name": project_domain_name,
            "user_domain_name": user_domain_name,
        }
    else:
        kwargs = {
            "username": user,
            "password": password,
            "tenant_name": tenant,
            "auth_url": auth_url,
            "region_name": region_name,
            "service_type": service_type,
            "os_auth_plugin": os_auth_system,
        }

    return suoneu.SaltNeutron(**kwargs)


def get_quotas_tenant(profile=None):
    """
    Fetches tenant info in server's context for following quota operation

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.get_quotas_tenant
        salt '*' neutron.get_quotas_tenant profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: Quotas information
    """

    conn = _auth(profile)
    return conn.get_quotas_tenant()


def list_quotas(profile=None):
    """
    Fetches all tenants quotas

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_quotas
        salt '*' neutron.list_quotas profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of quotas
    """
    conn = _auth(profile)
    return conn.list_quotas()


def show_quota(tenant_id, profile=None):
    """
    Fetches information of a certain tenant's quotas

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_quota tenant-id
        salt '*' neutron.show_quota tenant-id profile=openstack1

    :param tenant_id: ID of tenant
    :param profile: Profile to build on (Optional)
    :return: Quota information
    """
    conn = _auth(profile)
    return conn.show_quota(tenant_id)


def update_quota(
    tenant_id,
    subnet=None,
    router=None,
    network=None,
    floatingip=None,
    port=None,
    security_group=None,
    security_group_rule=None,
    profile=None,
):
    """
    Update a tenant's quota

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_quota tenant-id subnet=40 router=50
                                    network=10 floatingip=30 port=30

    :param tenant_id: ID of tenant
    :param subnet: Value of subnet quota (Optional)
    :param router: Value of router quota (Optional)
    :param network: Value of network quota (Optional)
    :param floatingip: Value of floatingip quota (Optional)
    :param port: Value of port quota (Optional)
    :param security_group: Value of security group (Optional)
    :param security_group_rule: Value of security group rule (Optional)
    :param profile: Profile to build on (Optional)
    :return: Value of updated quota
    """
    conn = _auth(profile)
    return conn.update_quota(
        tenant_id,
        subnet,
        router,
        network,
        floatingip,
        port,
        security_group,
        security_group_rule,
    )


def delete_quota(tenant_id, profile=None):
    """
    Delete the specified tenant's quota value

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_quota tenant-id
        salt '*' neutron.update_quota tenant-id profile=openstack1

    :param tenant_id: ID of tenant to quota delete
    :param profile: Profile to build on (Optional)
    :return: True(Delete succeed) or False(Delete failed)
    """
    conn = _auth(profile)
    return conn.delete_quota(tenant_id)


def list_extensions(profile=None):
    """
    Fetches a list of all extensions on server side

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_extensions
        salt '*' neutron.list_extensions profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of extensions
    """
    conn = _auth(profile)
    return conn.list_extensions()


def list_ports(profile=None):
    """
    Fetches a list of all networks for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_ports
        salt '*' neutron.list_ports profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of port
    """
    conn = _auth(profile)
    return conn.list_ports()


def show_port(port, profile=None):
    """
    Fetches information of a certain port

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_port port-id
        salt '*' neutron.show_port port-id profile=openstack1

    :param port: ID or name of port to look up
    :param profile: Profile to build on (Optional)
    :return: Port information
    """
    conn = _auth(profile)
    return conn.show_port(port)


def create_port(name, network, device_id=None, admin_state_up=True, profile=None):
    """
    Creates a new port

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_port network-name port-name

    :param name: Name of port to create
    :param network: Network name or ID
    :param device_id: ID of device (Optional)
    :param admin_state_up: Set admin state up to true or false,
            default: true (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created port information
    """
    conn = _auth(profile)
    return conn.create_port(name, network, device_id, admin_state_up)


def update_port(port, name, admin_state_up=True, profile=None):
    """
    Updates a port

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_port port-name network-name new-port-name

    :param port: Port name or ID
    :param name: Name of this port
    :param admin_state_up: Set admin state up to true or false,
            default: true (Optional)
    :param profile: Profile to build on (Optional)
    :return: Value of updated port information
    """
    conn = _auth(profile)
    return conn.update_port(port, name, admin_state_up)


def delete_port(port, profile=None):
    """
    Deletes the specified port

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_network port-name
        salt '*' neutron.delete_network port-name profile=openstack1

    :param port: port name or ID
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_port(port)


def list_networks(profile=None):
    """
    Fetches a list of all networks for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_networks
        salt '*' neutron.list_networks profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of network
    """
    conn = _auth(profile)
    return conn.list_networks()


def show_network(network, profile=None):
    """
    Fetches information of a certain network

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_network network-name
        salt '*' neutron.show_network network-name profile=openstack1

    :param network: ID or name of network to look up
    :param profile: Profile to build on (Optional)
    :return: Network information
    """
    conn = _auth(profile)
    return conn.show_network(network)


def create_network(
    name,
    router_ext=None,
    admin_state_up=True,
    network_type=None,
    physical_network=None,
    segmentation_id=None,
    shared=None,
    profile=None,
):
    """
    Creates a new network

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_network network-name
        salt '*' neutron.create_network network-name profile=openstack1

    :param name: Name of network to create
    :param admin_state_up: should the state of the network be up?
            default: True (Optional)
    :param router_ext: True then if create the external network (Optional)
    :param network_type: the Type of network that the provider is such as GRE, VXLAN, VLAN, FLAT, or LOCAL (Optional)
    :param physical_network: the name of the physical network as neutron knows it (Optional)
    :param segmentation_id: the vlan id or GRE id (Optional)
    :param shared: is the network shared or not (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created network information
    """
    conn = _auth(profile)
    return conn.create_network(
        name,
        admin_state_up,
        router_ext,
        network_type,
        physical_network,
        segmentation_id,
        shared,
    )


def update_network(network, name, profile=None):
    """
    Updates a network

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_network network-name new-network-name

    :param network: ID or name of network to update
    :param name: Name of this network
    :param profile: Profile to build on (Optional)
    :return: Value of updated network information
    """
    conn = _auth(profile)
    return conn.update_network(network, name)


def delete_network(network, profile=None):
    """
    Deletes the specified network

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_network network-name
        salt '*' neutron.delete_network network-name profile=openstack1

    :param network: ID or name of network to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_network(network)


def list_subnets(profile=None):
    """
    Fetches a list of all networks for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_subnets
        salt '*' neutron.list_subnets profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of subnet
    """
    conn = _auth(profile)
    return conn.list_subnets()


def show_subnet(subnet, profile=None):
    """
    Fetches information of a certain subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_subnet subnet-name

    :param subnet: ID or name of subnet to look up
    :param profile: Profile to build on (Optional)
    :return: Subnet information
    """
    conn = _auth(profile)
    return conn.show_subnet(subnet)


def create_subnet(network, cidr, name=None, ip_version=4, profile=None):
    """
    Creates a new subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_subnet network-name 192.168.1.0/24

    :param network: Network ID or name this subnet belongs to
    :param cidr: CIDR of subnet to create (Ex. '192.168.1.0/24')
    :param name: Name of the subnet to create (Optional)
    :param ip_version: Version to use, default is 4(IPv4) (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created subnet information
    """
    conn = _auth(profile)
    return conn.create_subnet(network, cidr, name, ip_version)


def update_subnet(subnet, name, profile=None):
    """
    Updates a subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_subnet subnet-name new-subnet-name

    :param subnet: ID or name of subnet to update
    :param name: Name of this subnet
    :param profile: Profile to build on (Optional)
    :return: Value of updated subnet information
    """
    conn = _auth(profile)
    return conn.update_subnet(subnet, name)


def delete_subnet(subnet, profile=None):
    """
    Deletes the specified subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_subnet subnet-name
        salt '*' neutron.delete_subnet subnet-name profile=openstack1

    :param subnet: ID or name of subnet to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_subnet(subnet)


def list_routers(profile=None):
    """
    Fetches a list of all routers for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_routers
        salt '*' neutron.list_routers profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of router
    """
    conn = _auth(profile)
    return conn.list_routers()


def show_router(router, profile=None):
    """
    Fetches information of a certain router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_router router-name

    :param router: ID or name of router to look up
    :param profile: Profile to build on (Optional)
    :return: Router information
    """
    conn = _auth(profile)
    return conn.show_router(router)


def create_router(name, ext_network=None, admin_state_up=True, profile=None):
    """
    Creates a new router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_router new-router-name

    :param name: Name of router to create (must be first)
    :param ext_network: ID or name of the external for the gateway (Optional)
    :param admin_state_up: Set admin state up to true or false,
            default:true (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created router information
    """
    conn = _auth(profile)
    return conn.create_router(name, ext_network, admin_state_up)


def update_router(router, name=None, admin_state_up=None, profile=None, **kwargs):
    """
    Updates a router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_router router_id name=new-router-name
                admin_state_up=True

    :param router: ID or name of router to update
    :param name: Name of this router
    :param ext_network: ID or name of the external for the gateway (Optional)
    :param admin_state_up: Set admin state up to true or false,
            default: true (Optional)
    :param profile: Profile to build on (Optional)
    :param kwargs:
    :return: Value of updated router information
    """
    conn = _auth(profile)
    return conn.update_router(router, name, admin_state_up, **kwargs)


def delete_router(router, profile=None):
    """
    Delete the specified router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_router router-name

    :param router: ID or name of router to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_router(router)


def add_interface_router(router, subnet, profile=None):
    """
    Adds an internal network interface to the specified router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.add_interface_router router-name subnet-name

    :param router: ID or name of the router
    :param subnet: ID or name of the subnet
    :param profile: Profile to build on (Optional)
    :return: Added interface information
    """
    conn = _auth(profile)
    return conn.add_interface_router(router, subnet)


def remove_interface_router(router, subnet, profile=None):
    """
    Removes an internal network interface from the specified router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.remove_interface_router router-name subnet-name

    :param router: ID or name of the router
    :param subnet: ID or name of the subnet
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.remove_interface_router(router, subnet)


def add_gateway_router(router, ext_network, profile=None):
    """
    Adds an external network gateway to the specified router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.add_gateway_router router-name ext-network-name

    :param router: ID or name of the router
    :param ext_network: ID or name of the external network the gateway
    :param profile: Profile to build on (Optional)
    :return: Added Gateway router information
    """
    conn = _auth(profile)
    return conn.add_gateway_router(router, ext_network)


def remove_gateway_router(router, profile=None):
    """
    Removes an external network gateway from the specified router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.remove_gateway_router router-name

    :param router: ID or name of router
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.remove_gateway_router(router)


def list_floatingips(profile=None):
    """
    Fetch a list of all floatingIPs for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_floatingips
        salt '*' neutron.list_floatingips profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of floatingIP
    """
    conn = _auth(profile)
    return conn.list_floatingips()


def show_floatingip(floatingip_id, profile=None):
    """
    Fetches information of a certain floatingIP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_floatingip floatingip-id

    :param floatingip_id: ID of floatingIP to look up
    :param profile: Profile to build on (Optional)
    :return: Floating IP information
    """
    conn = _auth(profile)
    return conn.show_floatingip(floatingip_id)


def create_floatingip(floating_network, port=None, profile=None):
    """
    Creates a new floatingIP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_floatingip network-name port-name

    :param floating_network: Network name or ID to allocate floatingIP from
    :param port: Of the port to be associated with the floatingIP (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created floatingIP information
    """
    conn = _auth(profile)
    return conn.create_floatingip(floating_network, port)


def update_floatingip(floatingip_id, port=None, profile=None):
    """
    Updates a floatingIP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_floatingip network-name port-name

    :param floatingip_id: ID of floatingIP
    :param port: ID or name of port, to associate floatingip to `None` or do
        not specify to disassociate the floatingip (Optional)
    :param profile: Profile to build on (Optional)
    :return: Value of updated floating IP information
    """
    conn = _auth(profile)
    return conn.update_floatingip(floatingip_id, port)


def delete_floatingip(floatingip_id, profile=None):
    """
    Deletes the specified floating IP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_floatingip floatingip-id

    :param floatingip_id: ID of floatingIP to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_floatingip(floatingip_id)


def list_security_groups(profile=None):
    """
    Fetches a list of all security groups for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_security_groups
        salt '*' neutron.list_security_groups profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of security group
    """
    conn = _auth(profile)
    return conn.list_security_groups()


def show_security_group(security_group, profile=None):
    """
    Fetches information of a certain security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_security_group security-group-name

    :param security_group: ID or name of security group to look up
    :param profile: Profile to build on (Optional)
    :return: Security group information
    """
    conn = _auth(profile)
    return conn.show_security_group(security_group)


def create_security_group(name=None, description=None, profile=None):
    """
    Creates a new security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_security_group security-group-name \
                description='Security group for servers'

    :param name: Name of security group (Optional)
    :param description: Description of security group (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created security group information
    """
    conn = _auth(profile)
    return conn.create_security_group(name, description)


def update_security_group(security_group, name=None, description=None, profile=None):
    """
    Updates a security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_security_group security-group-name \
                new-security-group-name

    :param security_group: ID or name of security group to update
    :param name: Name of this security group (Optional)
    :param description: Description of security group (Optional)
    :param profile: Profile to build on (Optional)
    :return: Value of updated security group information
    """
    conn = _auth(profile)
    return conn.update_security_group(security_group, name, description)


def delete_security_group(security_group, profile=None):
    """
    Deletes the specified security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_security_group security-group-name

    :param security_group: ID or name of security group to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_security_group(security_group)


def list_security_group_rules(profile=None):
    """
    Fetches a list of all security group rules for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_security_group_rules
        salt '*' neutron.list_security_group_rules profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of security group rule
    """
    conn = _auth(profile)
    return conn.list_security_group_rules()


def show_security_group_rule(security_group_rule_id, profile=None):
    """
    Fetches information of a certain security group rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_security_group_rule security-group-rule-id

    :param security_group_rule_id: ID of security group rule to look up
    :param profile: Profile to build on (Optional)
    :return: Security group rule information
    """
    conn = _auth(profile)
    return conn.show_security_group_rule(security_group_rule_id)


def create_security_group_rule(
    security_group,
    remote_group_id=None,
    direction="ingress",
    protocol=None,
    port_range_min=None,
    port_range_max=None,
    ethertype="IPv4",
    profile=None,
):
    """
    Creates a new security group rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_security_group_rule security-group-rule-id

    :param security_group: Security group name or ID to add rule
    :param remote_group_id: Remote security group name or ID to
            apply rule (Optional)
    :param direction: Direction of traffic: ingress/egress,
            default: ingress (Optional)
    :param protocol: Protocol of packet: null/icmp/tcp/udp,
            default: null (Optional)
    :param port_range_min: Starting port range (Optional)
    :param port_range_max: Ending port range (Optional)
    :param ethertype: IPv4/IPv6, default: IPv4 (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created security group rule information
    """
    conn = _auth(profile)
    return conn.create_security_group_rule(
        security_group,
        remote_group_id,
        direction,
        protocol,
        port_range_min,
        port_range_max,
        ethertype,
    )


def delete_security_group_rule(security_group_rule_id, profile=None):
    """
    Deletes the specified security group rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_security_group_rule security-group-rule-id

    :param security_group_rule_id: ID of security group rule to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_security_group_rule(security_group_rule_id)


def list_vpnservices(retrieve_all=True, profile=None, **kwargs):
    """
    Fetches a list of all configured VPN services for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_vpnservices

    :param retrieve_all: True or False, default: True (Optional)
    :param profile: Profile to build on (Optional)
    :return: List of VPN service
    """
    conn = _auth(profile)
    return conn.list_vpnservices(retrieve_all, **kwargs)


def show_vpnservice(vpnservice, profile=None, **kwargs):
    """
    Fetches information of a specific VPN service

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_vpnservice vpnservice-name

    :param vpnservice: ID or name of vpn service to look up
    :param profile: Profile to build on (Optional)
    :return: VPN service information
    """
    conn = _auth(profile)
    return conn.show_vpnservice(vpnservice, **kwargs)


def create_vpnservice(subnet, router, name, admin_state_up=True, profile=None):
    """
    Creates a new VPN service

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_vpnservice router-name name

    :param subnet: Subnet unique identifier for the VPN service deployment
    :param router: Router unique identifier for the VPN service
    :param name: Set a name for the VPN service
    :param admin_state_up: Set admin state up to true or false,
            default:True (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created VPN service information
    """
    conn = _auth(profile)
    return conn.create_vpnservice(subnet, router, name, admin_state_up)


def update_vpnservice(vpnservice, desc, profile=None):
    """
    Updates a VPN service

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_vpnservice vpnservice-name desc='VPN Service1'

    :param vpnservice: ID or name of vpn service to update
    :param desc: Set a description for the VPN service
    :param profile: Profile to build on (Optional)
    :return: Value of updated VPN service information
    """
    conn = _auth(profile)
    return conn.update_vpnservice(vpnservice, desc)


def delete_vpnservice(vpnservice, profile=None):
    """
    Deletes the specified VPN service

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_vpnservice vpnservice-name

    :param vpnservice: ID or name of vpn service to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_vpnservice(vpnservice)


def list_ipsec_site_connections(profile=None):
    """
    Fetches all configured IPsec Site Connections for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_ipsec_site_connections
        salt '*' neutron.list_ipsec_site_connections profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of IPSec site connection
    """
    conn = _auth(profile)
    return conn.list_ipsec_site_connections()


def show_ipsec_site_connection(ipsec_site_connection, profile=None):
    """
    Fetches information of a specific IPsecSiteConnection

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_ipsec_site_connection connection-name

    :param ipsec_site_connection: ID or name of ipsec site connection
            to look up
    :param profile: Profile to build on (Optional)
    :return: IPSec site connection information
    """
    conn = _auth(profile)
    return conn.show_ipsec_site_connection(ipsec_site_connection)


def create_ipsec_site_connection(
    name,
    ipsecpolicy,
    ikepolicy,
    vpnservice,
    peer_cidrs,
    peer_address,
    peer_id,
    psk,
    admin_state_up=True,
    profile=None,
    **kwargs
):
    """
    Creates a new IPsecSiteConnection

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_ipsec_site_connection connection-name
                ipsec-policy-name ikepolicy-name vpnservice-name
                192.168.XXX.XXX/24 192.168.XXX.XXX 192.168.XXX.XXX secret

    :param name: Set friendly name for the connection
    :param ipsecpolicy: IPSec policy ID or name associated with this connection
    :param ikepolicy: IKE policy ID or name associated with this connection
    :param vpnservice: VPN service instance ID or name associated with
            this connection
    :param peer_cidrs: Remote subnet(s) in CIDR format
    :param peer_address: Peer gateway public IPv4/IPv6 address or FQDN
    :param peer_id: Peer router identity for authentication
            Can be IPv4/IPv6 address, e-mail address, key id, or FQDN
    :param psk: Pre-shared key string
    :param initiator: Initiator state in lowercase, default:bi-directional
    :param admin_state_up: Set admin state up to true or false,
            default: True (Optional)
    :param mtu: size for the connection, default:1500 (Optional)
    :param dpd_action: Dead Peer Detection attribute: hold/clear/disabled/
            restart/restart-by-peer (Optional)
    :param dpd_interval: Dead Peer Detection attribute (Optional)
    :param dpd_timeout: Dead Peer Detection attribute (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created IPSec site connection information
    """
    conn = _auth(profile)
    return conn.create_ipsec_site_connection(
        name,
        ipsecpolicy,
        ikepolicy,
        vpnservice,
        peer_cidrs,
        peer_address,
        peer_id,
        psk,
        admin_state_up,
        **kwargs
    )


def delete_ipsec_site_connection(ipsec_site_connection, profile=None):
    """
    Deletes the specified IPsecSiteConnection

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_ipsec_site_connection connection-name

    :param ipsec_site_connection: ID or name of ipsec site connection to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_ipsec_site_connection(ipsec_site_connection)


def list_ikepolicies(profile=None):
    """
    Fetches a list of all configured IKEPolicies for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_ikepolicies
        salt '*' neutron.list_ikepolicies profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of IKE policy
    """
    conn = _auth(profile)
    return conn.list_ikepolicies()


def show_ikepolicy(ikepolicy, profile=None):
    """
    Fetches information of a specific IKEPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_ikepolicy ikepolicy-name

    :param ikepolicy: ID or name of ikepolicy to look up
    :param profile: Profile to build on (Optional)
    :return: IKE policy information
    """
    conn = _auth(profile)
    return conn.show_ikepolicy(ikepolicy)


def create_ikepolicy(name, profile=None, **kwargs):
    """
    Creates a new IKEPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_ikepolicy ikepolicy-name
                phase1_negotiation_mode=main auth_algorithm=sha1
                encryption_algorithm=aes-128 pfs=group5

    :param name: Name of the IKE policy
    :param phase1_negotiation_mode: IKE Phase1 negotiation mode in lowercase,
            default: main (Optional)
    :param auth_algorithm: Authentication algorithm in lowercase,
            default: sha1 (Optional)
    :param encryption_algorithm: Encryption algorithm in lowercase.
            default:aes-128 (Optional)
    :param pfs: Prefect Forward Security in lowercase,
            default: group5 (Optional)
    :param units: IKE lifetime attribute. default: seconds (Optional)
    :param value: IKE lifetime attribute. default: 3600 (Optional)
    :param ike_version: IKE version in lowercase, default: v1 (Optional)
    :param profile: Profile to build on (Optional)
    :param kwargs:
    :return: Created IKE policy information
    """
    conn = _auth(profile)
    return conn.create_ikepolicy(name, **kwargs)


def delete_ikepolicy(ikepolicy, profile=None):
    """
    Deletes the specified IKEPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_ikepolicy ikepolicy-name

    :param ikepolicy: ID or name of IKE policy to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_ikepolicy(ikepolicy)


def list_ipsecpolicies(profile=None):
    """
    Fetches a list of all configured IPsecPolicies for a tenant

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_ipsecpolicies ipsecpolicy-name
        salt '*' neutron.list_ipsecpolicies ipsecpolicy-name profile=openstack1

    :param profile: Profile to build on (Optional)
    :return: List of IPSec policy
    """
    conn = _auth(profile)
    return conn.list_ipsecpolicies()


def show_ipsecpolicy(ipsecpolicy, profile=None):
    """
    Fetches information of a specific IPsecPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_ipsecpolicy ipsecpolicy-name

    :param ipsecpolicy: ID or name of IPSec policy to look up
    :param profile: Profile to build on (Optional)
    :return: IPSec policy information
    """
    conn = _auth(profile)
    return conn.show_ipsecpolicy(ipsecpolicy)


def create_ipsecpolicy(name, profile=None, **kwargs):
    """
    Creates a new IPsecPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_ipsecpolicy ipsecpolicy-name
                transform_protocol=esp auth_algorithm=sha1
                encapsulation_mode=tunnel encryption_algorithm=aes-128

    :param name: Name of the IPSec policy
    :param transform_protocol: Transform protocol in lowercase,
            default: esp (Optional)
    :param auth_algorithm: Authentication algorithm in lowercase,
            default: sha1 (Optional)
    :param encapsulation_mode: Encapsulation mode in lowercase,
            default: tunnel (Optional)
    :param encryption_algorithm: Encryption algorithm in lowercase,
            default:aes-128 (Optional)
    :param pfs: Prefect Forward Security in lowercase,
            default: group5 (Optional)
    :param units: IPSec lifetime attribute. default: seconds (Optional)
    :param value: IPSec lifetime attribute. default: 3600 (Optional)
    :param profile: Profile to build on (Optional)
    :return: Created IPSec policy information
    """
    conn = _auth(profile)
    return conn.create_ipsecpolicy(name, **kwargs)


def delete_ipsecpolicy(ipsecpolicy, profile=None):
    """
    Deletes the specified IPsecPolicy

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_ipsecpolicy ipsecpolicy-name

    :param ipsecpolicy: ID or name of IPSec policy to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_ipsecpolicy(ipsecpolicy)


def list_firewall_rules(profile=None):
    """
    Fetches a list of all firewall rules for a tenant
    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_firewall_rules

    :param profile: Profile to build on (Optional)

    :return: List of firewall rules
    """
    conn = _auth(profile)
    return conn.list_firewall_rules()


def show_firewall_rule(firewall_rule, profile=None):
    """
    Fetches information of a specific firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_firewall_rule firewall-rule-name

    :param ipsecpolicy: ID or name of firewall rule to look up

    :param profile: Profile to build on (Optional)

    :return: firewall rule information
    """
    conn = _auth(profile)
    return conn.show_firewall_rule(firewall_rule)


def create_firewall_rule(protocol, action, profile=None, **kwargs):
    """
    Creates a new firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_firewall_rule protocol action
                tenant_id=TENANT_ID name=NAME description=DESCRIPTION ip_version=IP_VERSION
                source_ip_address=SOURCE_IP_ADDRESS destination_ip_address=DESTINATION_IP_ADDRESS source_port=SOURCE_PORT
                destination_port=DESTINATION_PORT shared=SHARED enabled=ENABLED

    :param protocol: Protocol for the firewall rule, choose "tcp","udp","icmp" or "None".
    :param action: Action for the firewall rule, choose "allow" or "deny".
    :param tenant_id: The owner tenant ID. (Optional)
    :param name: Name for the firewall rule. (Optional)
    :param description: Description for the firewall rule. (Optional)
    :param ip_version: IP protocol version, default: 4. (Optional)
    :param source_ip_address: Source IP address or subnet. (Optional)
    :param destination_ip_address: Destination IP address or subnet. (Optional)
    :param source_port: Source port (integer in [1, 65535] or range in a:b). (Optional)
    :param destination_port: Destination port (integer in [1, 65535] or range in a:b). (Optional)
    :param shared: Set shared to True, default: False. (Optional)
    :param enabled: To enable this rule, default: True. (Optional)
    """
    conn = _auth(profile)
    return conn.create_firewall_rule(protocol, action, **kwargs)


def delete_firewall_rule(firewall_rule, profile=None):
    """
    Deletes the specified firewall_rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_firewall_rule firewall-rule

    :param firewall_rule: ID or name of firewall rule to delete
    :param profile: Profile to build on (Optional)
    :return: True(Succeed) or False
    """
    conn = _auth(profile)
    return conn.delete_firewall_rule(firewall_rule)


def update_firewall_rule(
    firewall_rule,
    protocol=None,
    action=None,
    name=None,
    description=None,
    ip_version=None,
    source_ip_address=None,
    destination_ip_address=None,
    source_port=None,
    destination_port=None,
    shared=None,
    enabled=None,
    profile=None,
):
    """
    Update a firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_firewall_rule firewall_rule protocol=PROTOCOL action=ACTION
                name=NAME description=DESCRIPTION ip_version=IP_VERSION
                source_ip_address=SOURCE_IP_ADDRESS destination_ip_address=DESTINATION_IP_ADDRESS
                source_port=SOURCE_PORT destination_port=DESTINATION_PORT shared=SHARED enabled=ENABLED

    :param firewall_rule: ID or name of firewall rule to update.
    :param protocol: Protocol for the firewall rule, choose "tcp","udp","icmp" or "None". (Optional)
    :param action: Action for the firewall rule, choose "allow" or "deny". (Optional)
    :param name: Name for the firewall rule. (Optional)
    :param description: Description for the firewall rule. (Optional)
    :param ip_version: IP protocol version, default: 4. (Optional)
    :param source_ip_address: Source IP address or subnet. (Optional)
    :param destination_ip_address: Destination IP address or subnet. (Optional)
    :param source_port: Source port (integer in [1, 65535] or range in a:b). (Optional)
    :param destination_port: Destination port (integer in [1, 65535] or range in a:b). (Optional)
    :param shared: Set shared to True, default: False. (Optional)
    :param enabled: To enable this rule, default: True. (Optional)
    :param profile: Profile to build on (Optional)
    """
    conn = _auth(profile)
    return conn.update_firewall_rule(
        firewall_rule,
        protocol,
        action,
        name,
        description,
        ip_version,
        source_ip_address,
        destination_ip_address,
        source_port,
        destination_port,
        shared,
        enabled,
    )


def list_firewalls(profile=None):
    """
    Fetches a list of all firewalls for a tenant
    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_firewalls

    :param profile: Profile to build on (Optional)
    :return: List of firewalls
    """
    conn = _auth(profile)
    return conn.list_firewalls()


def show_firewall(firewall, profile=None):
    """
    Fetches information of a specific firewall rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.show_firewall firewall

    :param firewall: ID or name of firewall to look up
    :param profile: Profile to build on (Optional)
    :return: firewall information
    """
    conn = _auth(profile)
    return conn.show_firewall(firewall)


def list_l3_agent_hosting_routers(router, profile=None):
    """
    List L3 agents hosting a router.

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_l3_agent_hosting_routers router

    :param router:router name or ID to query.
    :param profile: Profile to build on (Optional)
    :return: L3 agents message.
    """
    conn = _auth(profile)
    return conn.list_l3_agent_hosting_routers(router)


def list_agents(profile=None):
    """
    List agents.

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_agents

    :param profile: Profile to build on (Optional)
    :return: agents message.
    """
    conn = _auth(profile)
    return conn.list_agents()
