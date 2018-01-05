# -*- coding: utf-8 -*-
'''
Azure Cloud Module
==================

.. versionadded:: 2016.11.0

The Azure cloud module is used to control access to Microsoft Azure

:depends:
    * `Microsoft Azure SDK for Python <https://pypi.python.org/pypi/azure>`_ >= 2.0rc5
    * `Microsoft Azure Storage SDK for Python <https://pypi.python.org/pypi/azure-storage>`_ >= 0.32
    * `Microsoft Azure CLI <https://pypi.python.org/pypi/azure-cli>` >= 2.0.12
:configuration:
    Required provider parameters:

    if using username and password:
    * ``subscription_id``
    * ``username``
    * ``password``

    if using a service principal:
    * ``subscription_id``
    * ``tenant``
    * ``client_id``
    * ``secret``

Example ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/azure.conf`` configuration:

.. code-block:: yaml

    my-azure-config with username and password:
      driver: azure
      subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
      username: larry
      password: 123pass

    Or my-azure-config with service principal:
      driver: azure
      subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
      tenant: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
      client_id: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
      secret: XXXXXXXXXXXXXXXXXXXXXXXX

      The Service Principal can be created with the new Azure CLI (https://github.com/Azure/azure-cli) with:
      az ad sp create-for-rbac -n "http://<yourappname>" --role <role> --scopes <scope>
      For example, this creates a service principal with 'owner' role for the whole subscription:
      az ad sp create-for-rbac -n "http://mysaltapp" --role owner --scopes /subscriptions/3287abc8-f98a-c678-3bde-326766fd3617
      *Note: review the details of Service Principals. Owner role is more than you normally need, and you can restrict scope to a resource group or individual resources.
'''
# pylint: disable=E0102

# pylint: disable=wrong-import-position,wrong-import-order
from __future__ import absolute_import, print_function, unicode_literals
import os
import os.path
import time
import logging
import pprint
import base64
import collections
import salt.cache
import salt.config as config
import salt.utils.cloud
import salt.utils.data
import salt.utils.files
import salt.utils.yaml
from salt.utils.versions import LooseVersion
from salt.ext import six
import salt.version
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
)
from salt.ext.six.moves import filter

# Import 3rd-party libs
HAS_LIBS = False
try:
    import salt.utils.msazure
    from salt.utils.msazure import object_to_dict
    from azure.common.credentials import (
        UserPassCredentials,
        ServicePrincipalCredentials,
    )
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.compute.models import (
        CachingTypes,
        DataDisk,
        DiskCreateOptionTypes,
        HardwareProfile,
        ImageReference,
        NetworkInterfaceReference,
        NetworkProfile,
        OSDisk,
        OSProfile,
        StorageProfile,
        SubResource,
        VirtualHardDisk,
        VirtualMachine,
        VirtualMachineSizeTypes,
    )
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.network.models import (
        IPAllocationMethod,
        NetworkInterface,
        NetworkInterfaceDnsSettings,
        NetworkInterfaceIPConfiguration,
        NetworkSecurityGroup,
        PublicIPAddress,
        SecurityRule,
    )
    from azure.mgmt.resource.resources import ResourceManagementClient
    from azure.mgmt.storage import StorageManagementClient
    from azure.mgmt.web import WebSiteManagementClient
    from msrestazure.azure_exceptions import CloudError
    from azure.multiapi.storage.v2016_05_31 import CloudStorageAccount
    from azure.cli import core
    HAS_LIBS = LooseVersion(core.__version__) >= LooseVersion("2.0.12")
except ImportError:
    pass
# pylint: enable=wrong-import-position,wrong-import-order

__virtualname__ = 'azurearm'
# pylint: disable=invalid-name
cache = None
storconn = None
compconn = None
netconn = None
webconn = None
resconn = None
# pylint: enable=invalid-name


# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the AZURE configurations are in place
def __virtual__():
    '''
    Check for Azure configurations.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return (
            False,
            'The following dependencies are required to use the AzureARM driver: '
            'Microsoft Azure SDK for Python >= 2.0rc5, '
            'Microsoft Azure Storage SDK for Python >= 0.32, '
            'Microsoft Azure CLI >= 2.0.12'
        )

    global cache  # pylint: disable=global-statement,invalid-name
    cache = salt.cache.Cache(__opts__)

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    provider = config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('subscription_id', 'tenant', 'client_id', 'secret')
        )
    if provider is False:
        return config.is_provider_configured(
            __opts__,
            __active_provider_name__ or __virtualname__,
            ('subscription_id', 'username', 'password')
        )
    else:
        return provider


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'azurearm': HAS_LIBS}
    )


def get_conn(Client=None):
    '''
    Return a conn object for the passed VM data
    '''
    if Client is None:
        Client = ComputeManagementClient

    subscription_id = config.get_cloud_config_value(
        'subscription_id',
        get_configured_provider(), __opts__, search_global=False
    )

    tenant = config.get_cloud_config_value(
        'tenant',
        get_configured_provider(), __opts__, search_global=False
    )
    if tenant is not None:
        client_id = config.get_cloud_config_value(
            'client_id',
            get_configured_provider(), __opts__, search_global=False
        )
        secret = config.get_cloud_config_value(
            'secret',
            get_configured_provider(), __opts__, search_global=False
        )
        credentials = ServicePrincipalCredentials(client_id, secret, tenant=tenant)
    else:
        username = config.get_cloud_config_value(
            'username',
            get_configured_provider(), __opts__, search_global=False
        )
        password = config.get_cloud_config_value(
            'password',
            get_configured_provider(), __opts__, search_global=False
        )
        credentials = UserPassCredentials(username, password)

    client = Client(
        credentials=credentials,
        subscription_id=subscription_id,
    )
    client.config.add_user_agent('SaltCloud/{0}'.format(salt.version.__version__))
    return client


def get_location():
    '''
    Return the location that is configured for this provider
    '''
    return config.get_cloud_config_value(
        'location',
        get_configured_provider(), __opts__, search_global=False
    )


def avail_locations(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available locations for Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    global webconn  # pylint: disable=global-statement,invalid-name
    if not webconn:
        webconn = get_conn(WebSiteManagementClient)

    ret = {}
    regions = webconn.global_model.get_subscription_geo_regions()
    if hasattr(regions, 'value'):
        regions = regions.value
    for location in regions:  # pylint: disable=no-member
        lowername = six.text_type(location.name).lower().replace(' ', '')
        ret[lowername] = object_to_dict(location)
    return ret


def avail_images(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List available images for Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}'.format(region)
    publishers = cache.cache(
        bank,
        'publishers',
        compconn.virtual_machine_images.list_publishers,
        loop_fun=object_to_dict,
        expire=config.get_cloud_config_value(
            'expire_publisher_cache', get_configured_provider(),
            __opts__, search_global=False, default=604800,  # 7 days
        ),
        location=region,
    )

    ret = {}
    for publisher in publishers:
        pub_bank = os.path.join(bank, 'publishers', publisher['name'])
        offers = cache.cache(
            pub_bank,
            'offers',
            compconn.virtual_machine_images.list_offers,
            loop_fun=object_to_dict,
            expire=config.get_cloud_config_value(
                'expire_offer_cache', get_configured_provider(),
                __opts__, search_global=False, default=518400,  # 6 days
            ),
            location=region,
            publisher_name=publisher['name'],
        )

        for offer in offers:
            offer_bank = os.path.join(pub_bank, 'offers', offer['name'])
            skus = cache.cache(
                offer_bank,
                'skus',
                compconn.virtual_machine_images.list_skus,
                loop_fun=object_to_dict,
                expire=config.get_cloud_config_value(
                    'expire_sku_cache', get_configured_provider(),
                    __opts__, search_global=False, default=432000,  # 5 days
                ),
                location=region,
                publisher_name=publisher['name'],
                offer=offer['name'],
            )

            for sku in skus:
                sku_bank = os.path.join(offer_bank, 'skus', sku['name'])
                results = cache.cache(
                    sku_bank,
                    'results',
                    compconn.virtual_machine_images.list,
                    loop_fun=object_to_dict,
                    expire=config.get_cloud_config_value(
                        'expire_version_cache', get_configured_provider(),
                        __opts__, search_global=False, default=345600,  # 4 days
                    ),
                    location=region,
                    publisher_name=publisher['name'],
                    offer=offer['name'],
                    skus=sku['name'],
                )

                for version in results:
                    name = '|'.join((
                        publisher['name'],
                        offer['name'],
                        sku['name'],
                        version['name'],
                    ))
                    ret[name] = {
                        'publisher': publisher['name'],
                        'offer': offer['name'],
                        'sku': sku['name'],
                        'version': version['name'],
                    }
    return ret


def avail_sizes(call=None):  # pylint: disable=unused-argument
    '''
    Return a list of sizes from Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    ret = {}
    location = get_location()
    sizes = compconn.virtual_machine_sizes.list(location)
    for size in sizes:
        ret[size.name] = object_to_dict(size)
    return ret


def list_nodes(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Azure Active Provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    nodes = list_nodes_full(compconn, call)

    active_resource_group = None
    try:
        provider, driver = __active_provider_name__.split(':')
        active_resource_group = __opts__['providers'][provider][driver]['resource_group']
    except KeyError:
        pass

    for node in nodes:
        if active_resource_group is not None:
            if nodes[node]['resource_group'] != active_resource_group:
                continue
        ret[node] = {'name': node}
        for prop in ('id', 'image', 'size', 'state', 'private_ips', 'public_ips'):
            ret[node][prop] = nodes[node].get(prop)
    return ret


def list_nodes_full(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Azure account, with full information
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    ret = {}
    for group in list_resource_groups():
        nodes = compconn.virtual_machines.list(group)
        for node in nodes:
            private_ips, public_ips = __get_ips_from_node(group, node)
            ret[node.name] = object_to_dict(node)
            ret[node.name]['id'] = node.id
            ret[node.name]['name'] = node.name
            ret[node.name]['size'] = node.hardware_profile.vm_size
            ret[node.name]['state'] = node.provisioning_state
            ret[node.name]['private_ips'] = private_ips
            ret[node.name]['public_ips'] = public_ips
            ret[node.name]['storage_profile']['data_disks'] = []
            ret[node.name]['resource_group'] = group
            for disk in node.storage_profile.data_disks:
                ret[node.name]['storage_profile']['data_disks'].append(make_safe(disk))
            try:
                ret[node.name]['image'] = '|'.join((
                    ret[node.name]['storage_profile']['image_reference']['publisher'],
                    ret[node.name]['storage_profile']['image_reference']['offer'],
                    ret[node.name]['storage_profile']['image_reference']['sku'],
                    ret[node.name]['storage_profile']['image_reference']['version'],
                ))
            except TypeError:
                try:
                    ret[node.name]['image'] = ret[node.name]['storage_profile']['os_disk']['image']['uri']
                except TypeError:
                    ret[node.name]['image'] = None
    return ret


def __get_ips_from_node(resource_group, node):
    '''
    List private and public IPs from a VM interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    private_ips = []
    public_ips = []
    for node_iface in node.network_profile.network_interfaces:
        node_iface_name = node_iface.id.split('/')[-1]
        network_interface = netconn.network_interfaces.get(resource_group, node_iface_name)
        for ip_configuration in network_interface.ip_configurations:
            if ip_configuration.private_ip_address:
                private_ips.append(ip_configuration.private_ip_address)
            if ip_configuration.public_ip_address and ip_configuration.public_ip_address.id:
                public_iface_name = ip_configuration.public_ip_address.id.split('/')[-1]
                public_iface = netconn.public_ip_addresses.get(resource_group, public_iface_name)
                public_ips.append(public_iface.ip_address)

    return private_ips, public_ips


def list_resource_groups(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List resource groups associated with the account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_hosted_services function must be called with '
            '-f or --function'
        )

    global resconn  # pylint: disable=global-statement,invalid-name
    if not resconn:
        resconn = get_conn(ResourceManagementClient)

    ret = {}

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}'.format(region)
    groups = cache.cache(
        bank,
        'resource_groups',
        resconn.resource_groups.list,
        loop_fun=object_to_dict,
        expire=config.get_cloud_config_value(
            'expire_group_cache', get_configured_provider(),
            __opts__, search_global=False, default=14400,
        )
    )

    for group in groups:
        ret[group['name']] = group
    return ret


def list_nodes_select(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(conn, 'function'), __opts__['query.selection'], call,
    )


def show_instance(name, resource_group=None, call=None):  # pylint: disable=unused-argument
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    data = None
    if resource_group is None:
        for group in list_resource_groups():
            try:
                instance = compconn.virtual_machines.get(group, name)
                data = object_to_dict(instance)
                resource_group = group
            except CloudError:
                continue

    # Find under which cloud service the name is listed, if any
    if data is None:
        return {}

    ifaces = {}
    if 'network_profile' not in data:
        data['network_profile'] = {}

    if 'network_interfaces' not in data['network_profile']:
        data['network_profile']['network_interfaces'] = []

    for iface in data['network_profile']['network_interfaces']:
        iface_name = iface.id.split('/')[-1]
        iface_data = show_interface(kwargs={
            'resource_group': resource_group,
            'iface_name': iface_name,
            'name': name,
        })
        ifaces[iface_name] = iface_data

    data['network_profile']['network_interfaces'] = ifaces
    data['resource_group'] = resource_group

    __utils__['cloud.cache_node'](
        salt.utils.data.simple_types_filter(data),
        __active_provider_name__,
        __opts__
    )
    return data


def list_networks(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List virtual networks
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}/virtual_networks'.format(region)

    if kwargs is None:
        kwargs = {}

    if 'group' in kwargs:
        groups = [kwargs['group']]
    else:
        groups = list_resource_groups()

    ret = {}
    for group in groups:
        try:
            networks = cache.cache(
                bank,
                group,
                netconn.virtual_networks.list,
                loop_fun=make_safe,
                expire=config.get_cloud_config_value(
                    'expire_network_cache', get_configured_provider(),
                    __opts__, search_global=False, default=3600,
                ),
                resource_group_name=group,
            )
        except CloudError:
            networks = {}
        for vnet in networks:
            ret[vnet['name']] = make_safe(vnet)
            ret[vnet['name']]['subnets'] = list_subnets(
                kwargs={'group': group, 'network': vnet['name']}
            )

    return ret


def list_subnets(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List subnets in a virtual network
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if 'group' in kwargs and 'resource_group' not in kwargs:
        kwargs['resource_group'] = kwargs['group']

    if 'resource_group' not in kwargs:
        raise SaltCloudSystemExit(
            'A resource_group must be specified as "group" or "resource_group"'
        )

    if 'network' not in kwargs:
        raise SaltCloudSystemExit(
            'A "network" must be specified'
        )

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}/{1}'.format(region, kwargs['network'])

    ret = {}
    subnets = netconn.subnets.list(kwargs['resource_group'], kwargs['network'])
    for subnet in subnets:
        ret[subnet.name] = make_safe(subnet)
        ret[subnet.name]['ip_configurations'] = {}
        if subnet.ip_configurations:
            for ip_ in subnet.ip_configurations:
                comps = ip_.id.split('/')
                name = comps[-1]
                ret[subnet.name]['ip_configurations'][name] = make_safe(ip_)
                ret[subnet.name]['ip_configurations'][name]['subnet'] = subnet.name
        ret[subnet.name]['resource_group'] = kwargs['resource_group']
    return ret


def delete_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    ips = []
    iface = netconn.network_interfaces.get(
        kwargs['resource_group'],
        kwargs['iface_name'],
    )
    iface_name = iface.name
    for ip_ in iface.ip_configurations:
        ips.append(ip_.name)

    poller = netconn.network_interfaces.delete(
        kwargs['resource_group'],
        kwargs['iface_name'],
    )
    poller.wait()

    for ip_ in ips:
        poller = netconn.public_ip_addresses.delete(kwargs['resource_group'], ip_)
        poller.wait()

    return {iface_name: ips}


def delete_ip(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    return netconn.public_ip_addresses.delete(
        kwargs['resource_group'],
        kwargs['ip_name'],
    )


def show_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('group'):
        kwargs['resource_group'] = kwargs['group']

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    iface_name = kwargs.get('iface_name', kwargs.get('name'))
    iface = netconn.network_interfaces.get(
        kwargs['resource_group'],
        iface_name,
    )
    data = object_to_dict(iface)
    data['resource_group'] = kwargs['resource_group']
    data['ip_configurations'] = {}
    for ip_ in iface.ip_configurations:
        data['ip_configurations'][ip_.name] = make_safe(ip_)
        if ip_.public_ip_address is not None:
            try:
                pubip = netconn.public_ip_addresses.get(
                    kwargs['resource_group'],
                    ip_.name,
                )
                data['ip_configurations'][ip_.name]['public_ip_address']['ip_address'] = pubip.ip_address
            except Exception as exc:
                log.warning('There was a %s cloud error: %s', type(exc), exc)
                continue

    return data


def list_ip_configurations(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List IP configurations
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if 'group' not in kwargs:
        if 'resource_group' in kwargs:
            kwargs['group'] = kwargs['resource_group']
        else:
            raise SaltCloudSystemExit(
                'A resource_group must be specified as "group" or "resource_group"'
            )

    ip_conf = {}
    for ip_ in kwargs.get('ip_configurations', []):
        ip_data = object_to_dict(ip_)
        ip_conf[ip_data['name']] = ip_data
        try:
            pub_ip = netconn.public_ip_addresses.get(  # pylint: disable=no-member
                kwargs['resource_group'], ip_data['name']
            ).ip_address
            ip_conf[ip_data['name']]['public_ip_address'] = pub_ip
        except CloudError:
            # There is no public IP on this interface
            pass
    return ip_conf


def list_interfaces(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = kwargs.get('group')

    if kwargs['resource_group'] is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True,
            default=config.get_cloud_config_value(
                'group', {}, __opts__, search_global=True
            )
        )

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}'.format(region)
    interfaces = cache.cache(
        bank,
        'network_interfaces',
        netconn.network_interfaces.list,
        loop_fun=make_safe,
        expire=config.get_cloud_config_value(
            'expire_interface_cache', get_configured_provider(),
            __opts__, search_global=False, default=3600,
        ),
        resource_group_name=kwargs['resource_group']
    )
    ret = {}
    for interface in interfaces:
        ret[interface['name']] = interface
    return ret


def create_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}
    vm_ = kwargs

    if kwargs.get('location') is None:
        kwargs['location'] = get_location()

    if kwargs.get('network') is None:
        kwargs['network'] = config.get_cloud_config_value(
            'network', vm_, __opts__, search_global=True
        )

    if kwargs.get('subnet') is None:
        kwargs['subnet'] = config.get_cloud_config_value(
            'subnet', vm_, __opts__, default='default', search_global=True
        )

    if kwargs.get('iface_name') is None:
        kwargs['iface_name'] = '{0}-iface0'.format(vm_['name'])

    backend_pools = None
    if kwargs.get('load_balancer') and kwargs.get('backend_pool'):
        load_balancer_obj = netconn.load_balancers.get(
            resource_group_name=kwargs['network_resource_group'],
            load_balancer_name=kwargs['load_balancer'],
        )
        backend_pools = list(filter(
            lambda backend: backend.name == kwargs['backend_pool'],
            load_balancer_obj.backend_address_pools,
        ))

    subnet_obj = netconn.subnets.get(
        resource_group_name=kwargs['network_resource_group'],
        virtual_network_name=kwargs['network'],
        subnet_name=kwargs['subnet'],
    )

    ip_kwargs = {}
    ip_configurations = None

    if 'private_ip_address' in kwargs.keys():
        ip_kwargs['private_ip_address'] = kwargs['private_ip_address']
        ip_kwargs['private_ip_allocation_method'] = IPAllocationMethod.static
    else:
        ip_kwargs['private_ip_allocation_method'] = IPAllocationMethod.dynamic

    if bool(kwargs.get('public_ip')) is True:
        pub_ip_name = '{0}-ip'.format(kwargs['iface_name'])
        poller = netconn.public_ip_addresses.create_or_update(
            resource_group_name=kwargs['resource_group'],
            public_ip_address_name=pub_ip_name,
            parameters=PublicIPAddress(
                location=kwargs['location'],
                public_ip_allocation_method=IPAllocationMethod.static,
            ),
        )
        count = 0
        poller.wait()
        while True:
            try:
                pub_ip_data = netconn.public_ip_addresses.get(
                    kwargs['resource_group'],
                    pub_ip_name,
                )
                if pub_ip_data.ip_address:  # pylint: disable=no-member
                    ip_kwargs['public_ip_address'] = PublicIPAddress(
                        six.text_type(pub_ip_data.id),  # pylint: disable=no-member
                    )
                    ip_configurations = [
                        NetworkInterfaceIPConfiguration(
                            name='{0}-ip'.format(kwargs['iface_name']),
                            load_balancer_backend_address_pools=backend_pools,
                            subnet=subnet_obj,
                            **ip_kwargs
                        )
                    ]
                    break
            except CloudError as exc:
                log.error('There was a cloud error: %s', exc)
            count += 1
            if count > 120:
                raise ValueError('Timed out waiting for public IP Address.')
            time.sleep(5)
    else:
        priv_ip_name = '{0}-ip'.format(kwargs['iface_name'])
        ip_configurations = [
            NetworkInterfaceIPConfiguration(
                name='{0}-ip'.format(kwargs['iface_name']),
                load_balancer_backend_address_pools=backend_pools,
                subnet=subnet_obj,
                **ip_kwargs
            )
        ]

    dns_settings = None
    if kwargs.get('dns_servers') is not None:
        if isinstance(kwargs['dns_servers'], list):
            dns_settings = NetworkInterfaceDnsSettings(
                dns_servers=kwargs['dns_servers'],
                applied_dns_servers=kwargs['dns_servers'],
                internal_dns_name_label=None,
                internal_fqdn=None,
                internal_domain_name_suffix=None,
            )

    network_security_group = None
    if kwargs.get('security_group') is not None:
        network_security_group = netconn.network_security_groups.get(
            resource_group_name=kwargs['resource_group'],
            network_security_group_name=kwargs['security_group'],
        )

    iface_params = NetworkInterface(
        location=kwargs['location'],
        network_security_group=network_security_group,
        ip_configurations=ip_configurations,
        dns_settings=dns_settings,
    )

    poller = netconn.network_interfaces.create_or_update(
        kwargs['resource_group'], kwargs['iface_name'], iface_params
    )
    poller.wait()
    count = 0
    while True:
        try:
            return show_interface(kwargs=kwargs)
        except CloudError:
            count += 1
            if count > 120:
                raise ValueError('Timed out waiting for operation to complete.')
            time.sleep(5)


def request_instance(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Request that Azure spin up a new instance
    '''
    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    vm_ = kwargs

    if vm_.get('driver') is None:
        vm_['driver'] = 'azurearm'

    if vm_.get('location') is None:
        vm_['location'] = get_location()

    if vm_.get('resource_group') is None:
        vm_['resource_group'] = config.get_cloud_config_value(
            'resource_group', vm_, __opts__, search_global=True
        )

    if vm_.get('name') is None:
        vm_['name'] = config.get_cloud_config_value(
            'name', vm_, __opts__, search_global=True
        )

    vm_['availability_set_id'] = None
    if vm_.get('availability_set'):
        availability_set = compconn.availability_sets.get(
            resource_group_name=vm_['resource_group'],
            availability_set_name=vm_['availability_set'],
        )
        vm_['availability_set_id'] = SubResource(
            id=availability_set.id
        )

    os_kwargs = {}
    userdata = None
    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False, default=None
    )
    if userdata_file is None:
        userdata = config.get_cloud_config_value(
            'userdata', vm_, __opts__, search_global=False, default=None
        )
    else:
        if os.path.exists(userdata_file):
            with salt.utils.files.fopen(userdata_file, 'r') as fh_:
                userdata = fh_.read()

    userdata = salt.utils.cloud.userdata_template(__opts__, vm_, userdata)

    if userdata is not None:
        try:
            os_kwargs['custom_data'] = base64.b64encode(userdata)
        except Exception as exc:
            log.exception('Failed to encode userdata: %s', exc)

    iface_data = create_interface(kwargs=vm_)
    vm_['iface_id'] = iface_data['id']

    disk_name = '{0}-vol0'.format(vm_['name'])

    vm_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, search_global=True,
        default=config.get_cloud_config_value(
            'win_username', vm_, __opts__, search_global=True
        )
    )

    vm_password = config.get_cloud_config_value(
        'ssh_password', vm_, __opts__, search_global=True,
        default=config.get_cloud_config_value(
            'win_password', vm_, __opts__, search_global=True
        )
    )

    if isinstance(kwargs.get('volumes'), six.string_types):
        volumes = salt.utils.yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs.get('volumes')

    data_disks = None
    if isinstance(volumes, list):
        data_disks = []
    else:
        volumes = []

    lun = 0
    luns = []
    for volume in volumes:
        if isinstance(volume, six.string_types):
            volume = {'name': volume}

        # Creating the name of the datadisk if missing in the configuration of the minion
        # If the "name: name_of_my_disk" entry then we create it with the same logic than the os disk
        volume.setdefault(
            'name', volume.get(
                'name', volume.get('name', '{0}-datadisk{1}'.format(
                    vm_['name'],
                    six.text_type(lun),
                    ),
                )
            )
        )

        # Use the size keyword to set a size, but you can use either the new
        # azure name (disk_size_gb) or the old (logical_disk_size_in_gb)
        # instead. If none are set, the disk has size 100GB.
        volume.setdefault(
            'disk_size_gb', volume.get(
                'logical_disk_size_in_gb', volume.get('size', 100)
            )
        )
        # Old kwarg was host_caching, new name is caching
        volume.setdefault('caching', volume.get('host_caching', 'ReadOnly'))
        while lun in luns:
            lun += 1
            if lun > 15:
                log.error('Maximum lun count has been reached')
                break
        volume.setdefault('lun', lun)
        lun += 1
        # The default vhd is {vm_name}-datadisk{lun}.vhd
        if 'media_link' in volume:
            volume['vhd'] = VirtualHardDisk(volume['media_link'])
            del volume['media_link']
        elif 'vhd' in volume:
            volume['vhd'] = VirtualHardDisk(volume['vhd'])
        else:
            volume['vhd'] = VirtualHardDisk(
                'https://{0}.blob.core.windows.net/vhds/{1}-datadisk{2}.vhd'.format(
                    vm_['storage_account'],
                    vm_['name'],
                    volume['lun'],
                ),
            )
        if 'image' in volume:
            volume['create_option'] = DiskCreateOptionTypes.from_image
        elif 'attach' in volume:
            volume['create_option'] = DiskCreateOptionTypes.attach
        else:
            volume['create_option'] = DiskCreateOptionTypes.empty
        data_disks.append(DataDisk(**volume))

    win_installer = config.get_cloud_config_value(
        'win_installer', vm_, __opts__, search_global=True
    )
    if vm_['image'].startswith('http'):
        # https://{storage_account}.blob.core.windows.net/{path}/{vhd}
        source_image = VirtualHardDisk(vm_['image'])
        img_ref = None
        if win_installer:
            os_type = 'Windows'
        else:
            os_type = 'Linux'
    else:
        img_pub, img_off, img_sku, img_ver = vm_['image'].split('|')
        source_image = None
        os_type = None
        img_ref = ImageReference(
            publisher=img_pub,
            offer=img_off,
            sku=img_sku,
            version=img_ver,
        )

    params = VirtualMachine(
        location=vm_['location'],
        plan=None,
        hardware_profile=HardwareProfile(
            vm_size=getattr(
                VirtualMachineSizeTypes, vm_['size'].lower()
            ),
        ),
        storage_profile=StorageProfile(
            os_disk=OSDisk(
                caching=CachingTypes.none,
                create_option=DiskCreateOptionTypes.from_image,
                name=disk_name,
                vhd=VirtualHardDisk(
                    'https://{0}.blob.core.windows.net/vhds/{1}.vhd'.format(
                        vm_['storage_account'],
                        disk_name,
                    ),
                ),
                os_type=os_type,
                image=source_image,
                disk_size_gb=vm_.get('os_disk_size_gb', 30)
            ),
            data_disks=data_disks,
            image_reference=img_ref,
        ),
        os_profile=OSProfile(
            admin_username=vm_username,
            admin_password=vm_password,
            computer_name=vm_['name'],
            **os_kwargs
        ),
        network_profile=NetworkProfile(
            network_interfaces=[
                NetworkInterfaceReference(vm_['iface_id']),
            ],
        ),
        availability_set=vm_['availability_set_id'],
    )

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('requesting', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    poller = compconn.virtual_machines.create_or_update(
        vm_['resource_group'], vm_['name'], params
    )
    try:
        poller.wait()
    except CloudError as exc:
        log.warning('There was a cloud error: %s', exc)
        log.warning('This may or may not indicate an actual problem')

    try:
        return show_instance(vm_['name'], call='action')
    except CloudError:
        return {}


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'azure',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    log.info('Creating Cloud VM %s', vm_['name'])

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    def _query_ip_address():
        data = request_instance(kwargs=vm_)
        ifaces = data['network_profile']['network_interfaces']
        iface = list(ifaces)[0]
        ip_name = list(ifaces[iface]['ip_configurations'])[0]

        if vm_.get('public_ip') is True:
            hostname = ifaces[iface]['ip_configurations'][ip_name]['public_ip_address']
        else:
            hostname = ifaces[iface]['ip_configurations'][ip_name]['private_ip_address']

        if isinstance(hostname, dict):
            hostname = hostname.get('ip_address')

        if not isinstance(hostname, six.string_types):
            return None
        return hostname

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_ip_address,
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=10),
            interval_multiplier=config.get_cloud_config_value(
                'wait_for_ip_interval_multiplier', vm_, __opts__, default=1),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure, SaltCloudSystemExit) as exc:
        try:
            log.warning(exc)
        finally:
            raise SaltCloudSystemExit(six.text_type(exc))

    # calling _query_ip_address() causes Salt to attempt to build the VM again.
    #hostname = _query_ip_address()
    hostname = data

    if not hostname or not isinstance(hostname, six.string_types):
        log.error('Failed to get a value for the hostname.')
        return False

    vm_['ssh_host'] = hostname
    if not vm_.get('ssh_username'):
        vm_['ssh_username'] = config.get_cloud_config_value(
            'ssh_username', vm_, __opts__
        )
    vm_['password'] = config.get_cloud_config_value(
        'ssh_password', vm_, __opts__
    )
    ret = __utils__['cloud.bootstrap'](vm_, __opts__)

    data = show_instance(vm_['name'], call='action')
    log.info('Created Cloud VM \'%s\'', vm_['name'])
    log.debug(
        '\'%s\' VM creation details:\n%s',
        vm_['name'], pprint.pformat(data)
    )

    ret.update(data)

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def destroy(name, conn=None, call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Destroy a VM

    CLI Examples:

    .. code-block:: bash

        salt-cloud -d myminion
        salt-cloud -a destroy myminion service_name=myservice
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    if kwargs is None:
        kwargs = {}

    node_data = show_instance(name, call='action')
    vhd = node_data['storage_profile']['os_disk']['vhd']['uri']

    ret = {name: {}}
    log.debug('Deleting VM')
    result = compconn.virtual_machines.delete(node_data['resource_group'], name)
    result.wait()

    if __opts__.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)

    cleanup_disks = config.get_cloud_config_value(
        'cleanup_disks',
        get_configured_provider(), __opts__, search_global=False, default=False,
    )
    if cleanup_disks:
        cleanup_vhds = kwargs.get('delete_vhd', config.get_cloud_config_value(
            'cleanup_vhds',
            get_configured_provider(), __opts__, search_global=False, default=False,
        ))
        if cleanup_vhds:
            log.debug('Deleting vhd')

            comps = vhd.split('/')
            container = comps[-2]
            blob = comps[-1]

            ret[name]['delete_disk'] = {
                'delete_disks': cleanup_disks,
                'delete_vhd': cleanup_vhds,
                'container': container,
                'blob': blob,
            }
            ret[name]['data'] = delete_blob(
                kwargs={'container': container, 'blob': blob},
                call='function'
            )

        cleanup_data_disks = kwargs.get('delete_data_disks', config.get_cloud_config_value(
            'cleanup_data_disks',
            get_configured_provider(), __opts__, search_global=False, default=False,
        ))
        if cleanup_data_disks:
            log.debug('Deleting data_disks')
            ret[name]['data_disks'] = {}

            for disk in node_data['storage_profile']['data_disks']:
                datavhd = disk.vhd.uri
                comps = datavhd.split('/')
                container = comps[-2]
                blob = comps[-1]

                ret[name]['data_disks'][disk.name] = {
                    'delete_disks': cleanup_disks,
                    'delete_vhd': cleanup_vhds,
                    'container': container,
                    'blob': blob,
                }
                ret[name]['data'] = delete_blob(
                    kwargs={'container': container, 'blob': blob},
                    call='function'
                )

    cleanup_interfaces = config.get_cloud_config_value(
        'cleanup_interfaces',
        get_configured_provider(), __opts__, search_global=False, default=False,
    )
    if cleanup_interfaces:
        ret[name]['cleanup_network'] = {
            'cleanup_interfaces': cleanup_interfaces,
            'resource_group': cleanup_interfaces,
            'iface_name': cleanup_interfaces,
            'data': [],
        }
        ifaces = node_data['network_profile']['network_interfaces']
        for iface in ifaces:
            ret[name]['cleanup_network']['data'].append(
                delete_interface(
                    kwargs={
                        'resource_group': ifaces[iface]['resource_group'],
                        'iface_name': iface,
                    },
                    call='function',
                )
            )

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def make_safe(data):
    '''
    Turn object data into something serializable
    '''
    return salt.utils.data.simple_types_filter(object_to_dict(data))


def create_security_group(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a security group
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('location') is None:
        kwargs['location'] = get_location()

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    if kwargs.get('name') is None:
        kwargs['name'] = config.get_cloud_config_value(
            'name', {}, __opts__, search_global=True
        )

    group_params = NetworkSecurityGroup(
        location=kwargs['location'],
    )

    netconn.network_security_group.create_or_update(  # pylint: disable=no-member
        rource_group_name=kwargs['resource_group'],
        network_security_group_name=kwargs['name'],
        parameters=group_params,
    )
    count = 0
    while True:
        try:
            return show_security_group(kwargs=kwargs)
        except CloudError:
            count += 1
            if count > 120:
                raise ValueError('Timed out waiting for operation to complete.')
            time.sleep(5)


def show_security_group(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network security_group
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    group = netconn.network_security_groups.get(
        resource_group_name=kwargs['resource_group'],
        network_security_group_name=kwargs['security_group'],
    )
    group_dict = make_safe(group)
    def_rules = {}
    for rule in group.default_security_rules:  # pylint: disable=no-member
        def_rules[rule.name] = make_safe(rule)
    group_dict['default_security_rules'] = def_rules
    sec_rules = {}
    for rule in group.security_rules:  # pylint: disable=no-member
        sec_rules[rule.name] = make_safe(rule)
    group_dict['security_rules'] = sec_rules
    return group_dict


def list_security_groups(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network security_group
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}'.format(region)
    security_groups = cache.cache(
        bank,
        'network_security_groups',
        netconn.network_security_groups.list,
        loop_fun=make_safe,
        expire=config.get_cloud_config_value(
            'expire_security_group_cache', get_configured_provider(),
            __opts__, search_global=False, default=86400,
        ),
        resource_group_name=kwargs['resource_group']
    )
    ret = {}
    for group in security_groups:
        ret[group['name']] = group
    return ret


def create_security_rule(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a security rule (aka, firewall rule)
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    if kwargs.get('security_group') is None:
        kwargs['security_group'] = config.get_cloud_config_value(
            'security_group', {}, __opts__, search_global=True
        )

    if kwargs.get('name') is None:
        kwargs['name'] = config.get_cloud_config_value(
            'name', {}, __opts__, default='default', search_global=True
        )

    rule_params = SecurityRule(
        protocol=kwargs['protocol'],  # Can be 'Tcp', 'Udp', or '*'
        source_address_prefix=kwargs['source_address'],  # '*', 'VirtualNetwork', 'AzureLoadBalancer', 'Internet', '0.0.0.0/24', etc pylint: disable=line-too-long
        source_port_range=kwargs['source_ports'],  # '*', int, or range (0-65535)
        destination_address_prefix=kwargs['destination_address'],  # '*', 'VirtualNetwork', 'AzureLoadBalancer', 'Internet', '0.0.0.0/24', etc pylint: disable=line-too-long
        destination_port_range=kwargs['destination_ports'],  # '*', int, or range (0-65535)
        access=kwargs['access'],  # 'Allow' or 'Deny'
        direction=kwargs['direction'],  # 'Inbound' or 'Outbound'
        priority=kwargs['priority'],  # Unique number between and 100-4096
    )

    netconn.security_rules.create_or_update(
        resource_group_name=kwargs['resource_group'],
        network_security_group_name=kwargs['security_group'],
        security_rule_name=kwargs['name'],
        security_rule_parameters=rule_params,
    )
    count = 0
    while True:
        try:
            return show_security_rule(kwargs=kwargs)
        except CloudError:
            count += 1
            if count > 120:
                raise ValueError('Timed out waiting for operation to complete.')
            time.sleep(5)


def show_security_rule(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network security_rule
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    rule = netconn.security_rules.get(
        resource_group_name=kwargs['resource_group'],
        network_security_group_name=kwargs['security_group'],
        security_rule_name=kwargs['name'],
    )
    return make_safe(rule)


def list_security_rules(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Lits network security rules
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    if kwargs.get('security_group') is None:
        kwargs['security_group'] = config.get_cloud_config_value(
            'security_group', {}, __opts__, search_global=True
        )

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}'.format(region)
    security_rules = cache.cache(
        bank,
        'security_rules',
        netconn.security_rules.list,
        loop_fun=make_safe,
        expire=config.get_cloud_config_value(
            'expire_security_rule_cache', get_configured_provider(),
            __opts__, search_global=False, default=86400,
        ),
        resource_group_name=kwargs['resource_group'],
        network_security_group_name=kwargs['security_group'],
    )
    ret = {}
    for group in security_rules:
        ret[group['name']] = group
    return ret


def pages_to_list(items):
    '''
    Convert a set of links from a group of pages to a list
    '''
    objs = []
    while True:
        try:
            page = items.next()  # pylint: disable=incompatible-py3-code
            if isinstance(page, collections.Iterable):
                for item in page:
                    objs.append(item)
            else:
                objs.append(page)
        except GeneratorExit:
            break
        except StopIteration:
            break
    return objs


def list_storage_accounts(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List storage accounts
    '''
    global storconn  # pylint: disable=global-statement,invalid-name
    if not storconn:
        storconn = get_conn(StorageManagementClient)

    if kwargs is None:
        kwargs = {}

    ret = {}
    for acct in pages_to_list(storconn.storage_accounts.list()):
        ret[acct.name] = object_to_dict(acct)

    return ret


def list_containers(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List containers
    '''
    global storconn  # pylint: disable=global-statement,invalid-name
    if not storconn:
        storconn = get_conn(StorageManagementClient)

    storageaccount = CloudStorageAccount(
        config.get_cloud_config_value(
            'storage_account',
            get_configured_provider(), __opts__, search_global=False
        ),
        config.get_cloud_config_value(
            'storage_key',
            get_configured_provider(), __opts__, search_global=False
        ),
    )
    storageservice = storageaccount.create_block_blob_service()

    if kwargs is None:
        kwargs = {}

    ret = {}
    for cont in storageservice.list_containers().items:
        ret[cont.name] = object_to_dict(cont)

    return ret


list_storage_containers = list_containers


def list_blobs(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List blobs
    '''
    global storconn  # pylint: disable=global-statement,invalid-name
    if not storconn:
        storconn = get_conn(StorageManagementClient)

    if kwargs is None:
        kwargs = {}

    if 'container' not in kwargs:
        raise SaltCloudSystemExit(
            'A container must be specified'
        )

    storageaccount = CloudStorageAccount(
        config.get_cloud_config_value(
            'storage_account',
            get_configured_provider(), __opts__, search_global=False
        ),
        config.get_cloud_config_value(
            'storage_key',
            get_configured_provider(), __opts__, search_global=False
        ),
    )
    storageservice = storageaccount.create_block_blob_service()

    ret = {}
    for blob in storageservice.list_blobs(kwargs['container']).items:
        ret[blob.name] = object_to_dict(blob)

    return ret


def delete_blob(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Delete a blob from a container
    '''
    global storconn  # pylint: disable=global-statement,invalid-name
    if not storconn:
        storconn = get_conn(StorageManagementClient)

    if kwargs is None:
        kwargs = {}

    if 'container' not in kwargs:
        raise SaltCloudSystemExit(
            'A container must be specified'
        )

    if 'blob' not in kwargs:
        raise SaltCloudSystemExit(
            'A blob must be specified'
        )

    storageaccount = CloudStorageAccount(
        config.get_cloud_config_value(
            'storage_account',
            get_configured_provider(), __opts__, search_global=False
        ),
        config.get_cloud_config_value(
            'storage_key',
            get_configured_provider(), __opts__, search_global=False
        ),
    )
    storageservice = storageaccount.create_block_blob_service()

    storageservice.delete_blob(kwargs['container'], kwargs['blob'])
    return True
