"""
Neutron module for interacting with OpenStack Neutron

.. versionadded:: 2018.3.0

:depends:shade

Example configuration

.. code-block:: yaml

    neutron:
      cloud: default

.. code-block:: yaml

    neutron:
      auth:
        username: admin
        password: password123
        user_domain_name: mydomain
        project_name: myproject
        project_domain_name: myproject
        auth_url: https://example.org:5000/v3
      identity_api_version: 3
"""


HAS_SHADE = False
try:
    import shade

    HAS_SHADE = True
except ImportError:
    pass

__virtualname__ = "neutronng"


def __virtual__():
    """
    Only load this module if shade python module is installed
    """
    if HAS_SHADE:
        return __virtualname__
    return (
        False,
        "The neutronng execution module failed to load: shade python module is not available",
    )


def compare_changes(obj, **kwargs):
    """
    Compare two dicts returning only keys that exist in the first dict and are
    different in the second one
    """
    changes = {}
    for key, value in obj.items():
        if key in kwargs:
            if value != kwargs[key]:
                changes[key] = kwargs[key]
    return changes


def _clean_kwargs(keep_name=False, **kwargs):
    """
    Sanatize the arguments for use with shade
    """
    if "name" in kwargs and not keep_name:
        kwargs["name_or_id"] = kwargs.pop("name")

    return __utils__["args.clean_kwargs"](**kwargs)


def setup_clouds(auth=None):
    """
    Call functions to create Shade cloud objects in __context__ to take
    advantage of Shade's in-memory caching across several states
    """
    get_operator_cloud(auth)
    get_openstack_cloud(auth)


def get_operator_cloud(auth=None):
    """
    Return an operator_cloud
    """
    if auth is None:
        auth = __salt__["config.option"]("neutron", {})
    if "shade_opcloud" in __context__:
        if __context__["shade_opcloud"].auth == auth:
            return __context__["shade_opcloud"]
    __context__["shade_opcloud"] = shade.operator_cloud(**auth)
    return __context__["shade_opcloud"]


def get_openstack_cloud(auth=None):
    """
    Return an openstack_cloud
    """
    if auth is None:
        auth = __salt__["config.option"]("neutron", {})
    if "shade_oscloud" in __context__:
        if __context__["shade_oscloud"].auth == auth:
            return __context__["shade_oscloud"]
    __context__["shade_oscloud"] = shade.openstack_cloud(**auth)
    return __context__["shade_oscloud"]


def network_create(auth=None, **kwargs):
    """
    Create a network

    name
        Name of the network being created

    shared : False
        If ``True``, set the network as shared

    admin_state_up : True
        If ``True``, Set the network administrative state to "up"

    external : False
        Control whether or not this network is externally accessible

    provider
        An optional Python dictionary of network provider options

    project_id
        The project ID on which this network will be created

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_create name=network2 \
          shared=True admin_state_up=True external=True

        salt '*' neutronng.network_create name=network3 \
          provider='{"network_type": "vlan",\
                     "segmentation_id": "4010",\
                     "physical_network": "provider"}' \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_network(**kwargs)


def network_delete(auth=None, **kwargs):
    """
    Delete a network

    name_or_id
        Name or ID of the network being deleted

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_delete name_or_id=network1
        salt '*' neutronng.network_delete name_or_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_network(**kwargs)


def list_networks(auth=None, **kwargs):
    """
    List networks

    filters
        A Python dictionary of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.list_networks
        salt '*' neutronng.list_networks \
          filters='{"tenant_id": "1dcac318a83b4610b7a7f7ba01465548"}'

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_networks(**kwargs)


def network_get(auth=None, **kwargs):
    """
    Get a single network

    filters
        A Python dictionary of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_get name=XLB4

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_network(**kwargs)


def subnet_create(auth=None, **kwargs):
    """
    Create a subnet

    network_name_or_id
        The unique name or ID of the attached network. If a non-unique name is
        supplied, an exception is raised.

    cidr
        The CIDR

    ip_version
        The IP version, which is 4 or 6.

    enable_dhcp : False
        Set to ``True`` if DHCP is enabled and ``False`` if disabled

    subnet_name
        The name of the subnet

    tenant_id
        The ID of the tenant who owns the network. Only administrative users
        can specify a tenant ID other than their own.

    allocation_pools
        A list of dictionaries of the start and end addresses for the
        allocation pools.

    gateway_ip
        The gateway IP address. When you specify both ``allocation_pools`` and
        ``gateway_ip``, you must ensure that the gateway IP does not overlap
        with the specified allocation pools.

    disable_gateway_ip : False
        Set to ``True`` if gateway IP address is disabled and ``False`` if
        enabled. It is not allowed with ``gateway_ip``.

    dns_nameservers
        A list of DNS name servers for the subnet

    host_routes
        A list of host route dictionaries for the subnet

    ipv6_ra_mode
        IPv6 Router Advertisement mode. Valid values are ``dhcpv6-stateful``,
        ``dhcpv6-stateless``, or ``slaac``.

    ipv6_address_mode
        IPv6 address mode. Valid values are ``dhcpv6-stateful``,
        ``dhcpv6-stateless``, or ``slaac``.

    use_default_subnetpool
        If ``True``, use the default subnetpool for ``ip_version`` to obtain a
        CIDR. It is required to pass ``None`` to the ``cidr`` argument when
        enabling this option.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.subnet_create network_name_or_id=network1
          subnet_name=subnet1

        salt '*' neutronng.subnet_create subnet_name=subnet2\
          network_name_or_id=network2 enable_dhcp=True \
          allocation_pools='[{"start": "192.168.199.2",\
                              "end": "192.168.199.254"}]'\
          gateway_ip='192.168.199.1' cidr=192.168.199.0/24

        salt '*' neutronng.subnet_create network_name_or_id=network1 \
          subnet_name=subnet1 dns_nameservers='["8.8.8.8", "8.8.8.7"]'

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.create_subnet(**kwargs)


def subnet_update(auth=None, **kwargs):
    """
    Update a subnet

    name_or_id
        Name or ID of the subnet to update

    subnet_name
        The new name of the subnet

    enable_dhcp
        Set to ``True`` if DHCP is enabled and ``False`` if disabled

    gateway_ip
        The gateway IP address. When you specify both allocation_pools and
        gateway_ip, you must ensure that the gateway IP does not overlap with
        the specified allocation pools.

    disable_gateway_ip : False
        Set to ``True`` if gateway IP address is disabled and False if enabled.
        It is not allowed with ``gateway_ip``.

    allocation_pools
        A list of dictionaries of the start and end addresses for the
        allocation pools.

    dns_nameservers
        A list of DNS name servers for the subnet

    host_routes
        A list of host route dictionaries for the subnet

    .. code-block:: bash

        salt '*' neutronng.subnet_update name=subnet1 subnet_name=subnet2
        salt '*' neutronng.subnet_update name=subnet1 dns_nameservers='["8.8.8.8", "8.8.8.7"]'

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_subnet(**kwargs)


def subnet_delete(auth=None, **kwargs):
    """
    Delete a subnet

    name
        Name or ID of the subnet to update

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.subnet_delete name=subnet1
        salt '*' neutronng.subnet_delete \
          name=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_subnet(**kwargs)


def list_subnets(auth=None, **kwargs):
    """
    List subnets

    filters
        A Python dictionary of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.list_subnets
        salt '*' neutronng.list_subnets \
          filters='{"tenant_id": "1dcac318a83b4610b7a7f7ba01465548"}'

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_subnets(**kwargs)


def subnet_get(auth=None, **kwargs):
    """
    Get a single subnet

    filters
        A Python dictionary of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.subnet_get name=subnet1

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_subnet(**kwargs)


def security_group_create(auth=None, **kwargs):
    """
    Create a security group. Use security_group_get to create default.

    project_id
        The project ID on which this security group will be created

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_create name=secgroup1 \
          description="Very secure security group"
        salt '*' neutronng.security_group_create name=secgroup1 \
          description="Very secure security group" \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_security_group(**kwargs)


def security_group_update(secgroup=None, auth=None, **kwargs):
    """
    Update a security group

    secgroup
        Name, ID or Raw Object of the security group to update

    name
        New name for the security group

    description
        New description for the security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_update secgroup=secgroup1 \
          description="Very secure security group"
        salt '*' neutronng.security_group_update secgroup=secgroup1 \
          description="Very secure security group" \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.update_security_group(secgroup, **kwargs)


def security_group_delete(auth=None, **kwargs):
    """
    Delete a security group

    name_or_id
        The name or unique ID of the security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_delete name_or_id=secgroup1

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_security_group(**kwargs)


def security_group_get(auth=None, **kwargs):
    """
    Get a single security group. This will create a default security group
    if one does not exist yet for a particular project id.

    filters
        A Python dictionary of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_get \
          name=1dcac318a83b4610b7a7f7ba01465548

        salt '*' neutronng.security_group_get \
          name=default\
          filters='{"tenant_id":"2e778bb64ca64a199eb526b5958d8710"}'
    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_security_group(**kwargs)


def security_group_rule_create(auth=None, **kwargs):
    """
    Create a rule in a security group

    secgroup_name_or_id
        The security group name or ID to associate with this security group
        rule. If a non-unique group name is given, an exception is raised.

    port_range_min
        The minimum port number in the range that is matched by the security
        group rule. If the protocol is TCP or UDP, this value must be less than
        or equal to the port_range_max attribute value. If nova is used by the
        cloud provider for security groups, then a value of None will be
        transformed to -1.

    port_range_max
        The maximum port number in the range that is matched by the security
        group rule. The port_range_min attribute constrains the port_range_max
        attribute. If nova is used by the cloud provider for security groups,
        then a value of None will be transformed to -1.

    protocol
        The protocol that is matched by the security group rule.  Valid values
        are ``None``, ``tcp``, ``udp``, and ``icmp``.

    remote_ip_prefix
        The remote IP prefix to be associated with this security group rule.
        This attribute matches the specified IP prefix as the source IP address
        of the IP packet.

    remote_group_id
        The remote group ID to be associated with this security group rule

    direction
        Either ``ingress`` or ``egress``; the direction in which the security
        group rule is applied. For a compute instance, an ingress security
        group rule is applied to incoming (ingress) traffic for that instance.
        An egress rule is applied to traffic leaving the instance

    ethertype
        Must be IPv4 or IPv6, and addresses represented in CIDR must match the
        ingress or egress rules

    project_id
        Specify the project ID this security group will be created on
        (admin-only)

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_rule_create\
          secgroup_name_or_id=secgroup1

        salt '*' neutronng.security_group_rule_create\
          secgroup_name_or_id=secgroup2 port_range_min=8080\
          port_range_max=8080 direction='egress'

        salt '*' neutronng.security_group_rule_create\
          secgroup_name_or_id=c0e1d1ce-7296-405e-919d-1c08217be529\
          protocol=icmp project_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.create_security_group_rule(**kwargs)


def security_group_rule_delete(auth=None, **kwargs):
    """
    Delete a security group

    name_or_id
        The unique ID of the security group rule

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_rule_delete name_or_id=1dcac318a83b4610b7a7f7ba01465548

    """
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_security_group_rule(**kwargs)
