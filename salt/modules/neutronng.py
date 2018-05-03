# -*- coding: utf-8 -*-
'''
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
'''

from __future__ import absolute_import, print_function, unicode_literals

HAS_SHADE = False
try:
    import shade
    HAS_SHADE = True
except ImportError:
    pass

__virtualname__ = 'neutronng'


def __virtual__():
    '''
    Only load this module if shade python module is installed
    '''
    if HAS_SHADE:
        return __virtualname__
    return (False, 'The neutronng execution module failed to \
                    load: shade python module is not available')


def compare_changes(obj, **kwargs):
    '''
    Compare two dicts returning only keys that exist in the first dict and are
    different in the second one
    '''
    changes = {}
    for key, value in obj.items():
        if key in kwargs:
            if value != kwargs[key]:
                changes[key] = kwargs[key]
    return changes


def _clean_kwargs(keep_name=False, **kwargs):
    '''
    Sanatize the the arguments for use with shade
    '''
    if 'name' in kwargs and not keep_name:
        kwargs['name_or_id'] = kwargs.pop('name')

    return __utils__['args.clean_kwargs'](**kwargs)


def setup_clouds(auth=None):
    '''
    Call functions to create Shade cloud objects in __context__ to take
    advantage of Shade's in-memory caching across several states
    '''
    get_operator_cloud(auth)
    get_openstack_cloud(auth)


def get_operator_cloud(auth=None):
    '''
    Return an operator_cloud
    '''
    if auth is None:
        auth = __salt__['config.option']('neutron', {})
    if 'shade_opcloud' in __context__:
        if __context__['shade_opcloud'].auth == auth:
            return __context__['shade_opcloud']
    __context__['shade_opcloud'] = shade.operator_cloud(**auth)
    return __context__['shade_opcloud']


def get_openstack_cloud(auth=None):
    '''
    Return an openstack_cloud
    '''
    if auth is None:
        auth = __salt__['config.option']('neutron', {})
    if 'shade_oscloud' in __context__:
        if __context__['shade_oscloud'].auth == auth:
            return __context__['shade_oscloud']
    __context__['shade_oscloud'] = shade.openstack_cloud(**auth)
    return __context__['shade_oscloud']


def network_create(auth=None, **kwargs):
    '''
    Create a network

    Parameters:
    Defaults: shared=False, admin_state_up=True, external=False,
              provider=None, project_id=None

    name (string): Name of the network being created.
    shared (bool): Set the network as shared.
    admin_state_up (bool): Set the network administrative state to up.
    external (bool): Whether this network is externally accessible.
    provider (dict): A dict of network provider options.
    project_id (string): Specify the project ID this network will be created on.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_create name=network2 \
          shared=True admin_state_up=True external=True

        salt '*' neutronng.network_create name=network3 \
          provider='{"network_type": "vlan",\
                     "segmentation_id": "4010",\
                     "physical_network": "provider"}' \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_network(**kwargs)


def network_delete(auth=None, **kwargs):
    '''
    Delete a network

    Parameters:
    name: Name or ID of the network being deleted.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_delete name=network1
        salt '*' neutronng.network_delete \
          name=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_network(**kwargs)


def list_networks(auth=None, **kwargs):
    '''
    List networks

    Parameters:
    Defaults: filters=None

    filters (dict): dict of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.list_networks
        salt '*' neutronng.list_networks \
          filters='{"tenant_id": "1dcac318a83b4610b7a7f7ba01465548"}'

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_networks(**kwargs)


def network_get(auth=None, **kwargs):
    '''
    Get a single network

    Parameters:
    Defaults: filters=None

    filters (dict): dict of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.network_get name=XLB4

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_network(**kwargs)


def subnet_create(auth=None, **kwargs):
    '''
    Create a subnet

    Parameters:
    Defaults: cidr=None, ip_version=4, enable_dhcp=False, subnet_name=None,
              tenant_id=None, allocation_pools=None, gateway_ip=None,
              disable_gateway_ip=False, dns_nameservers=None, host_routes=None,
              ipv6_ra_mode=None, ipv6_address_mode=None,
              use_default_subnetpool=False

    allocation_pools:
    A list of dictionaries of the start and end addresses for allocation pools.

    dns_nameservers: A list of DNS name servers for the subnet.
    host_routes: A list of host route dictionaries for the subnet.

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

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.create_subnet(**kwargs)


def subnet_update(auth=None, **kwargs):
    '''
    Update a subnet

    Parameters:
    Defaults: subnet_name=None, enable_dhcp=None, gateway_ip=None,\
              disable_gateway_ip=None, allocation_pools=None, \
              dns_nameservers=None, host_routes=None

    name: Name or ID of the subnet to update.
    subnet_name: The new name of the subnet.

    .. code-block:: bash

        salt '*' neutronng.subnet_update name=subnet1 subnet_name=subnet2
        salt '*' neutronng.subnet_update name=subnet1\
          dns_nameservers='["8.8.8.8", "8.8.8.7"]'

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.update_subnet(**kwargs)


def subnet_delete(auth=None, **kwargs):
    '''
    Delete a subnet

    Parameters:
    name: Name or ID of the subnet to update.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.subnet_delete name=subnet1
        salt '*' neutronng.subnet_delete \
          name=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_subnet(**kwargs)


def list_subnets(auth=None, **kwargs):
    '''
    List subnets

    Parameters:
    Defaults: filters=None

    filters (dict): dict of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.list_subnets
        salt '*' neutronng.list_subnets \
          filters='{"tenant_id": "1dcac318a83b4610b7a7f7ba01465548"}'

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.list_subnets(**kwargs)


def subnet_get(auth=None, **kwargs):
    '''
    Get a single subnet

    Parameters:
    Defaults: filters=None

    filters (dict): dict of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.subnet_get name=subnet1

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_subnet(**kwargs)


def security_group_create(auth=None, **kwargs):
    '''
    Create a security group. Use security_group_get to create default.

    Parameters:
    Defaults: project_id=None

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_create name=secgroup1 \
          description="Very secure security group"
        salt '*' neutronng.security_group_create name=secgroup1 \
          description="Very secure security group" \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.create_security_group(**kwargs)


def security_group_update(secgroup=None, auth=None, **kwargs):
    '''
    Update a security group

    secgroup: Name, ID or Raw Object of the security group to update.
    name: New name for the security group.
    description: New description for the security group.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_update secgroup=secgroup1 \
          description="Very secure security group"
        salt '*' neutronng.security_group_update secgroup=secgroup1 \
          description="Very secure security group" \
          project_id=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(keep_name=True, **kwargs)
    return cloud.update_security_group(secgroup, **kwargs)


def security_group_delete(auth=None, **kwargs):
    '''
    Delete a security group

    Parameters:
    name: The name or unique ID of the security group.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_delete name=secgroup1

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_security_group(**kwargs)


def security_group_get(auth=None, **kwargs):
    '''
    Get a single security group. This will create a default security group
    if one does not exist yet for a particular project id.

    Parameters:
    Defaults: filters=None

    filters (dict): dict of filter conditions to push down

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_get \
          name=1dcac318a83b4610b7a7f7ba01465548

        salt '*' neutronng.security_group_get \
          name=default\
          filters='{"tenant_id":"2e778bb64ca64a199eb526b5958d8710"}'
    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.get_security_group(**kwargs)


def security_group_rule_create(auth=None, **kwargs):
    '''
    Create a rule in a security group

    Parameters:
    Defaults: port_range_min=None, port_range_max=None, protocol=None,
              remote_ip_prefix=None, remote_group_id=None, direction='ingress',
              ethertype='IPv4', project_id=None

    secgroup_name_or_id:
        This is the Name or Id of security group you want to create a rule in.
        However, it throws errors on non-unique security group names like
        'default' even when you supply a project_id

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

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.create_security_group_rule(**kwargs)


def security_group_rule_delete(auth=None, **kwargs):
    '''
    Delete a security group

    Parameters:
    rule_id (string): The unique ID of the security group rule.

    CLI Example:

    .. code-block:: bash

        salt '*' neutronng.security_group_rule_delete\
          rule_id=1dcac318a83b4610b7a7f7ba01465548

    '''
    cloud = get_operator_cloud(auth)
    kwargs = _clean_kwargs(**kwargs)
    return cloud.delete_security_group_rule(**kwargs)
