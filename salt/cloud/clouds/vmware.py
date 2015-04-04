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
    from random import randint
    random_key = randint(-2099, -2000)

    size_kb = long(size_gb) * 1024 * 1024

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


def _add_or_edit_disks(disk, vm):
    unit_number = 0
    existing_disks_label = []
    disks_specs_list = []
    for device in vm.config.hardware.device:
        if hasattr(device.backing, 'fileName'):
            unit_number += 1
            # check if scsi controller
            if unit_number == 7:
                unit_number += 1
            existing_disks_label.append(device.deviceInfo.label)
            if device.deviceInfo.label in disk.keys():
                size_kb = long(disk[device.deviceInfo.label]['size']) * 1024 * 1024
                if device.capacityInKB < size_kb:
                    # expand the disk
                    disk_spec = _edit_existing_hard_disk_helper(device, size_kb)
                    disks_specs_list.append(disk_spec)

    disks_to_create = list(set(disk.keys()) - set(existing_disks_label))
    disks_to_create.sort()
    log.debug("Disks to create: {0}".format(disks_to_create))
    for disk_label in disks_to_create:
        # create the disk
        disk_spec = _add_new_hard_disk_helper(disk_label, disk[disk_label]['size'], unit_number)
        disks_specs_list.append(disk_spec)
        unit_number += 1
        # check if scsi controller
        if unit_number == 7:
            unit_number += 1

    return disks_specs_list


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
    from random import randint
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
        log.warn("Cannot create network adapter of type {0}. Creating default type vmxnet3".format(adapter_type))

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


def _add_or_edit_network_adapters(network, vm):
    network_specs_list = []
    existing_network_adapters_label = []
    for device in vm.config.hardware.device:
        if hasattr(device.backing, 'network'):
            existing_network_adapters_label.append(device.deviceInfo.label)
            if device.deviceInfo.label in network.keys():
                network_name = network[device.deviceInfo.label]['name']
                # Only edit the network adapter if network name is different
                if device.backing.deviceName != network_name:
                    network_spec = _edit_existing_network_adapter_helper(device, network_name)
                    network_specs_list.append(network_spec)

    network_adapters_to_create = list(set(network.keys()) - set(existing_network_adapters_label))
    network_adapters_to_create.sort()
    log.debug("Networks to create: {0}".format(network_adapters_to_create))
    for network_adapter_label in network_adapters_to_create:
        # create the network adapter
        network_spec = _add_new_network_adapter_helper(network_adapter_label, network[network_adapter_label]['name'], network[network_adapter_label]['type'])
        network_specs_list.append(network_spec)

    return network_specs_list


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
    cluster_properties = [
                             "name"
                         ]

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
    datastore_cluster_properties = [
                                       "name"
                                   ]

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
    datastore_properties = [
                               "name"
                           ]

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
    host_properties = [
                          "name"
                      ]

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
    resource_pool_properties = [
                                   "name"
                               ]

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
    network_properties = [
                             "name"
                         ]

    network_list = _get_mors_with_properties(vim.Network, network_properties)

    for network in network_list:
        networks.append(network["name"])

    return {'Networks': networks}


def list_nodes_min(kwargs=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with no details

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud -f list_nodes_min my-vmware-config
    '''

    ret = {}
    vm_properties = [
                        "name"
                    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

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

    folder_list = _get_mors_with_properties(vim.Folder, folder_properties)

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
                    while task.info.state != 'success':
                        log.debug("Waiting for Power off task to finish")
                except Exception as exc:
                    log.error('Could not destroy VM {0}: {1}'.format(name, exc))
                    return 'failed to destroy'
            task = vm["object"].Destroy_Task()
            while task.info.state != 'success':
                log.debug("Waiting for destroy task to finish")

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)
    return 'True'


def create(vm_):
    '''
    To create a single VM in the VMware environment.

    Create a profile at ``/etc/salt/cloud.profiles`` or ``/etc/salt/cloud.profiles.d/vmware.conf``

    .. code-block:: yaml

        vmware-centos6.5:
          provider: vmware-vcenter01
          clonefrom: test-vm

          ## Optional arguments
          num_cpus: 4
          memory: 8192
          disk:
            'Hard disk 2':
              size: 30
            'Hard disk 3':
              size: 20
            'Hard disk 4':
              size: 5
          network:
            'Network adapter 1':
              name: 10.20.30-400-Test
            'Network adapter 2':
              name: 10.30.40-500-Dev
              type: e1000
            'Network adapter 3':
              name: 10.40.50-600-Prod
              type: vmxnet3
          datastore: HUGE-DATASTORE-Cluster

          # If cloning from template, either resourcepool or cluster MUST be specified!
          resourcepool: Resources
          cluster: Prod

          folder: Development
          datacenter: DC1
          host: c4212n-002.domain.com
          template: False
          power_on: True


    provider
        Enter the name that was specified when the cloud provider config was created.

    clonefrom
        Enter the name of the VM/template to clone from.

    num_cpus
        Enter the number of vCPUS you want the VM/template to have. If not specified, the current
        VM/template\'s vCPU count is used.

    memory
        Enter memory (in MB) you want the VM/template to have. If not specified, the current
        VM/template\'s memory size is used.

    disk
        Enter the disk specification here. If the hard disk doesn\'t exist, it will be created with
        the provided size. If the hard disk already exists, it will be expanded if the provided size
        is greater than the current size of the disk.

    network
        Enter the network adapter specification here. If the network adapter doesn\'t exist, a new
        network adapter will be created with the specified network name and type. If the network
        adapter already exists, it will be reconfigured with the network name specified. Currently,
        only network adapters of type vmxnet, vmxnet2, vmxnet3, e1000 and e1000e can be created. If
        the specified network adapter type is not one of these, a network adapter of type vmxnet3
        will be created by default.

    datastore
        Enter the name of the datastore or the datastore cluster where the virtual machine should
        be located on physical storage. If not specified, the current datastore is used.

        .. note::

            - If you specify a datastore cluster name, DRS Storage recommendation is automatically
              applied.
            - If you specify a datastore name, DRS Storage recommendation is disabled.

    resourcepool
        Enter the name of the resourcepool to which the new virtual machine should be
        attached. This determines what compute resources will be available to the clone.

        .. note::

            - For a clone operation from a virtual machine, it will use the same resourcepool as
              the original virtual machine unless specified.
            - For a clone operation from a template to a virtual machine, specifying either this
              or cluster is required. If both are specified, the resourcepool value will be used.
            - For a clone operation to a template, this argument is ignored.

    cluster
        Enter the name of the cluster whose resource pool the new virtual machine should be
        attached to.

        .. note::

            - For a clone operation from a virtual machine, it will use the same cluster\'s
              resourcepool as the original virtual machine unless specified.
            - For a clone operation from a template to a virtual machine, specifying either
              this or resourcepool is required. If both are specified, the resourcepool value
              will be used.
            - For a clone operation to a template, this argument is ignored.

    folder
        Enter the name of the folder that will contain the new virtual machine.

        .. note::

            - For a clone operation from a VM/template, the new VM/template will be added to the
              same folder that the original VM/template belongs to unless specified.
            - If both folder and datacenter are specified, the folder value will be used.

    datacenter
        Enter the name of the datacenter that will contain the new virtual machine.

        .. note::

            - For a clone operation from a VM/template, the new VM/template will be added to the
              same folder that the original VM/template belongs to unless specified.
            - If both folder and datacenter are specified, the folder value will be used.

    host
        Enter the name of the target host where the virtual machine should be registered.

        If not specified:

        .. note::

            - If resource pool is not specified, current host is used.
            - If resource pool is specified, and the target pool represents a stand-alone
              host, the host is used.
            - If resource pool is specified, and the target pool represents a DRS-enabled
              cluster, a host selected by DRS is used.
            - If resource pool is specified and the target pool represents a cluster without
              DRS enabled, an InvalidArgument exception be thrown.

    template
        Specifies whether the new virtual machine should be marked as a template or not.
        Default is ``template: False``.

    power_on
        Specifies whether the new virtual machine should be powered on or not. If ``template: True``
        is set, this field is ignored. Default is ``power_on: True``.


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
    disk = config.get_cloud_config_value(
        'disk', vm_, __opts__, default=None
    )
    network = config.get_cloud_config_value(
        'network', vm_, __opts__, default=None
    )
    power = config.get_cloud_config_value(
        'power_on', vm_, __opts__, default=False
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

        if disk or network:
            devices = []
            if disk:
                devices.extend(_add_or_edit_disks(disk, object_ref))
            if network:
                devices.extend(_add_or_edit_network_adapters(network, object_ref))
            config_spec.deviceChange = devices

        # Create the clone specs
        clone_spec = vim.vm.CloneSpec(
            template=template,
            location=reloc_spec,
            config=config_spec
        )

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
            time_counter = 0
            while task.info.state != 'success':
                log.debug("Waiting for clone task to finish [{0} s]".format(time_counter))
                time.sleep(5)
                time_counter += 5
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

    return {vm_name: True}
