# -*- coding: utf-8 -*-
'''
Azure Cloud Module
==================

.. versionadded:: Carbon

The Azure cloud module is used to control access to Microsoft Azure

:depends:
    * `Microsoft Azure SDK for Python <https://pypi.python.org/pypi/azure>`_ == 2.0rc2
    * `Microsoft Azure Storage SDK for Python <https://pypi.python.org/pypi/azure-storage>`_
:configuration:
    Required provider parameters:

    * ``subscription_id``
    * ``username``
    * ``password``

Example ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/azure.conf`` configuration:

.. code-block:: yaml

    my-azure-config:
      driver: azure
      subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
      username: larry
      password: 123pass
'''
# pylint: disable=E0102

# pylint: disable=wrong-import-position,wrong-import-order
from __future__ import absolute_import
import os
import os.path
import time
import logging
import pprint
import base64
import salt.cache
import salt.config as config
import salt.utils.cloud
from salt.exceptions import SaltCloudSystemExit

# Import 3rd-party libs
HAS_LIBS = False
try:
    import salt.utils.msazure
    from salt.utils.msazure import object_to_dict
    import azure.storage
    from azure.common.credentials import UserPassCredentials
    from azure.mgmt.compute import (
        ComputeManagementClient,
        ComputeManagementClientConfiguration,
    )
    from azure.mgmt.compute.models import (
        CachingTypes,
        DiskCreateOptionTypes,
        HardwareProfile,
        ImageReference,
        NetworkInterfaceReference,
        NetworkProfile,
        OSDisk,
        OSProfile,
        StorageProfile,
        VirtualHardDisk,
        VirtualMachine,
        VirtualMachineSizeTypes,
    )
    from azure.mgmt.network import (
        NetworkManagementClient,
        NetworkManagementClientConfiguration,
    )
    from azure.mgmt.network.models import (
        IPAllocationMethod,
        NetworkInterface,
        NetworkInterfaceIPConfiguration,
        NetworkSecurityGroup,
        PublicIPAddress,
        Resource,
        SecurityRule,
    )
    from azure.mgmt.resource.resources import (
        ResourceManagementClient,
        ResourceManagementClientConfiguration,
    )
    from azure.mgmt.storage import (
        StorageManagementClient,
        StorageManagementClientConfiguration,
    )
    from azure.mgmt.web import (
        WebSiteManagementClient,
        WebSiteManagementClientConfiguration,
    )
    from msrestazure.azure_exceptions import CloudError
    HAS_LIBS = True
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
        return False

    global cache  # pylint: disable=global-statement,invalid-name
    cache = salt.cache.Cache(__opts__)

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('subscription_id', 'username', 'password')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'azurearm': HAS_LIBS}
    )


def get_conn(Client=None, ClientConfig=None):
    '''
    Return a conn object for the passed VM data
    '''
    if Client is None:
        Client = ComputeManagementClient
    if ClientConfig is None:
        ClientConfig = ComputeManagementClientConfiguration

    subscription_id = config.get_cloud_config_value(
        'subscription_id',
        get_configured_provider(), __opts__, search_global=False
    )

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
        ClientConfig(
            credentials,
            subscription_id=subscription_id,
        )
    )
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
        webconn = get_conn(
            WebSiteManagementClient, WebSiteManagementClientConfiguration
        )

    ret = {}
    regions = webconn.global_model.get_subscription_geo_regions()
    for location in regions.value:  # pylint: disable=no-member
        lowername = str(location.name).lower().replace(' ', '')
        ret[lowername] = object_to_dict(location)
    return ret


def _cache(bank, key, fun, **kwargs):
    '''
    Cache an Azure ARM object
    '''
    items = cache.fetch(bank, key)
    if items is None:
        items = {}
        try:
            item_list = fun(**kwargs)
        except CloudError as exc:
            log.warn('There was a cloud error calling {0} with kwargs {1}: {2}'.format(fun, kwargs, exc))
        for item in item_list:
            items[item.name] = object_to_dict(item)
        cache.store(bank, key, items)
    return items


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
    publishers = _cache(
        bank,
        'publishers',
        compconn.virtual_machine_images.list_publishers,
        location=region,
    )

    ret = {}
    for publisher in publishers:
        pub_bank = os.path.join(bank, 'publishers', publisher)
        offers = _cache(
            pub_bank,
            'offers',
            compconn.virtual_machine_images.list_offers,
            location=region,
            publisher_name=publishers[publisher]['name'],
        )

        for offer in offers:
            offer_bank = os.path.join(pub_bank, 'offers', offer)
            skus = _cache(
                offer_bank,
                'skus',
                compconn.virtual_machine_images.list_skus,
                location=region,
                publisher_name=publishers[publisher]['name'],
                offer=offers[offer]['name'],
            )

            for sku in skus:
                sku_bank = os.path.join(offer_bank, 'skus', sku)
                results = _cache(
                    sku_bank,
                    'results',
                    compconn.virtual_machine_images.list,
                    location=region,
                    publisher_name=publishers[publisher]['name'],
                    offer=offers[offer]['name'],
                    skus=skus[sku]['name'],
                )

                for version in results:
                    name = '|'.join((
                        publishers[publisher]['name'],
                        offers[offer]['name'],
                        skus[sku]['name'],
                        results[version]['name'],
                    ))
                    ret[name] = {
                        'publisher': publishers[publisher]['name'],
                        'offer': offers[offer]['name'],
                        'sku': skus[sku]['name'],
                        'version': results[version]['name'],
                    }
    return ret


def _pages_to_list(items):
    '''
    Convert a set of links from a group of pages to a list
    '''
    objs = []
    while True:
        try:
            page = items.next()
            for item in page:
                objs.append(item)
        except GeneratorExit:
            break
    return objs


def _pages_to_list_old(items):
    '''
    Convert a set of links from a group of pages to a list
    '''
    objs = []
    while True:
        try:
            page = items.next()
            for item in page:
                objs.append(item)
        except GeneratorExit:
            break
    return objs


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
    sizeobjs = _pages_to_list(sizes)
    for size in sizeobjs:
        ret[size.name] = object_to_dict(size)
    return ret


def list_nodes(conn=None, call=None):  # pylint: disable=unused-argument
    '''
    List VMs on this Azure account
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
    for node in nodes:
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
        nodeobjs = _pages_to_list(nodes)
        for node in nodeobjs:
            ret[node.name] = object_to_dict(node)
            ret[node.name]['id'] = node.id
            ret[node.name]['name'] = node.name
            ret[node.name]['size'] = node.hardware_profile.vm_size
            ret[node.name]['state'] = node.provisioning_state
            ret[node.name]['private_ips'] = node.network_profile.network_interfaces
            ret[node.name]['public_ips'] = node.network_profile.network_interfaces
            try:
                ret[node.name]['image'] = '|'.join((
                    ret[node.name]['storage_profile']['image_reference']['publisher'],
                    ret[node.name]['storage_profile']['image_reference']['offer'],
                    ret[node.name]['storage_profile']['image_reference']['sku'],
                    ret[node.name]['storage_profile']['image_reference']['version'],
                ))
            except TypeError:
                ret[node.name]['image'] = ret[node.name]['storage_profile']['os_disk']['image']['uri']
    return ret


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
        resconn = get_conn(
            ResourceManagementClient, ResourceManagementClientConfiguration
        )

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
            __opts__, search_global=False, default=86400,
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

    salt.utils.cloud.cache_node(
        salt.utils.cloud.simple_types_filter(data),
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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
                    __opts__, search_global=False, default=86400,
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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

    if 'group' not in kwargs:
        raise SaltCloudSystemExit(
            'A resource_group must be specified as "group"'
        )

    if 'network' not in kwargs:
        raise SaltCloudSystemExit(
            'A "network" must be specified using'
        )

    region = get_location()
    bank = 'cloud/metadata/azurearm/{0}/{1}'.format(region, kwargs['network'])

    ret = {}
    try:
        subnets = cache.cache(
            bank,
            'subnets',
            netconn.subnets.list,
            loop_fun=make_safe,
            expire=config.get_cloud_config_value(
                'expire_subnet_cache', get_configured_provider(),
                __opts__, search_global=False, default=86400,
            ),
            resource_group_name=kwargs['group'],
            virtual_network_name=kwargs['network'],
        )
    except CloudError:
        return ret
    for subnet in subnets:
        ret[subnet['name']] = subnet
        subnet['resource_group'] = kwargs['group']
        #subnet['ip_configurations'] = list_ip_configurations(kwargs=subnet)
    return ret


def delete_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    return netconn.network_interfaces.delete(
        kwargs['resource_group'],
        kwargs['iface_name'],
    )


def show_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
        )

    iface = netconn.network_interfaces.get(
        kwargs['resource_group'],
        kwargs.get('iface_name', kwargs.get('name'))
    )
    data = object_to_dict(iface)
    data['resource_group'] = kwargs['resource_group']
    data['ip_configurations'] = list_ip_configurations(kwargs=data)
    return data


def list_ip_configurations(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List IP configurations
    '''
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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

    if kwargs is None:
        kwargs = {}

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', {}, __opts__, search_global=True
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
            __opts__, search_global=False, default=86400,
        ),
        resource_group_name=kwargs['resource_group']
    )
    return interfaces


def create_interface(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a network interface
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

    if kwargs is None:
        kwargs = {}
    vm_ = kwargs

    if kwargs.get('location') is None:
        kwargs['location'] = get_location()

    if kwargs.get('resource_group') is None:
        kwargs['resource_group'] = config.get_cloud_config_value(
            'resource_group', vm_, __opts__, search_global=True
        )

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

    if 'network_resource_group' in kwargs:
        group = kwargs['network_resource_group']
    else:
        group = kwargs['resource_group']

    subnet_obj = netconn.subnets.get(
        resource_group_name=kwargs['resource_group'],
        virtual_network_name=kwargs['network'],
        subnet_name=kwargs['subnet'],
    )

    ip_kwargs = {}
    if bool(kwargs.get('public_ip', False)) is True:
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
                    ip_kwargs['public_ip_address'] = Resource(
                        str(pub_ip_data.id),  # pylint: disable=no-member
                    )
                    break
            except CloudError:
                pass
            count += 1
            if count > 120:
                raise ValueError('Timed out waiting for public IP Address.')
            time.sleep(5)

    iface_params = NetworkInterface(
        name=kwargs['iface_name'],
        location=kwargs['location'],
        ip_configurations=[
            NetworkInterfaceIPConfiguration(
                name='{0}-ip'.format(kwargs['iface_name']),
                private_ip_allocation_method='Dynamic',
                subnet=subnet_obj,
                **ip_kwargs
            )
        ]
    )

    netconn.network_interfaces.create_or_update(
        kwargs['resource_group'], kwargs['iface_name'], iface_params
    )
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
            with salt.utils.fopen(userdata_file, 'r') as fh_:
                userdata = fh_.read()

    if userdata is not None:
        os_kwargs['custom_data'] = base64.b64encode(userdata)

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

    win_installer = config.get_cloud_config_value(
        'win_installer', vm_, __opts__, search_global=True
    )
    if vm_['image'].startswith('http'):
        # https://{storage_account}.blob.core.windows.net/{path}/{vhd}
        source_image = VirtualHardDisk(uri=vm_['image'])
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
        name=vm_['name'],
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
                    uri='https://{0}.blob.core.windows.net/vhds/{1}.vhd'.format(
                        vm_['storage_account'],
                        disk_name,
                    ),
                ),
                os_type=os_type,
                image=source_image,
            ),
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
    )

    poller = compconn.virtual_machines.create_or_update(
        vm_['resource_group'], vm_['name'], params
    )
    poller.wait()

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

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )
    log.info('Creating Cloud VM {0}'.format(vm_['name']))

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    data = request_instance(kwargs=vm_)
    #resource_group = data.get('resource_group')

    ifaces = data['network_profile']['network_interfaces']
    iface = ifaces.keys()[0]
    ip_name = ifaces[iface]['ip_configurations'].keys()[0]

    if vm_.get('public_ip') is True:
        hostname = ifaces[iface]['ip_configurations'][ip_name]['public_ip_address']
    else:
        hostname = ifaces[iface]['ip_configurations'][ip_name]['private_ip_address']

    if not hostname:
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
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    data = show_instance(vm_['name'], call='action')
    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    ret.update(data)

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
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

    global compconn  # pylint: disable=global-statement,invalid-name
    if not compconn:
        compconn = get_conn()

    if kwargs is None:
        kwargs = {}

    node_data = show_instance(name, call='action')
    vhd = node_data['storage_profile']['os_disk']['vhd']['uri']

    ret = {}
    log.debug('Deleting VM')
    result = compconn.virtual_machines.delete(node_data['resource_group'], name)
    result.wait()

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

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

        comps = vhd.split('.')
        container = comps[0].replace('https://', '')
        blob = node_data['storage_profile']['os_disk']['name']

        ret[name]['delete_disk'] = {
            'delete_vhd': cleanup_vhds,
            'container': container,
            'blob': blob,
        }
        #data = delete_disk(kwargs={'name': disk_name, 'delete_vhd': cleanup_vhds}, call='function')

    return ret


def make_safe(data):
    '''
    Turn object data into something serializable
    '''
    return salt.utils.cloud.simple_types_filter(object_to_dict(data))


def create_security_group(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    Create a security group
    '''
    global netconn  # pylint: disable=global-statement,invalid-name
    if not netconn:
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
        netconn = get_conn(NetworkManagementClient,
                           NetworkManagementClientConfiguration)

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
            page = items.next()
            for item in page:
                objs.append(item)
        except GeneratorExit:
            break
    return objs


def list_storage_accounts(call=None, kwargs=None):  # pylint: disable=unused-argument
    '''
    List storage accounts
    '''
    global storconn  # pylint: disable=global-statement,invalid-name
    if not storconn:
        storconn = get_conn(StorageManagementClient,
                            StorageManagementClientConfiguration)

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
        storconn = get_conn(StorageManagementClient,
                            StorageManagementClientConfiguration)

    storageaccount = azure.storage.CloudStorageAccount(
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
