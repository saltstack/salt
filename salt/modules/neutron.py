# -*- coding: utf-8 -*-
'''
Module for handling openstack neutron calls.

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:platform: all

:optdepends:    - neutronclient Python adapter
:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        keystone.user: admin
        keystone.password: verybadpass
        keystone.tenant: admin
        keystone.tenant_id: f80919baedab48ec8931f200c65a50df
        keystone.insecure: False   #(optional)
        keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

    If configuration for multiple openstack accounts is required, they can be
    set up as different configuration profiles:
    For example::

        openstack1:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.tenant_id: f80919baedab48ec8931f200c65a50df
          keystone.auth_url: 'http://127.0.0.1:5000/v2.0/'

        openstack2:
          keystone.user: admin
          keystone.password: verybadpass
          keystone.tenant: admin
          keystone.tenant_id: f80919baedab48ec8931f200c65a50df
          keystone.auth_url: 'http://127.0.0.2:5000/v2.0/'

    With this configuration in place, any of the neutron functions can make
    use of a configuration profile by declaring it explicitly.
    For example::

        salt '*' neutron.list_subnets profile=openstack1

    Please check 'https://wiki.openstack.org/wiki/Neutron/APIv2-specification'
    for the correct arguments to the api
'''


import logging
from functools import wraps
LOG = logging.getLogger(__name__)
# Import third party libs
HAS_NEUTRON = False
try:
    from neutronclient.v2_0 import client
    HAS_NEUTRON = True
except ImportError:
    pass


__opts__ = {}


def __virtual__():
    '''
    Only load this module if neutron
    is installed on this minion.
    '''
    if HAS_NEUTRON:
        return 'neutron'
    return False


def _autheticate(func_name):
    '''
    Authenticate requests with the salt keystone module and format return data
    '''
    @wraps(func_name)
    def decorator_method(*args, **kwargs):
        '''
        Authenticate request and format return data
        '''
        connection_args = {'profile': kwargs.get('profile', None)}
        nkwargs = {}
        for kwarg in kwargs:
            if 'connection_' in kwarg:
                connection_args.update({kwarg: kwargs[kwarg]})
            elif '__' not in kwarg:
                nkwargs.update({kwarg: kwargs[kwarg]})
        kstone = __salt__['keystone.auth'](**connection_args)
        token = kstone.auth_token
        endpoint = kstone.service_catalog.url_for(
            service_type='network',
            endpoint_type='publicURL')
        neutron_interface = client.Client(
            endpoint_url=endpoint, token=token)
        LOG.error('calling with args ' + str(args))
        LOG.error('calling with kwargs ' + str(nkwargs))
        return_data = func_name(neutron_interface, *args, **nkwargs)
        LOG.error('got return data ' + str(return_data))
        if isinstance(return_data, list):
            # format list as a dict for rendering
            return {data.get('name', None) or data['id']: data
                    for data in return_data}
        return return_data
    return decorator_method


@_autheticate
def list_floatingips(neutron_interface, **kwargs):
    '''
    list all floatingips

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_floatingips
    '''
    return neutron_interface.list_floatingips(**kwargs)['floatingips']


@_autheticate
def list_security_groups(neutron_interface, **kwargs):
    '''
    list all security_groups

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_security_groups
    '''
    return neutron_interface.list_security_groups(**kwargs)['security_groups']


@_autheticate
def list_subnets(neutron_interface, **kwargs):
    '''
    list all subnets

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_subnets
    '''
    return neutron_interface.list_subnets(**kwargs)['subnets']


@_autheticate
def list_networks(neutron_interface, **kwargs):
    '''
    list all networks

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_networks
    '''
    return neutron_interface.list_networks(**kwargs)['networks']


@_autheticate
def list_ports(neutron_interface, **kwargs):
    '''
    list all ports

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_ports
    '''
    return neutron_interface.list_ports(**kwargs)['ports']


@_autheticate
def list_routers(neutron_interface, **kwargs):
    '''
    list all routers

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.list_routers
    '''
    return neutron_interface.list_routers(**kwargs)['routers']


@_autheticate
def update_floatingip(neutron_interface, fip, port_id=None):
    '''
    update floating IP. Should be used to associate and disassociate
    floating IP with instance

    CLI Example:

    .. code-block:: bash

        to associate with an instance's port
        salt '*' neutron.update_floatingip openstack-floatingip-id port-id

        to disassociate from an instance's port
        salt '*' neutron.update_floatingip openstack-floatingip-id
    '''
    neutron_interface.update_floatingip(fip, {"floatingip":
                                              {"port_id": port_id}})


@_autheticate
def update_subnet(neutron_interface, subnet_id, **subnet_params):
    '''
    update given subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_subnet openstack-subnet-id name='new_name'
    '''
    neutron_interface.update_subnet(subnet_id, {'subnet': subnet_params})


@_autheticate
def update_router(neutron_interface, router_id, **router_params):
    '''
    update given router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_router openstack-router-id name='new_name'
            external_gateway='openstack-network-id' administrative_state=true
    '''
    neutron_interface.update_router(router_id, {'router': router_params})


@_autheticate
def router_gateway_set(neutron_interface, router_id, external_gateway):
    '''
    Set external gateway for a router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_router openstack-router-id openstack-network-id
    '''
    neutron_interface.update_router(
        router_id, {'router': {'external_gateway_info':
                               {'network_id': external_gateway}}})


@_autheticate
def router_gateway_clear(neutron_interface, router_id):
    '''
    Clear external gateway for a router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_router openstack-router-id
    '''
    neutron_interface.update_router(
        router_id, {'router': {'external_gateway_info': None}})


@_autheticate
def create_router(neutron_interface, **router_params):
    '''
    Create OpenStack Neutron router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_router openstack-router-id name=External
            provider_network_type=flat provider_physical_network=ext
    '''
    response = neutron_interface.create_router({'router': router_params})
    if 'router' in response and 'id' in response['router']:
        return response['router']['id']


@_autheticate
def router_add_interface(neutron_interface, router_id, subnet_id):
    '''
    Attach router to a subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.router_add_interface openstack-router-id subnet-id
    '''
    neutron_interface.add_interface_router(router_id, {'subnet_id': subnet_id})


@_autheticate
def router_rem_interface(neutron_interface, router_id, subnet_id):
    '''
    Dettach router from a subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.router_rem_interface openstack-router-id subnet-id
    '''
    neutron_interface.remove_interface_router(
        router_id, {'subnet_id': subnet_id})


@_autheticate
def create_security_group(neutron_interface, **sg_params):
    '''
    Create a new security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_security_group name='new_rule'
            description='test rule'
    '''
    response = neutron_interface.create_security_group(
        {'security_group': sg_params})
    if 'security_group' in response and 'id' in response['security_group']:
        return response['security_group']['id']


@_autheticate
def create_security_group_rule(neutron_interface, **rule_params):
    '''
    Create a rule entry for a security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_security_group_rule
    '''
    neutron_interface.create_security_group_rule(
        {'security_group_rule': rule_params})


@_autheticate
def create_floatingip(neutron_interface, **floatingip_params):
    '''
    Create a new floating IP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_floatingip floating_network_id=ext-net-id
    '''
    response = neutron_interface.create_floatingip(
        {'floatingip': floatingip_params})
    if 'floatingip' in response and 'id' in response['floatingip']:
        return response['floatingip']['id']


@_autheticate
def create_subnet(neutron_interface, **subnet_params):
    '''
    Create a new subnet in OpenStack

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_subnet name='subnet name'
            network_id='openstack-network-id' cidr='192.168.10.0/24' \\
            gateway_ip='192.168.10.1' ip_version='4' enable_dhcp=false \\
            start_ip='192.168.10.10' end_ip='192.168.10.20'
    '''
    if 'start_ip' in subnet_params:
        subnet_params.update(
            {'allocation_pools': [{'start': subnet_params.pop('start_ip'),
                                   'end': subnet_params.pop('end_ip', None)}]})
    response = neutron_interface.create_subnet({'subnet': subnet_params})
    if 'subnet' in response and 'id' in response['subnet']:
        return response['subnet']['id']


@_autheticate
def create_network(neutron_interface, **network_params):
    '''
    Create a new network segment in OpenStack

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_network name='network-name'
    '''
    network_params = {param.replace('_', ':', 1):
                      network_params[param] for param in network_params}
    response = neutron_interface.create_network({'network': network_params})
    if 'network' in response and 'id' in response['network']:
        return response['network']['id']


@_autheticate
def create_port(neutron_interface, **port_params):
    '''
    Create a new port in OpenStack

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.create_port network_id='openstack-network-id'
    '''
    response = neutron_interface.create_port({'port': port_params})
    if 'port' in response and 'id' in response['port']:
        return response['port']['id']


@_autheticate
def update_port(neutron_interface, port_id, **port_params):
    '''
    Create a new port in OpenStack

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.update_port name='new_port_name'
    '''
    neutron_interface.update_port(port_id, {'port': port_params})


@_autheticate
def delete_floatingip(neutron_interface, floating_ip_id):
    '''
    delete a floating IP

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_floatingip openstack-floating-ip-id
    '''
    neutron_interface.delete_floatingip(floating_ip_id)


@_autheticate
def delete_security_group(neutron_interface, sg_id):
    '''
    delete a security group

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_security_group openstack-security-group-id
    '''
    neutron_interface.delete_security_group(sg_id)


@_autheticate
def delete_security_group_rule(neutron_interface, rule):
    '''
    delete a security group rule. pass all rule params that match the rule
    to be deleted

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_security_group_rule direction='ingress'
            ethertype='ipv4' security_group_id='openstack-security-group-id'
            port_range_min=100 port_range_max=4096 protocol='tcp'
            remote_group_id='default'
    '''
    sg_rules = neutron_interface.list_security_group_rules(
        security_group_id=rule['security_group_id'])
    for sg_rule in sg_rules['security_group_rules']:
        sgr_id = sg_rule.pop('id')
        if sg_rule == rule:
            neutron_interface.delete_security_group_rule(sgr_id)


@_autheticate
def delete_subnet(neutron_interface, subnet_id):
    '''
    delete given subnet

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_subnet openstack-subnet-id
    '''
    neutron_interface.delete_subnet(subnet_id)


@_autheticate
def delete_network(neutron_interface, network_id):
    '''
    delete given network

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_network openstack-network-id
    '''
    neutron_interface.delete_network(network_id)


@_autheticate
def delete_router(neutron_interface, router_id):
    '''
    delete given router

    CLI Example:

    .. code-block:: bash

        salt '*' neutron.delete_router openstack-router-id
    '''
    neutron_interface.delete_router(router_id)
