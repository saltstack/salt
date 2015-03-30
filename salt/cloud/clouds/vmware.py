# -*- coding: utf-8 -*-
'''
VMware Cloud Module
===================

.. versionadded:: Beryllium

The VMware cloud module allows you to manage VMware ESX, ESXi, and vCenter.

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
:depends: pyVmomi Python module

.. note::
    Ensure python pyVmomi module is installed by running following one-liner
    check. The output should be 0.

    .. code-block:: bash

       python -c "import pyVmomi" ; echo $?

To use this module, set up the vCenter Host URL, username and password in the
cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      provider: vmware
      user: myuser
      password: verybadpass
      host: 'vcenter01.domain.com'

    vmware-vcenter02:
      provider: vmware
      user: myuser
      password: verybadpass
      host: 'vcenter02.domain.com'

    vmware-vcenter03:
      provider: vmware
      user: myuser
      password: verybadpass
      host: 'vcenter03.domain.com'
'''
from __future__ import absolute_import

# Import python libs
import pprint
import logging
import time

# Import salt libs
import salt.utils.cloud
import salt.utils.xmlutil
from salt.exceptions import SaltCloudSystemExit

# Import salt cloud libs
import salt.config as config

# Attempt to import pyVim and pyVmomi libs
HAS_LIBS = False
try:
    from pyVim.connect import SmartConnect
    from pyVmomi import vim, vmodl
    HAS_LIBS = True
except Exception:
    pass

# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the VMware configurations are in place
def __virtual__():
    '''
    Check for VMware configuration and if required libs are available.
    '''
    if not HAS_LIBS:
        return False

    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'vmware',
        ('host', 'user', 'password',)
    )


def _get_si():
    '''
    Authenticate with vCenter server and return service instance object.
    '''
    try:
        si = SmartConnect(
                 host = config.get_cloud_config_value(
                            'host', get_configured_provider(), __opts__, search_global=False
                        ),
                 user = config.get_cloud_config_value(
                            'user', get_configured_provider(), __opts__, search_global=False
                        ),
                 pwd = config.get_cloud_config_value(
                           'password', get_configured_provider(), __opts__, search_global=False
                       ),
             )
    except:
        raise SaltCloudSystemExit(
            '\nCould not connect to the host using the specified username and password'
        )

    return si


def _get_inv():
    '''
    Return the inventory.
    '''
    si = _get_si()
    return si.RetrieveContent()


def _get_object_property_list(obj_type, property_list=None):
    '''
    Returns a list of properties for the managed object in the VMware environment
    '''
    # Get service instance object
    si = _get_si()

    # Refer to http://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch5_PropertyCollector.7.6.html for more information.

    content = si.content

    # Create a object view
    obj_view = content.viewManager.CreateContainerView(content.rootFolder, [obj_type], True)

    # Create object spec to navigate content
    obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
    obj_spec.obj = obj_view
    obj_spec.skip = True

    # Create property spec to determine properties to be retrieved
    property_spec = vmodl.query.PropertyCollector.PropertySpec()
    property_spec.type = obj_type
    if not property_list:
        property_spec.all = True
    else:
        property_spec.pathSet = property_list

    # Create a filter spec and specify object, property spec in it
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = [obj_spec]
    filter_spec.propSet = [property_spec]

    # Create traversal spec to determine the path for collection
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec()
    traversal_spec.name = 'traverseEntities'
    traversal_spec.path = 'view'
    traversal_spec.skip = False
    traversal_spec.type = obj_view.__class__
    obj_spec.selectSet = [traversal_spec]

    # Retrieve the content
    content = content.propertyCollector.RetrieveContents([filter_spec])

    # Destroy the object view
    obj_view.Destroy()

    obj_list = []
    for object in content:
        properties = {}
        for property in object.propSet:
            properties[property.name] = property.val
            properties['object'] = object.obj
        obj_list.append(properties)

    return obj_list


def get_vcenter_version(kwargs=None, call=None):
    '''
    Show the vCenter Server version with build number.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_vcenter_version my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_vcenter_version function must be called with -f or --function.'
        )

    # Get the inventory
    inv = _get_inv()

    return inv.about.fullName


def list_datacenters(kwargs=None, call=None):
    '''
    List all the data centers for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_datacenters my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_datacenters function must be called with -f or --function.'
        )
        return False

    datacenters = []
    datacenter_properties = [
                                "name"
                            ]

    datacenter_list = _get_object_property_list(vim.Datacenter, datacenter_properties)

    for datacenter in datacenter_list:
        datacenters.append(datacenter["name"])

    return {'Datacenters': datacenters}


def list_clusters(kwargs=None, call=None):
    '''
    List all the clusters for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_clusters my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_clusters function must be called with -f or --function.'
        )
        return False

    clusters = []
    cluster_properties = [
                             "name"
                         ]

    cluster_list = _get_object_property_list(vim.ClusterComputeResource, cluster_properties)

    for cluster in cluster_list:
        clusters.append(cluster["name"])

    return {'Clusters': clusters}


def list_datastore_clusters(kwargs=None, call=None):
    '''
    List all the datastore clusters for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_datastore_clusters my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_datastore_clusters function must be called with -f or --function.'
        )
        return False

    datastore_clusters = []
    datastore_cluster_properties = [
                                       "name"
                                   ]

    datastore_cluster_list = _get_object_property_list(vim.StoragePod, datastore_cluster_properties)

    for datastore_cluster in datastore_cluster_list:
        datastore_clusters.append(datastore_cluster["name"])

    return {'Datastore Clusters': datastore_clusters}


def list_datastores(kwargs=None, call=None):
    '''
    List all the datastores for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_datastores my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_datastores function must be called with -f or --function.'
        )
        return False

    datastores = []
    datastore_properties = [
                               "name"
                           ]

    datastore_list = _get_object_property_list(vim.Datastore, datastore_properties)

    for datastore in datastore_list:
        datastores.append(datastore["name"])

    return {'Datastores': datastores}


def list_hosts(kwargs=None, call=None):
    '''
    List all the hosts for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_hosts function must be called with -f or --function.'
        )
        return False

    hosts = []
    host_properties = [
                          "name"
                      ]

    host_list = _get_object_property_list(vim.HostSystem, host_properties)

    for host in host_list:
        hosts.append(host["name"])

    return {'Hosts': hosts}


def list_resourcepools(kwargs=None, call=None):
    '''
    List all the resource pools for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_resourcepools my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_resourcepools function must be called with -f or --function.'
        )
        return False

    resource_pools = []
    resource_pool_properties = [
                                   "name"
                               ]

    resource_pool_list = _get_object_property_list(vim.ResourcePool, resource_pool_properties)

    for resource_pool in resource_pool_list:
        resource_pools.append(resource_pool["name"])

    return {'Resource Pools': resource_pools}


def list_networks(kwargs=None, call=None):
    '''
    List all the standard networks for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_networks my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_networks function must be called with -f or --function.'
        )
        return False

    networks = []
    network_properties = [
                             "name"
                         ]

    network_list = _get_object_property_list(vim.Network, network_properties)

    for network in network_list:
        networks.append(network["name"])

    return {'Networks': networks}


def list_nodes_min(kwargs=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with no details

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-vmware-config
    '''

    ret = {}
    vm_properties = [
                        "name"
                    ]

    vm_list = _get_object_property_list(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        ret[vm["name"]] = True

    return ret


def list_nodes(kwargs=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with basic fields

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes my-vmware-config
    '''

    ret = {}
    vm_properties = [
                        "name",
                        "guest.ipAddress",
                        "config.guestFullName",
                        "config.hardware.numCPU",
                        "config.hardware.memoryMB"
                    ]

    vm_list = _get_object_property_list(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        vm_info = {
            'id': vm["name"],
            'ip_address': vm["guest.ipAddress"] if "guest.ipAddress" in vm else None,
            'guest_fullname': vm["config.guestFullName"],
            'cpus': vm["config.hardware.numCPU"],
            'ram': vm["config.hardware.memoryMB"],
        }
        ret[vm_info['id']] = vm_info

    return ret


def list_folders(kwargs=None, call=None):
    '''
    List all the folders for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_folders my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_folders function must be called with -f or --function.'
        )
        return False

    folders = []
    folder_properties = [
                            "name"
                        ]

    folder_list = _get_object_property_list(vim.Folder, folder_properties)

    for folder in folder_list:
        folders.append(folder["name"])

    return {'Folders': folders}


def start(name, call=None):
    '''
    To start/power on a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    vm_properties = [
                        "name",
                        "summary.runtime.powerState"
                    ]

    vm_list = _get_object_property_list(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["name"] == name:
            if vm["summary.runtime.powerState"] == "poweredOn":
                ret = 'already powered on'
                log.info('VM {0} {1}'.format(name, ret))
                return ret
            try:
                log.info('Starting VM {0}'.format(name))
                vm["object"].PowerOn()
            except Exception as exc:
                log.error('Could not power on VM {0}: {1}'.format(name, exc))
                return 'failed to power on'
    return 'powered on'


def stop(name, call=None):
    '''
    To stop/power off a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    vm_properties = [
                        "name",
                        "summary.runtime.powerState"
                    ]

    vm_list = _get_object_property_list(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["name"] == name:
            if vm["summary.runtime.powerState"] == "poweredOff":
                ret = 'already powered off'
                log.info('VM {0} {1}'.format(name, ret))
                return ret
            try:
                log.info('Stopping VM {0}'.format(name))
                vm["object"].PowerOff()
            except Exception as exc:
                log.error('Could not power off VM {0}: {1}'.format(name, exc))
                return 'failed to power off'
    return 'powered off'
