# -*- coding: utf-8 -*-
'''
VMware Cloud Module
===================

.. versionadded:: Beryllium

The VMware cloud module allows you to manage VMware ESX, ESXi, and vCenter.

See :doc:`Getting started with VMware </topics/cloud/vmware>` to get started.

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>
:depends: pyVmomi Python module

.. note::
    Ensure python pyVmomi module is installed by running following one-liner
    check. The output should be 0.

    .. code-block:: bash

       python -c "import pyVmomi" ; echo $?

To use this module, set up the vCenter URL, username and password in the
cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      provider: vmware
      user: DOMAIN\\user
      password: verybadpass
      url: vcenter01.domain.com

    vmware-vcenter02:
      provider: vmware
      user: DOMAIN\\user
      password: verybadpass
      url: vcenter02.domain.com

    vmware-vcenter03:
      provider: vmware
      user: DOMAIN\\user
      password: verybadpass
      url: vcenter03.domain.com
'''

# Import python libs
from __future__ import absolute_import
from random import randint
from re import match
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
        ('url', 'user', 'password',)
    )


def script(vm_):
    '''
    Return the script deployment object
    '''
    script_name = config.get_cloud_config_value('script', vm_, __opts__)
    if not script_name:
        script_name = 'bootstrap-salt'

    return salt.utils.cloud.os_script(
        script_name,
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def _get_si():
    '''
    Authenticate with vCenter server and return service instance object.
    '''
    try:
        si = SmartConnect(
                 host=config.get_cloud_config_value(
                          'url', get_configured_provider(), __opts__, search_global=False
                      ),
                 user=config.get_cloud_config_value(
                          'user', get_configured_provider(), __opts__, search_global=False
                      ),
                 pwd=config.get_cloud_config_value(
                         'password', get_configured_provider(), __opts__, search_global=False
                     ),
             )
    except:
        raise SaltCloudSystemExit(
            '\nCould not connect to the vCenter server using the specified username and password'
        )

    return si


def _get_inv():
    '''
    Return the inventory.
    '''
    si = _get_si()
    return si.RetrieveContent()


def _get_content(obj_type, property_list=None):
    # Get service instance object
    si = _get_si()

    # Refer to http://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch5_PropertyCollector.7.6.html for more information.

    # Create an object view
    obj_view = si.content.viewManager.CreateContainerView(si.content.rootFolder, [obj_type], True)

    # Create traversal spec to determine the path for collection
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        name='traverseEntities',
        path='view',
        skip=False,
        type=vim.view.ContainerView
    )

    # Create property spec to determine properties to be retrieved
    property_spec = vmodl.query.PropertyCollector.PropertySpec(
        type=obj_type,
        all=True if not property_list else False,
        pathSet=property_list
    )

    # Create object spec to navigate content
    obj_spec = vmodl.query.PropertyCollector.ObjectSpec(
        obj=obj_view,
        skip=True,
        selectSet=[traversal_spec]
    )

    # Create a filter spec and specify object, property spec in it
    filter_spec = vmodl.query.PropertyCollector.FilterSpec(
        objectSet=[obj_spec],
        propSet=[property_spec],
        reportMissingObjectsInResults=False
    )

    # Retrieve the contents
    content = si.content.propertyCollector.RetrieveContents([filter_spec])

    # Destroy the object view
    obj_view.Destroy()

    return content


def _get_mors_with_properties(obj_type, property_list=None):
    '''
    Returns list containing properties and managed object references for the managed object
    '''
    # Get all the content
    content = _get_content(obj_type, property_list)

    object_list = []
    for object in content:
        properties = {}
        for property in object.propSet:
            properties[property.name] = property.val
            properties['object'] = object.obj
        object_list.append(properties)

    return object_list


def _get_mor_by_property(obj_type, property_value, property_name='name'):
    '''
    Returns the first managed object reference having the specified property value
    '''
    # Get list of all managed object references with specified property
    object_list = _get_mors_with_properties(obj_type, [property_name])

    for object in object_list:
        if object[property_name] == property_value:
            return object['object']

    return None


def _edit_existing_hard_disk_helper(disk, size_kb):
    disk.capacityInKB = size_kb
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    disk_spec.device = disk

    return disk_spec


def _add_new_hard_disk_helper(disk_label, size_gb, unit_number):
    random_key = randint(-2099, -2000)

    size_kb = int(size_gb) * 1024 * 1024

    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = 'create'
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.key = random_key
    disk_spec.device.deviceInfo = vim.Description()
    disk_spec.device.deviceInfo.label = disk_label
    disk_spec.device.deviceInfo.summary = "{0} GB".format(size_gb)
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.controllerKey = 1000
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.capacityInKB = size_kb

    return disk_spec


def _edit_existing_network_adapter_helper(network_adapter, new_network_name):
    network_ref = _get_mor_by_property(vim.Network, new_network_name)
    network_adapter.backing.deviceName = new_network_name
    network_adapter.backing.network = network_ref
    network_adapter.deviceInfo.summary = new_network_name
    network_adapter.connectable.allowGuestControl = True
    network_adapter.connectable.startConnected = True
    network_spec = vim.vm.device.VirtualDeviceSpec()
    network_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    network_spec.device = network_adapter

    return network_spec


def _add_new_network_adapter_helper(network_adapter_label, network_name, adapter_type):
    random_key = randint(-4099, -4000)

    adapter_type.strip().lower()
    network_spec = vim.vm.device.VirtualDeviceSpec()

    if adapter_type == "vmxnet":
        network_spec.device = vim.vm.device.VirtualVmxnet()
    elif adapter_type == "vmxnet2":
        network_spec.device = vim.vm.device.VirtualVmxnet2()
    elif adapter_type == "vmxnet3":
        network_spec.device = vim.vm.device.VirtualVmxnet3()
    elif adapter_type == "e1000":
        network_spec.device = vim.vm.device.VirtualE1000()
    elif adapter_type == "e1000e":
        network_spec.device = vim.vm.device.VirtualE1000e()
    else:
        # If type not specified or does not match, create adapter of type vmxnet3
        network_spec.device = vim.vm.device.VirtualVmxnet3()
        log.warn("Cannot create network adapter of type {0}. Creating {1} of default type vmxnet3".format(adapter_type, network_adapter_label))

    network_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

    network_spec.device.key = random_key
    network_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
    network_spec.device.backing.deviceName = network_name
    network_spec.device.backing.network = _get_mor_by_property(vim.Network, network_name)
    network_spec.device.deviceInfo = vim.Description()
    network_spec.device.deviceInfo.label = network_adapter_label
    network_spec.device.deviceInfo.summary = network_name
    network_spec.device.wakeOnLanEnabled = True
    network_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    network_spec.device.connectable.startConnected = True
    network_spec.device.connectable.allowGuestControl = True

    return network_spec


def _manage_devices(devices, vm):
    unit_number = 0
    device_specs = []
    existing_disks_label = []
    existing_network_adapters_label = []
    nics_map = []

    # loop through all the devices the vm/template has
    # check if the device needs to be created or configured
    for device in vm.config.hardware.device:
        if hasattr(device.backing, 'fileName'):
            # this is a hard disk
            if 'disk' in devices.keys():
                # there is atleast one disk specified to be created/configured
                unit_number += 1
                # check if scsi controller
                if unit_number == 7:
                    unit_number += 1
                existing_disks_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in devices['disk'].keys():
                    size_gb = devices['disk'][device.deviceInfo.label]['size']
                    size_kb = int(size_gb) * 1024 * 1024
                    if device.capacityInKB < size_kb:
                        # expand the disk
                        disk_spec = _edit_existing_hard_disk_helper(device, size_kb)
                        device_specs.append(disk_spec)
        elif hasattr(device.backing, 'network'):
            # this is a network adapter
            if 'network' in devices.keys():
                # there is atleast one network adapter specified to be created/configured
                existing_network_adapters_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in devices['network'].keys():
                    network_name = devices['network'][device.deviceInfo.label]['name']
                    network_spec = _edit_existing_network_adapter_helper(device, network_name)
                    device_specs.append(network_spec)

                    adapter_mapping = vim.vm.customization.AdapterMapping()
                    adapter_mapping.adapter = vim.vm.customization.IPSettings()

                    if 'domain' in devices['network'][device.deviceInfo.label].keys():
                        domain = devices['network'][device.deviceInfo.label]['domain']
                        adapter_mapping.adapter.dnsDomain = domain
                    if 'gateway' in devices['network'][device.deviceInfo.label].keys():
                        gateway = devices['network'][device.deviceInfo.label]['gateway']
                        adapter_mapping.adapter.gateway = gateway
                    if 'ip' in devices['network'][device.deviceInfo.label].keys():
                        ip = str(devices['network'][device.deviceInfo.label]['ip'])
                        subnet_mask = str(devices['network'][device.deviceInfo.label]['subnet_mask'])
                        adapter_mapping.adapter.ip = vim.vm.customization.FixedIp(ipAddress=ip)
                        adapter_mapping.adapter.subnetMask = subnet_mask
                    else:
                        adapter_mapping.adapter.ip = vim.vm.customization.DhcpIpGenerator()
                    nics_map.append(adapter_mapping)

    if 'disk' in devices.keys():
        disks_to_create = list(set(devices['disk'].keys()) - set(existing_disks_label))
        disks_to_create.sort()
        log.debug("Disks to create: {0}".format(disks_to_create))
        for disk_label in disks_to_create:
            # create the disk
            size_gb = devices['disk'][disk_label]['size']
            disk_spec = _add_new_hard_disk_helper(disk_label, size_gb, unit_number)
            device_specs.append(disk_spec)
            unit_number += 1
            # check if scsi controller
            if unit_number == 7:
                unit_number += 1

    if 'network' in devices.keys():
        network_adapters_to_create = list(set(devices['network'].keys()) - set(existing_network_adapters_label))
        network_adapters_to_create.sort()
        log.debug("Networks to create: {0}".format(network_adapters_to_create))
        for network_adapter_label in network_adapters_to_create:
            network_name = devices['network'][network_adapter_label]['name']
            adapter_type = devices['network'][network_adapter_label]['type']
            # create the network adapter
            network_spec = _add_new_network_adapter_helper(network_adapter_label, network_name, adapter_type)
            device_specs.append(network_spec)

            adapter_mapping = vim.vm.customization.AdapterMapping()
            adapter_mapping.adapter = vim.vm.customization.IPSettings()

            if 'domain' in devices['network'][network_adapter_label].keys():
                domain = devices['network'][network_adapter_label]['domain']
                adapter_mapping.adapter.dnsDomain = domain
            if 'gateway' in devices['network'][network_adapter_label].keys():
                gateway = devices['network'][network_adapter_label]['gateway']
                adapter_mapping.adapter.gateway = gateway
            if 'ip' in devices['network'][network_adapter_label].keys():
                ip = str(devices['network'][network_adapter_label]['ip'])
                subnet_mask = str(devices['network'][network_adapter_label]['subnet_mask'])
                adapter_mapping.adapter.ip = vim.vm.customization.FixedIp(ipAddress=ip)
                adapter_mapping.adapter.subnetMask = subnet_mask
            else:
                adapter_mapping.adapter.ip = vim.vm.customization.DhcpIpGenerator()
            nics_map.append(adapter_mapping)

    ret = {
        'device_specs': device_specs,
        'nics_map': nics_map
    }

    return ret


def _wait_for_ip(vm, max_wait_minute):
    time_counter = 0
    max_wait_second = int(max_wait_minute * 60)
    while time_counter < max_wait_second:
        log.info("Waiting to get IP information [{0} s]".format(time_counter))
        for net in vm.guest.net:
            if net.ipConfig.ipAddress:
                for current_ip in net.ipConfig.ipAddress:
                    if match(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', current_ip.ipAddress) and current_ip.ipAddress != '127.0.0.1':
                        ip = current_ip.ipAddress
                        return ip
        time.sleep(5)
        time_counter += 5
    return False


def _wait_for_task(task, task_type, sleep_seconds=1, log_level='debug'):
    time_counter = 0
    while task.info.state == 'running':
        message = "Waiting for {0} task to finish [{1} s]".format(task_type, time_counter)
        if log_level=='info':
            log.info(message)
        else:
            log.debug(message)
        time.sleep(int(sleep_seconds))
        time_counter += int(sleep_seconds)
    if task.info.state == 'success':
        message = "Successfully completed {0} task in {1} seconds".format(task_type, time_counter)
        if log_level=='info':
            log.info(message)
        else:
            log.debug(message)
    else:
        raise task.info.error


def _format_instance_info(vm):
    device_full_info = {}
    disk_full_info = {}
    for device in vm["config.hardware.device"]:
        device_full_info[device.deviceInfo.label] = {
            'key': device.key,
            'label': device.deviceInfo.label,
            'summary': device.deviceInfo.summary,
            'type': type(device).__name__.rsplit(".", 1)[1],
            'unitNumber': device.unitNumber
        }

        if hasattr(device.backing, 'network'):
            device_full_info[device.deviceInfo.label]['addressType'] = device.addressType
            device_full_info[device.deviceInfo.label]['macAddress'] = device.macAddress

        if hasattr(device, 'busNumber'):
            device_full_info[device.deviceInfo.label]['busNumber'] = device.busNumber

        if hasattr(device, 'device'):
            device_full_info[device.deviceInfo.label]['devices'] = device.device

        if hasattr(device, 'videoRamSizeInKB'):
            device_full_info[device.deviceInfo.label]['videoRamSizeInKB'] = device.videoRamSizeInKB

        if isinstance(device, vim.vm.device.VirtualDisk):
            device_full_info[device.deviceInfo.label]['capacityInKB'] = device.capacityInKB
            device_full_info[device.deviceInfo.label]['diskMode'] = device.backing.diskMode
            disk_full_info[device.deviceInfo.label] = device_full_info[device.deviceInfo.label].copy()
            disk_full_info[device.deviceInfo.label]['fileName'] = device.backing.fileName

    storage_full_info = {
        'committed': vm["summary.storage.committed"],
        'uncommitted': vm["summary.storage.uncommitted"],
        'unshared': vm["summary.storage.unshared"],
        'disks': disk_full_info,
    }

    file_full_info = {}
    for file in vm["layoutEx.file"]:
        file_full_info[file.key] = {
            'key': file.key,
            'name': file.name,
            'size': file.size,
            'type': file.type
        }

    network_full_info = {}
    for net in vm["guest.net"]:
        network_full_info = {
            'connected': net.connected,
            'ip_addresses': net.ipAddress,
            'mac_address': net.macAddress,
            'network': net.network
        }

    vm_full_info = {
        'devices': device_full_info,
        'storage': storage_full_info,
        'files': file_full_info,
        'guest_full_name': vm["config.guestFullName"],
        'guest_id': vm["config.guestId"],
        'hostname': vm["object"].guest.hostName,
        'ip_address': vm["object"].guest.ipAddress,
        'mac_address': network_full_info["mac_address"] if "mac_address" in network_full_info else None,
        'memory_mb': vm["config.hardware.memoryMB"],
        'name': vm['name'],
        'net': [network_full_info],
        'num_cpu': vm["config.hardware.numCPU"],
        'path': vm["config.files.vmPathName"],
        'status': vm["summary.runtime.powerState"],
        'tools_status': vm["guest.toolsStatus"],
    }

    return vm_full_info


def _get_snapshots(snapshot_list, parent_snapshot_path=""):
    snapshots = {}
    for snapshot in snapshot_list:
        snapshot_path = "{0}/{1}".format(parent_snapshot_path, snapshot.name)
        snapshots[snapshot_path] = {
            'name': snapshot.name,
            'description': snapshot.description,
            'created': str(snapshot.createTime).split('.')[0],
            'state': snapshot.state,
            'path': snapshot_path,
        }
        # Check if child snapshots exist
        if snapshot.childSnapshotList:
            snapshots.update(_get_snapshots(snapshot.childSnapshotList, snapshot_path))
    return snapshots


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
    datacenter_properties = ["name"]

    datacenter_list = _get_mors_with_properties(vim.Datacenter, datacenter_properties)

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
    cluster_properties = ["name"]

    cluster_list = _get_mors_with_properties(vim.ClusterComputeResource, cluster_properties)

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
    datastore_cluster_properties = ["name"]

    datastore_cluster_list = _get_mors_with_properties(vim.StoragePod, datastore_cluster_properties)

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
    datastore_properties = ["name"]

    datastore_list = _get_mors_with_properties(vim.Datastore, datastore_properties)

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
    host_properties = ["name"]

    host_list = _get_mors_with_properties(vim.HostSystem, host_properties)

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
    resource_pool_properties = ["name"]

    resource_pool_list = _get_mors_with_properties(vim.ResourcePool, resource_pool_properties)

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
    network_properties = ["name"]

    network_list = _get_mors_with_properties(vim.Network, network_properties)

    for network in network_list:
        networks.append(network["name"])

    return {'Networks': networks}


def list_nodes_min(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the provider, with no details

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud -f list_nodes_min my-vmware-config
    '''

    ret = {}
    vm_properties = ["name"]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        ret[vm["name"]] = True

    return ret


def list_nodes(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the provider, with basic fields

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

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

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


def list_nodes_full(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the provider, with full details

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_full my-vmware-config
    '''

    ret = {}
    vm_properties = [
        "config.hardware.device",
        "summary.storage.committed",
        "summary.storage.uncommitted",
        "summary.storage.unshared",
        "layoutEx.file",
        "config.guestFullName",
        "config.guestId",
        "guest.net",
        "config.hardware.memoryMB",
        "name",
        "config.hardware.numCPU",
        "config.files.vmPathName",
        "summary.runtime.powerState",
        "guest.toolsStatus"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        vm_full_info = _format_instance_info(vm)
        ret[vm_full_info['name']] = vm_full_info

    return ret


def show_instance(name, call=None):
    '''
    List all available details of the specified VM

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    vm_properties = [
        "config.hardware.device",
        "summary.storage.committed",
        "summary.storage.uncommitted",
        "summary.storage.unshared",
        "layoutEx.file",
        "config.guestFullName",
        "config.guestId",
        "guest.net",
        "config.hardware.memoryMB",
        "name",
        "config.hardware.numCPU",
        "config.files.vmPathName",
        "summary.runtime.powerState",
        "guest.toolsStatus"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm['name'] == name:
            vm_full_info = _format_instance_info(vm)
    return vm_full_info


def avail_images():
    '''
    Return a list of all the templates present in this VMware environment with basic
    details

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-vmware-config
    '''

    templates = {}
    vm_properties = [
        "name",
        "config.template",
        "config.guestFullName",
        "config.hardware.numCPU",
        "config.hardware.memoryMB"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["config.template"]:
            templates[vm["name"]] = {
                'name': vm["name"],
                'guest_fullname': vm["config.guestFullName"],
                'cpus': vm["config.hardware.numCPU"],
                'ram': vm["config.hardware.memoryMB"]
            }
    return templates


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
    folder_properties = ["name"]

    folder_list = _get_mors_with_properties(vim.Folder, folder_properties)

    for folder in folder_list:
        folders.append(folder["name"])

    return {'Folders': folders}


def list_snapshots(kwargs=None, call=None):
    '''
    List snapshots either for all VMs and templates or for a specific VM/template
    in this VMware environment

    To list snapshots for all VMs and templates:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_snapshots my-vmware-config

    To list snapshots for a specific VM/template:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_snapshots my-vmware-config name="vmname"
    '''
    if call != 'function':
        log.error(
            'The list_snapshots function must be called with -f or --function.'
        )
        return False

    ret = {}
    vm_properties = [
        "name",
        "rootSnapshot",
        "snapshot"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["rootSnapshot"]:
            if kwargs and 'name' in kwargs and vm["name"] == kwargs['name']:
                return {vm["name"]: _get_snapshots(vm["snapshot"].rootSnapshotList)}
            else:
                ret[vm["name"]] = _get_snapshots(vm["snapshot"].rootSnapshotList)
    return ret


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

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

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

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

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


def suspend(name, call=None):
    '''
    To suspend a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a suspend vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The suspend action must be called with -a or --action.'
        )

    vm_properties = [
        "name",
        "summary.runtime.powerState"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["name"] == name:
            if vm["summary.runtime.powerState"] == "poweredOff":
                ret = 'cannot suspend in powered off state'
                log.info('VM {0} {1}'.format(name, ret))
                return ret
            elif vm["summary.runtime.powerState"] == "suspended":
                ret = 'already suspended'
                log.info('VM {0} {1}'.format(name, ret))
                return ret
            try:
                log.info('Suspending VM {0}'.format(name))
                vm["object"].Suspend()
            except Exception as exc:
                log.error('Could not suspend VM {0}: {1}'.format(name, exc))
                return 'failed to suspend'
    return 'suspended'


def reset(name, call=None):
    '''
    To reset a VM using its name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reset vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The reset action must be called with -a or --action.'
        )

    vm_properties = [
        "name",
        "summary.runtime.powerState"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["name"] == name:
            if vm["summary.runtime.powerState"] == "suspended" or vm["summary.runtime.powerState"] == "poweredOff":
                ret = 'cannot reset in suspended/powered off state'
                log.info('VM {0} {1}'.format(name, ret))
                return ret
            try:
                log.info('Resetting VM {0}'.format(name))
                vm["object"].Reset()
            except Exception as exc:
                log.error('Could not reset VM {0}: {1}'.format(name, exc))
                return 'failed to reset'
    return 'reset'


def destroy(name, call=None):
    '''
    To destroy a VM from the VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vmname
        salt-cloud --destroy vmname
        salt-cloud -a destroy vmname
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    vm_properties = [
        "name",
        "summary.runtime.powerState"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["name"] == name:
            if vm["summary.runtime.powerState"] != "poweredOff":
                #Power off the vm first
                try:
                    log.info('Powering Off VM {0}'.format(name))
                    task = vm["object"].PowerOff()
                    _wait_for_task(task, "power off")
                except Exception as exc:
                    log.error('Could not destroy VM {0}: {1}'.format(name, exc))
                    return 'failed to destroy'
            task = vm["object"].Destroy_Task()
            _wait_for_task(task, "destroy")

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)
    return True


def create(vm_):
    '''
    To create a single VM in the VMware environment.

    Sample profile and arguments that can be specified in it can be found
    :ref:`here. <vmware-cloud-profile>`

    CLI Example:

    .. code-block:: bash

        salt-cloud -p vmware-centos6.5 vmname
    '''
    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    vm_name = config.get_cloud_config_value(
        'name', vm_, __opts__, default=None
    )
    folder = config.get_cloud_config_value(
        'folder', vm_, __opts__, default=None
    )
    datacenter = config.get_cloud_config_value(
        'datacenter', vm_, __opts__, default=None
    )
    resourcepool = config.get_cloud_config_value(
        'resourcepool', vm_, __opts__, default=None
    )
    cluster = config.get_cloud_config_value(
        'cluster', vm_, __opts__, default=None
    )
    datastore = config.get_cloud_config_value(
        'datastore', vm_, __opts__, default=None
    )
    host = config.get_cloud_config_value(
        'host', vm_, __opts__, default=None
    )
    template = config.get_cloud_config_value(
        'template', vm_, __opts__, default=False
    )
    num_cpus = config.get_cloud_config_value(
        'cpus', vm_, __opts__, default=None
    )
    memory = config.get_cloud_config_value(
        'memory', vm_, __opts__, default=None
    )
    devices = config.get_cloud_config_value(
        'devices', vm_, __opts__, default=None
    )
    extra_config = config.get_cloud_config_value(
        'extra_config', vm_, __opts__, default=None
    )
    power = config.get_cloud_config_value(
        'power_on', vm_, __opts__, default=False
    )
    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    deploy = config.get_cloud_config_value(
        'deploy', vm_, __opts__, search_global=False, default=True
    )

    if 'clonefrom' in vm_:
        # Clone VM/template from specified VM/template
        object_ref = _get_mor_by_property(vim.VirtualMachine, vm_['clonefrom'])
        if object_ref.config.template:
            clone_type = "template"
        else:
            clone_type = "vm"

        # Either a cluster, or a resource pool must be specified when cloning from template.
        if resourcepool:
            resourcepool_ref = _get_mor_by_property(vim.ResourcePool, resourcepool)
        elif cluster:
            cluster_ref = _get_mor_by_property(vim.ClusterComputeResource, cluster)
            resourcepool_ref = cluster_ref.resourcePool
        elif clone_type == "template":
            log.error('You must either specify a cluster, a host or a resource pool')
            return False

        # Either a datacenter or a folder can be optionally specified
        # If not specified, the existing VM/template\'s parent folder is used.
        if folder:
            folder_ref = _get_mor_by_property(vim.Folder, folder)
        elif datacenter:
            datacenter_ref = _get_mor_by_property(vim.Datacenter, datacenter)
            folder_ref = datacenter_ref.vmFolder
        else:
            folder_ref = object_ref.parent

        # Create the relocation specs
        reloc_spec = vim.vm.RelocateSpec()

        if resourcepool or cluster:
            reloc_spec.pool = resourcepool_ref

        # Either a datastore/datastore cluster can be optionally specified.
        # If not specified, the current datastore is used.
        if datastore:
            datastore_ref = _get_mor_by_property(vim.Datastore, datastore)

        if host:
            host_ref = _get_mor_by_property(vim.HostSystem, host)
            if host_ref:
                reloc_spec.host = host_ref
            else:
                log.warning("Specified host: {0} does not exist".format(host))
                log.warning("Using host used by the {0} {1}".format(clone_type, vm_['clonefrom']))

        # Create the config specs
        config_spec = vim.vm.ConfigSpec()

        if num_cpus:
            config_spec.numCPUs = num_cpus

        if memory:
            config_spec.memoryMB = memory

        if devices:
            specs = _manage_devices(devices, object_ref)
            config_spec.deviceChange = specs['device_specs']

        if extra_config:
            for key, value in extra_config.iteritems():
                option = vim.option.OptionValue(key=key, value=value)
                config_spec.extraConfig.append(option)

        # Create the clone specs
        clone_spec = vim.vm.CloneSpec(
            template=template,
            location=reloc_spec,
            config=config_spec
        )

        if specs['nics_map']:
            if "Windows" not in object_ref.config.guestFullName:
                global_ip = vim.vm.customization.GlobalIPSettings()
                if vm_['dns_servers']:
                    global_ip.dnsServerList = vm_['dns_servers']
                identity = vim.vm.customization.LinuxPrep()
                identity.domain = vm_['domain']
                identity.hostName = vim.vm.customization.FixedName(name=vm_name)

                custom_spec = vim.vm.customization.Specification(
                    nicSettingMap=specs['nics_map'],
                    globalIPSettings=global_ip,
                    identity=identity
                )
                clone_spec.customization = custom_spec

        if not template:
            clone_spec.powerOn = power

        log.debug('clone_spec set to {0}\n'.format(
            pprint.pformat(clone_spec))
        )

        try:
            log.info("Creating {0} from {1}({2})\n".format(vm_['name'], clone_type, vm_['clonefrom']))
            salt.utils.cloud.fire_event(
                'event',
                'requesting instance',
                'salt/cloud/{0}/requesting'.format(vm_['name']),
                {'kwargs': vm_},
                transport=__opts__['transport']
            )

            task = object_ref.Clone(folder_ref, vm_name, clone_spec)
            _wait_for_task(task, "clone", 5, 'info')
        except Exception as exc:
            log.error(
                'Error creating {0}: {1}'.format(
                    vm_['name'],
                    exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return False

        new_vm_ref = _get_mor_by_property(vim.VirtualMachine, vm_name)

        # If it a template or if it does not need to be powered on, or if deploy is False then do not wait for ip
        if not template and power:
            ip = _wait_for_ip(new_vm_ref, 20)
            if ip:
                log.debug("IP is: {0}".format(ip))
                # ssh or smb using ip and install salt
                if deploy:
                    vm_['key_filename'] = key_filename
                    vm_['ssh_host'] = ip

                    salt.utils.cloud.bootstrap(vm_, __opts__)
            else:
                log.warning("Could not get IP information for {0}".format(vm_name))

        data = show_instance(vm_name, call='action')

        salt.utils.cloud.fire_event(
            'event',
            'created instance',
            'salt/cloud/{0}/created'.format(vm_['name']),
            {
                'name': vm_['name'],
                'profile': vm_['profile'],
                'provider': vm_['provider'],
            },
            transport=__opts__['transport']
        )
    else:
        log.error("clonefrom option hasn\'t been specified. Exiting.")
        return False

    return {vm_name: data}
