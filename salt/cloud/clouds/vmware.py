# -*- coding: utf-8 -*-
'''
VMware Cloud Module
===================

.. versionadded:: 2015.5.4

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
      user: "DOMAIN\\user"
      password: "verybadpass"
      url: "vcenter01.domain.com"

    vmware-vcenter02:
      provider: vmware
      user: "DOMAIN\\user"
      password: "verybadpass"
      url: "vcenter02.domain.com"

    vmware-vcenter03:
      provider: vmware
      user: "DOMAIN\\user"
      password: "verybadpass"
      url: "vcenter03.domain.com"
      protocol: "http"
      port: 80

.. note::

    Optionally, ``protocol`` and ``port`` can be specified if the vCenter
    server is not using the defaults. Default is ``protocol: https`` and
    ``port: 443``.

To test the connection for ``my-vmware-config`` specified in the cloud
configuration, run :py:func:`test_vcenter_connection`
'''

# Import python libs
from __future__ import absolute_import
from random import randint
from re import match, findall
import atexit
import pprint
import logging
import time
import os.path
import subprocess

# Import salt libs
import salt.utils
import salt.utils.cloud
import salt.utils.xmlutil
from salt.exceptions import SaltCloudSystemExit

# Import salt cloud libs
import salt.config as config

# Attempt to import pyVim and pyVmomi libs
HAS_LIBS = False
try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim, vmodl
    HAS_LIBS = True
except Exception:
    pass

# Disable InsecureRequestWarning generated on python > 2.6
try:
    from requests.packages.urllib3 import disable_warnings
    disable_warnings()
except Exception:
    pass

# Import third party libs
try:
    import salt.ext.six as six
except ImportError:
    # Salt version <= 2014.7.0
    try:
        import six
    except ImportError:
        HAS_LIBS = False

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


def _str_to_bool(var):
    if isinstance(var, bool):
        return var

    if isinstance(var, six.string_types):
        return True if var.lower() == 'true' else False

    return None


def _get_si():
    '''
    Authenticate with vCenter server and return service instance object.
    '''

    url = config.get_cloud_config_value(
        'url', get_configured_provider(), __opts__, search_global=False
    )
    username = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    )
    password = config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__, search_global=False
    )
    protocol = config.get_cloud_config_value(
        'protocol', get_configured_provider(), __opts__, search_global=False, default='https'
    )
    port = config.get_cloud_config_value(
        'port', get_configured_provider(), __opts__, search_global=False, default=443
    )

    try:
        si = SmartConnect(
            host=url,
            user=username,
            pwd=password,
            protocol=protocol,
            port=port
        )
    except Exception as exc:
        if isinstance(exc, vim.fault.HostConnectFault) and '[SSL: CERTIFICATE_VERIFY_FAILED]' in exc.msg:
            try:
                import ssl
                default_context = ssl._create_default_https_context
                ssl._create_default_https_context = ssl._create_unverified_context
                si = SmartConnect(
                    host=url,
                    user=username,
                    pwd=password,
                    protocol=protocol,
                    port=port
                )
                ssl._create_default_https_context = default_context
            except:
                err_msg = exc.msg if isinstance(exc, vim.fault.InvalidLogin) and hasattr(exc, 'msg') else 'Could not connect to the specified vCenter server. Please check the specified protocol or url or port'
                raise SaltCloudSystemExit(err_msg)
        else:
            err_msg = exc.msg if isinstance(exc, vim.fault.InvalidLogin) and hasattr(exc, 'msg') else 'Could not connect to the specified vCenter server. Please check the specified protocol or url or port'
            raise SaltCloudSystemExit(err_msg)

    atexit.register(Disconnect, si)

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

    size_kb = int(size_gb * 1024.0 * 1024.0)

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


def _get_network_adapter_type(adapter_type):
    if adapter_type == "vmxnet":
        return vim.vm.device.VirtualVmxnet()
    elif adapter_type == "vmxnet2":
        return vim.vm.device.VirtualVmxnet2()
    elif adapter_type == "vmxnet3":
        return vim.vm.device.VirtualVmxnet3()
    elif adapter_type == "e1000":
        return vim.vm.device.VirtualE1000()
    elif adapter_type == "e1000e":
        return vim.vm.device.VirtualE1000e()


def _edit_existing_network_adapter_helper(network_adapter, new_network_name, adapter_type, switch_type):
    adapter_type.strip().lower()
    switch_type.strip().lower()

    if adapter_type in ["vmxnet", "vmxnet2", "vmxnet3", "e1000", "e1000e"]:
        edited_network_adapter = _get_network_adapter_type(adapter_type)
        if isinstance(network_adapter, type(edited_network_adapter)):
            edited_network_adapter = network_adapter
        else:
            log.debug("Changing type of '{0}' from '{1}' to '{2}'".format(network_adapter.deviceInfo.label, type(network_adapter).__name__.rsplit(".", 1)[1][7:].lower(), adapter_type))
    else:
        # If type not specified or does not match, dont change adapter type
        if adapter_type:
            log.error("Cannot change type of '{0}' to '{1}'. Not changing type".format(network_adapter.deviceInfo.label, adapter_type))
        edited_network_adapter = network_adapter

    if switch_type == 'standard':
        network_ref = _get_mor_by_property(vim.Network, new_network_name)
        edited_network_adapter.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        edited_network_adapter.backing.deviceName = new_network_name
        edited_network_adapter.backing.network = network_ref
    elif switch_type == 'distributed':
        network_ref = _get_mor_by_property(vim.dvs.DistributedVirtualPortgroup, new_network_name)
        dvs_port_connection = vim.dvs.PortConnection(
            portgroupKey=network_ref.key,
            switchUuid=network_ref.config.distributedVirtualSwitch.uuid
        )
        edited_network_adapter.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
        edited_network_adapter.backing.port = dvs_port_connection
    else:
        # If switch type not specified or does not match, show error and return
        if not switch_type:
            err_msg = "The switch type to be used by '{0}' has not been specified".format(network_adapter.deviceInfo.label)
        else:
            err_msg = "Cannot create '{0}'. Invalid/unsupported switch type '{1}'".format(network_adapter.deviceInfo.label, switch_type)
        raise SaltCloudSystemExit(err_msg)

    edited_network_adapter.key = network_adapter.key
    edited_network_adapter.deviceInfo = network_adapter.deviceInfo
    edited_network_adapter.deviceInfo.summary = new_network_name
    edited_network_adapter.connectable = network_adapter.connectable
    edited_network_adapter.slotInfo = network_adapter.slotInfo
    edited_network_adapter.controllerKey = network_adapter.controllerKey
    edited_network_adapter.unitNumber = network_adapter.unitNumber
    edited_network_adapter.addressType = network_adapter.addressType
    edited_network_adapter.macAddress = network_adapter.macAddress
    edited_network_adapter.wakeOnLanEnabled = network_adapter.wakeOnLanEnabled
    network_spec = vim.vm.device.VirtualDeviceSpec()
    network_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    network_spec.device = edited_network_adapter

    return network_spec


def _add_new_network_adapter_helper(network_adapter_label, network_name, adapter_type, switch_type):
    random_key = randint(-4099, -4000)

    adapter_type.strip().lower()
    switch_type.strip().lower()
    network_spec = vim.vm.device.VirtualDeviceSpec()

    if adapter_type in ["vmxnet", "vmxnet2", "vmxnet3", "e1000", "e1000e"]:
        network_spec.device = _get_network_adapter_type(adapter_type)
    else:
        # If type not specified or does not match, create adapter of type vmxnet3
        if not adapter_type:
            log.debug("The type of '{0}' has not been specified. Creating of default type 'vmxnet3'".format(network_adapter_label))
        else:
            log.error("Cannot create network adapter of type '{0}'. Creating '{1}' of default type 'vmxnet3'".format(adapter_type, network_adapter_label))
        network_spec.device = vim.vm.device.VirtualVmxnet3()

    network_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

    if switch_type == 'standard':
        network_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        network_spec.device.backing.deviceName = network_name
        network_spec.device.backing.network = _get_mor_by_property(vim.Network, network_name)
    elif switch_type == 'distributed':
        network_ref = _get_mor_by_property(vim.dvs.DistributedVirtualPortgroup, network_name)
        dvs_port_connection = vim.dvs.PortConnection(
            portgroupKey=network_ref.key,
            switchUuid=network_ref.config.distributedVirtualSwitch.uuid
        )
        network_spec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
        network_spec.device.backing.port = dvs_port_connection
    else:
        # If switch type not specified or does not match, show error and return
        if not switch_type:
            err_msg = "The switch type to be used by '{0}' has not been specified".format(network_adapter_label)
        else:
            err_msg = "Cannot create '{0}'. Invalid/unsupported switch type '{1}'".format(network_adapter_label, switch_type)
        raise SaltCloudSystemExit(err_msg)

    network_spec.device.key = random_key
    network_spec.device.deviceInfo = vim.Description()
    network_spec.device.deviceInfo.label = network_adapter_label
    network_spec.device.deviceInfo.summary = network_name
    network_spec.device.wakeOnLanEnabled = True
    network_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    network_spec.device.connectable.startConnected = True
    network_spec.device.connectable.allowGuestControl = True

    return network_spec


def _edit_existing_scsi_adapter_helper(scsi_adapter, bus_sharing):
    scsi_adapter.sharedBus = bus_sharing
    scsi_spec = vim.vm.device.VirtualDeviceSpec()
    scsi_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    scsi_spec.device = scsi_adapter

    return scsi_spec


def _add_new_scsi_adapter_helper(scsi_adapter_label, properties, bus_number):
    random_key = randint(-1050, -1000)
    adapter_type = properties['type'].strip().lower() if 'type' in properties else None
    bus_sharing = properties['bus_sharing'].strip().lower() if 'bus_sharing' in properties else None

    scsi_spec = vim.vm.device.VirtualDeviceSpec()

    if adapter_type == "lsilogic":
        summary = "LSI Logic"
        scsi_spec.device = vim.vm.device.VirtualLsiLogicController()
    elif adapter_type == "lsilogic_sas":
        summary = "LSI Logic Sas"
        scsi_spec.device = vim.vm.device.VirtualLsiLogicSASController()
    elif adapter_type == "paravirtual":
        summary = "VMware paravirtual SCSI"
        scsi_spec.device = vim.vm.device.ParaVirtualSCSIController()
    else:
        # If type not specified or does not match, show error and return
        if not adapter_type:
            err_msg = "The type of '{0}' has not been specified".format(scsi_adapter_label)
        else:
            err_msg = "Cannot create '{0}'. Invalid/unsupported type '{1}'".format(scsi_adapter_label, adapter_type)
        raise SaltCloudSystemExit(err_msg)

    scsi_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

    scsi_spec.device.key = random_key
    scsi_spec.device.busNumber = bus_number
    scsi_spec.device.deviceInfo = vim.Description()
    scsi_spec.device.deviceInfo.label = scsi_adapter_label
    scsi_spec.device.deviceInfo.summary = summary

    if bus_sharing == "virtual":
        # Virtual disks can be shared between virtual machines on the same server
        scsi_spec.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.virtualSharing

    elif bus_sharing == "physical":
        # Virtual disks can be shared between virtual machines on any server
        scsi_spec.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.physicalSharing

    else:
        # Virtual disks cannot be shared between virtual machines
        scsi_spec.device.sharedBus = vim.vm.device.VirtualSCSIController.Sharing.noSharing

    return scsi_spec


def _set_cd_or_dvd_backing_type(drive, device_type, mode, iso_path):
    if device_type == "datastore_iso_file":
        drive.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
        drive.backing.fileName = iso_path

        datastore = iso_path.partition('[')[-1].rpartition(']')[0]
        datastore_ref = _get_mor_by_property(vim.Datastore, datastore)
        if datastore_ref:
            drive.backing.datastore = datastore_ref

        drive.deviceInfo.summary = 'ISO {0}'.format(iso_path)

    elif device_type == "client_device":
        if mode == 'passthrough':
            drive.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            drive.deviceInfo.summary = 'Remote Device'
        elif mode == 'atapi':
            drive.backing = vim.vm.device.VirtualCdrom.RemoteAtapiBackingInfo()
            drive.deviceInfo.summary = 'Remote ATAPI'

    return drive


def _edit_existing_cd_or_dvd_drive_helper(drive, device_type, mode, iso_path):
    device_type.strip().lower()
    mode.strip().lower()

    drive_spec = vim.vm.device.VirtualDeviceSpec()
    drive_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    drive_spec.device = _set_cd_or_dvd_backing_type(drive, device_type, mode, iso_path)

    return drive_spec


def _add_new_cd_or_dvd_drive_helper(drive_label, controller_key, device_type, mode, iso_path):
    random_key = randint(-3025, -3000)

    device_type.strip().lower()
    mode.strip().lower()

    drive_spec = vim.vm.device.VirtualDeviceSpec()
    drive_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    drive_spec.device = vim.vm.device.VirtualCdrom()
    drive_spec.device.deviceInfo = vim.Description()

    if device_type in ['datastore_iso_file', 'client_device']:
        drive_spec.device = _set_cd_or_dvd_backing_type(drive_spec.device, device_type, mode, iso_path)
    else:
        # If device_type not specified or does not match, create drive of Client type with Passthough mode
        if not device_type:
            log.debug("The 'device_type' of '{0}' has not been specified. Creating of default type 'client_device'".format(drive_label))
        else:
            log.error("Cannot create CD/DVD drive of type '{0}'. Creating '{1}' of default type 'client_device'".format(device_type, drive_label))
        drive_spec.device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
        drive_spec.device.deviceInfo.summary = 'Remote Device'

    drive_spec.device.key = random_key
    drive_spec.device.deviceInfo.label = drive_label
    drive_spec.device.controllerKey = controller_key
    drive_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
    drive_spec.device.connectable.startConnected = True
    drive_spec.device.connectable.allowGuestControl = True

    return drive_spec


def _set_network_adapter_mapping_helper(adapter_specs):
    adapter_mapping = vim.vm.customization.AdapterMapping()
    adapter_mapping.adapter = vim.vm.customization.IPSettings()

    if 'domain' in list(adapter_specs.keys()):
        domain = adapter_specs['domain']
        adapter_mapping.adapter.dnsDomain = domain
    if 'gateway' in list(adapter_specs.keys()):
        gateway = adapter_specs['gateway']
        adapter_mapping.adapter.gateway = gateway
    if 'ip' in list(adapter_specs.keys()):
        ip = str(adapter_specs['ip'])
        subnet_mask = str(adapter_specs['subnet_mask'])
        adapter_mapping.adapter.ip = vim.vm.customization.FixedIp(ipAddress=ip)
        adapter_mapping.adapter.subnetMask = subnet_mask
    else:
        adapter_mapping.adapter.ip = vim.vm.customization.DhcpIpGenerator()

    return adapter_mapping


def _manage_devices(devices, vm):
    unit_number = 0
    bus_number = 0
    device_specs = []
    existing_disks_label = []
    existing_scsi_adapters_label = []
    existing_network_adapters_label = []
    existing_cd_drives_label = []
    ide_controllers = {}
    nics_map = []

    # loop through all the devices the vm/template has
    # check if the device needs to be created or configured
    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualDisk):
            # this is a hard disk
            if 'disk' in list(devices.keys()):
                # there is atleast one disk specified to be created/configured
                unit_number += 1
                existing_disks_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in list(devices['disk'].keys()):
                    size_gb = float(devices['disk'][device.deviceInfo.label]['size'])
                    size_kb = int(size_gb * 1024.0 * 1024.0)
                    if device.capacityInKB < size_kb:
                        # expand the disk
                        disk_spec = _edit_existing_hard_disk_helper(device, size_kb)
                        device_specs.append(disk_spec)

        elif isinstance(device.backing, vim.vm.device.VirtualEthernetCard.NetworkBackingInfo) or isinstance(device.backing, vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo):
            # this is a network adapter
            if 'network' in list(devices.keys()):
                # there is atleast one network adapter specified to be created/configured
                existing_network_adapters_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in list(devices['network'].keys()):
                    network_name = devices['network'][device.deviceInfo.label]['name']
                    adapter_type = devices['network'][device.deviceInfo.label]['adapter_type'] if 'adapter_type' in devices['network'][device.deviceInfo.label] else ''
                    switch_type = devices['network'][device.deviceInfo.label]['switch_type'] if 'switch_type' in devices['network'][device.deviceInfo.label] else ''
                    network_spec = _edit_existing_network_adapter_helper(device, network_name, adapter_type, switch_type)
                    adapter_mapping = _set_network_adapter_mapping_helper(devices['network'][device.deviceInfo.label])
                    device_specs.append(network_spec)
                    nics_map.append(adapter_mapping)

        elif hasattr(device, 'scsiCtlrUnitNumber'):
            # this is a scsi adapter
            if 'scsi' in list(devices.keys()):
                # there is atleast one scsi adapter specified to be created/configured
                bus_number += 1
                existing_scsi_adapters_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in list(devices['scsi'].keys()):
                    # Modify the existing SCSI adapter
                    scsi_adapter_properties = devices['scsi'][device.deviceInfo.label]
                    bus_sharing = scsi_adapter_properties['bus_sharing'].strip().lower() if 'bus_sharing' in scsi_adapter_properties else None
                    if bus_sharing and bus_sharing in ['virtual', 'physical', 'no']:
                        bus_sharing = '{0}Sharing'.format(bus_sharing)
                        if bus_sharing != device.sharedBus:
                            # Only edit the SCSI adapter if bus_sharing is different
                            scsi_spec = _edit_existing_scsi_adapter_helper(device, bus_sharing)
                            device_specs.append(scsi_spec)

        elif isinstance(device, vim.vm.device.VirtualCdrom):
            # this is a cd/dvd drive
            if 'cd' in list(devices.keys()):
                # there is atleast one cd/dvd drive specified to be created/configured
                existing_cd_drives_label.append(device.deviceInfo.label)
                if device.deviceInfo.label in list(devices['cd'].keys()):
                    device_type = devices['cd'][device.deviceInfo.label]['device_type'] if 'device_type' in devices['cd'][device.deviceInfo.label] else ''
                    mode = devices['cd'][device.deviceInfo.label]['mode'] if 'mode' in devices['cd'][device.deviceInfo.label] else ''
                    iso_path = devices['cd'][device.deviceInfo.label]['iso_path'] if 'iso_path' in devices['cd'][device.deviceInfo.label] else ''
                    cd_drive_spec = _edit_existing_cd_or_dvd_drive_helper(device, device_type, mode, iso_path)
                    device_specs.append(cd_drive_spec)

        elif isinstance(device, vim.vm.device.VirtualIDEController):
            # this is a controller to add new cd drives to
            ide_controllers[device.key] = len(device.device)

    if 'disk' in list(devices.keys()):
        disks_to_create = list(set(devices['disk'].keys()) - set(existing_disks_label))
        disks_to_create.sort()
        log.debug("Hard disks to create: {0}".format(disks_to_create))
        for disk_label in disks_to_create:
            # create the disk
            size_gb = float(devices['disk'][disk_label]['size'])
            disk_spec = _add_new_hard_disk_helper(disk_label, size_gb, unit_number)
            device_specs.append(disk_spec)
            unit_number += 1

    if 'network' in list(devices.keys()):
        network_adapters_to_create = list(set(devices['network'].keys()) - set(existing_network_adapters_label))
        network_adapters_to_create.sort()
        log.debug("Networks adapters to create: {0}".format(network_adapters_to_create))
        for network_adapter_label in network_adapters_to_create:
            network_name = devices['network'][network_adapter_label]['name']
            adapter_type = devices['network'][network_adapter_label]['adapter_type'] if 'adapter_type' in devices['network'][network_adapter_label] else ''
            switch_type = devices['network'][network_adapter_label]['switch_type'] if 'switch_type' in devices['network'][network_adapter_label] else ''
            # create the network adapter
            network_spec = _add_new_network_adapter_helper(network_adapter_label, network_name, adapter_type, switch_type)
            adapter_mapping = _set_network_adapter_mapping_helper(devices['network'][network_adapter_label])
            device_specs.append(network_spec)
            nics_map.append(adapter_mapping)

    if 'scsi' in list(devices.keys()):
        scsi_adapters_to_create = list(set(devices['scsi'].keys()) - set(existing_scsi_adapters_label))
        scsi_adapters_to_create.sort()
        log.debug("SCSI devices to create: {0}".format(scsi_adapters_to_create))
        for scsi_adapter_label in scsi_adapters_to_create:
            # create the scsi adapter
            scsi_adapter_properties = devices['scsi'][scsi_adapter_label]
            scsi_spec = _add_new_scsi_adapter_helper(scsi_adapter_label, scsi_adapter_properties, bus_number)
            device_specs.append(scsi_spec)
            bus_number += 1

    if 'cd' in list(devices.keys()):
        cd_drives_to_create = list(set(devices['cd'].keys()) - set(existing_cd_drives_label))
        cd_drives_to_create.sort()
        log.debug("CD/DVD drives to create: {0}".format(cd_drives_to_create))
        for cd_drive_label in cd_drives_to_create:
            # create the CD/DVD drive
            device_type = devices['cd'][cd_drive_label]['device_type'] if 'device_type' in devices['cd'][cd_drive_label] else ''
            mode = devices['cd'][cd_drive_label]['mode'] if 'mode' in devices['cd'][cd_drive_label] else ''
            iso_path = devices['cd'][cd_drive_label]['iso_path'] if 'iso_path' in devices['cd'][cd_drive_label] else ''
            for ide_controller_key, num_devices in six.iteritems(ide_controllers):
                if num_devices < 2:
                    controller_key = ide_controller_key
                    break
                else:
                    controller_key = None
            if not controller_key:
                log.error("No more available controllers for '{0}'. All IDE controllers are currently in use".format(cd_drive_label))
            else:
                cd_drive_spec = _add_new_cd_or_dvd_drive_helper(cd_drive_label, controller_key, device_type, mode, iso_path)
                device_specs.append(cd_drive_spec)
                ide_controllers[controller_key] += 1

    ret = {
        'device_specs': device_specs,
        'nics_map': nics_map
    }

    return ret


def _wait_for_vmware_tools(vm_ref, max_wait_minute):
    time_counter = 0
    starttime = time.time()
    max_wait_second = int(max_wait_minute * 60)
    while time_counter < max_wait_second:
        if time_counter % 5 == 0:
            log.info("[ {0} ] Waiting for VMware tools to be running [{1} s]".format(vm_ref.name, time_counter))
        if str(vm_ref.summary.guest.toolsRunningStatus) == "guestToolsRunning":
            log.info("[ {0} ] Succesfully got VMware tools running on the guest in {1} seconds".format(vm_ref.name, time_counter))
            return True

        time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        time_counter += 1
    log.warning("[ {0} ] Timeout Reached. VMware tools still not running after waiting for {1} minutes".format(vm_ref.name, max_wait_minute))
    return False


def _wait_for_ip(vm_ref, max_wait_minute):
    max_wait_minute_vmware_tools = max_wait_minute - 5
    max_wait_minute_ip = max_wait_minute - max_wait_minute_vmware_tools
    vmware_tools_status = _wait_for_vmware_tools(vm_ref, max_wait_minute_vmware_tools)
    if not vmware_tools_status:
        return False

    time_counter = 0
    starttime = time.time()
    max_wait_second = int(max_wait_minute_ip * 60)
    while time_counter < max_wait_second:
        if time_counter % 5 == 0:
            log.info("[ {0} ] Waiting to retrieve IPv4 information [{1} s]".format(vm_ref.name, time_counter))

        if vm_ref.summary.guest.ipAddress:
            if match(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', vm_ref.summary.guest.ipAddress) and vm_ref.summary.guest.ipAddress != '127.0.0.1':
                log.info("[ {0} ] Successfully retrieved IPv4 information in {1} seconds".format(vm_ref.name, time_counter))
                return vm_ref.summary.guest.ipAddress

        for net in vm_ref.guest.net:
            if net.ipConfig.ipAddress:
                for current_ip in net.ipConfig.ipAddress:
                    if match(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', current_ip.ipAddress) and current_ip.ipAddress != '127.0.0.1':
                        log.info("[ {0} ] Successfully retrieved IPv4 information in {1} seconds".format(vm_ref.name, time_counter))
                        return current_ip.ipAddress
        time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        time_counter += 1
    log.warning("[ {0} ] Timeout Reached. Unable to retrieve IPv4 information after waiting for {1} minutes".format(vm_ref.name, max_wait_minute_ip))
    return False


def _wait_for_task(task, vm_name, task_type, sleep_seconds=1, log_level='debug'):
    time_counter = 0
    starttime = time.time()
    while task.info.state == 'running':
        if time_counter % sleep_seconds == 0:
            message = "[ {0} ] Waiting for {1} task to finish [{2} s]".format(vm_name, task_type, time_counter)
            if log_level == 'info':
                log.info(message)
            else:
                log.debug(message)
        time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        time_counter += 1
    if task.info.state == 'success':
        message = "[ {0} ] Successfully completed {1} task in {2} seconds".format(vm_name, task_type, time_counter)
        if log_level == 'info':
            log.info(message)
        else:
            log.debug(message)
    else:
        raise Exception(task.info.error)


def _wait_for_host(host_ref, task_type, sleep_seconds=5, log_level='debug'):
    time_counter = 0
    starttime = time.time()
    while host_ref.runtime.connectionState != 'notResponding':
        if time_counter % sleep_seconds == 0:
            message = "[ {0} ] Waiting for host {1} to finish [{2} s]".format(host_ref.name, task_type, time_counter)
            if log_level == 'info':
                log.info(message)
            else:
                log.debug(message)
        time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        time_counter += 1
    while host_ref.runtime.connectionState != 'connected':
        if time_counter % sleep_seconds == 0:
            message = "[ {0} ] Waiting for host {1} to finish [{2} s]".format(host_ref.name, task_type, time_counter)
            if log_level == 'info':
                log.info(message)
            else:
                log.debug(message)
        time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        time_counter += 1
    if host_ref.runtime.connectionState == 'connected':
        message = "[ {0} ] Successfully completed host {1} in {2} seconds".format(host_ref.name, task_type, time_counter)
        if log_level == 'info':
            log.info(message)
        else:
            log.debug(message)
    else:
        log.error('Could not connect back to the host system')


def _format_instance_info_select(vm, selection):
    vm_select_info = {}

    if 'id' in selection:
        vm_select_info['id'] = vm["name"]

    if 'image' in selection:
        vm_select_info['image'] = "{0} (Detected)".format(vm["config.guestFullName"]) if "config.guestFullName" in vm else "N/A"

    if 'size' in selection:
        cpu = vm["config.hardware.numCPU"] if "config.hardware.numCPU" in vm else "N/A"
        ram = "{0} MB".format(vm["config.hardware.memoryMB"]) if "config.hardware.memoryMB" in vm else "N/A"
        vm_select_info['size'] = u"cpu: {0}\nram: {1}".format(cpu, ram)

    if 'state' in selection:
        vm_select_info['state'] = str(vm["summary.runtime.powerState"]) if "summary.runtime.powerState" in vm else "N/A"

    if 'guest_id' in selection:
        vm_select_info['guest_id'] = vm["config.guestId"] if "config.guestId" in vm else "N/A"

    if 'hostname' in selection:
        vm_select_info['hostname'] = vm["object"].guest.hostName

    if 'path' in selection:
        vm_select_info['path'] = vm["config.files.vmPathName"] if "config.files.vmPathName" in vm else "N/A"

    if 'tools_status' in selection:
        vm_select_info['tools_status'] = str(vm["guest.toolsStatus"]) if "guest.toolsStatus" in vm else "N/A"

    if ('private_ips' or 'mac_address' or 'networks') in selection:
        network_full_info = {}
        ip_addresses = []
        mac_addresses = []

        if "guest.net" in vm:
            for net in vm["guest.net"]:
                network_full_info[net.network] = {
                    'connected': net.connected,
                    'ip_addresses': net.ipAddress,
                    'mac_address': net.macAddress
                }
                ip_addresses.extend(net.ipAddress)
                mac_addresses.append(net.macAddress)

        if 'private_ips' in selection:
            vm_select_info['private_ips'] = ip_addresses

        if 'mac_address' in selection:
            vm_select_info['mac_address'] = mac_addresses

        if 'networks' in selection:
            vm_select_info['networks'] = network_full_info

    if 'devices' in selection:
        device_full_info = {}
        if "config.hardware.device" in vm:
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
                    device_full_info[device.deviceInfo.label]['fileName'] = device.backing.fileName

        vm_select_info['devices'] = device_full_info

    if 'storage' in selection:
        storage_full_info = {
            'committed': int(vm["summary.storage.committed"]) if "summary.storage.committed" in vm else "N/A",
            'uncommitted': int(vm["summary.storage.uncommitted"]) if "summary.storage.uncommitted" in vm else "N/A",
            'unshared': int(vm["summary.storage.unshared"]) if "summary.storage.unshared" in vm else "N/A"
        }
        vm_select_info['storage'] = storage_full_info

    if 'files' in selection:
        file_full_info = {}
        if "layoutEx.file" in file:
            for file in vm["layoutEx.file"]:
                file_full_info[file.key] = {
                    'key': file.key,
                    'name': file.name,
                    'size': file.size,
                    'type': file.type
                }
        vm_select_info['files'] = file_full_info

    return vm_select_info


def _format_instance_info(vm):
    device_full_info = {}

    if "config.hardware.device" in vm:
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
                device_full_info[device.deviceInfo.label]['fileName'] = device.backing.fileName

    storage_full_info = {
        'committed': int(vm["summary.storage.committed"]) if "summary.storage.committed" in vm else "N/A",
        'uncommitted': int(vm["summary.storage.uncommitted"]) if "summary.storage.uncommitted" in vm else "N/A",
        'unshared': int(vm["summary.storage.unshared"]) if "summary.storage.unshared" in vm else "N/A"
    }

    file_full_info = {}
    if "layoutEx.file" in vm:
        for file in vm["layoutEx.file"]:
            file_full_info[file.key] = {
                'key': file.key,
                'name': file.name,
                'size': file.size,
                'type': file.type
            }

    network_full_info = {}
    ip_addresses = []
    mac_addresses = []
    if "guest.net" in vm:
        for net in vm["guest.net"]:
            network_full_info[net.network] = {
                'connected': net.connected,
                'ip_addresses': net.ipAddress,
                'mac_address': net.macAddress
            }
            ip_addresses.extend(net.ipAddress)
            mac_addresses.append(net.macAddress)

    cpu = vm["config.hardware.numCPU"] if "config.hardware.numCPU" in vm else "N/A"
    ram = "{0} MB".format(vm["config.hardware.memoryMB"]) if "config.hardware.memoryMB" in vm else "N/A"
    vm_full_info = {
        'id': str(vm['name']),
        'image': "{0} (Detected)".format(vm["config.guestFullName"]) if "config.guestFullName" in vm else "N/A",
        'size': u"cpu: {0}\nram: {1}".format(cpu, ram),
        'state': str(vm["summary.runtime.powerState"]) if "summary.runtime.powerState" in vm else "N/A",
        'private_ips': ip_addresses,
        'public_ips': [],
        'devices': device_full_info,
        'storage': storage_full_info,
        'files': file_full_info,
        'guest_id': str(vm["config.guestId"]) if "config.guestId" in vm else "N/A",
        'hostname': str(vm["object"].guest.hostName),
        'mac_address': mac_addresses,
        'networks': network_full_info,
        'path': str(vm["config.files.vmPathName"]) if "config.files.vmPathName" in vm else "N/A",
        'tools_status': str(vm["guest.toolsStatus"]) if "guest.toolsStatus" in vm else "N/A"
    }

    return vm_full_info


def _get_snapshots(snapshot_list, current_snapshot=None, parent_snapshot_path=""):
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

        if current_snapshot and current_snapshot == snapshot.snapshot:
            return snapshots[snapshot_path]

        # Check if child snapshots exist
        if snapshot.childSnapshotList:
            ret = _get_snapshots(snapshot.childSnapshotList, current_snapshot, snapshot_path)
            if current_snapshot:
                return ret
            snapshots.update(ret)

    return snapshots


def _upg_tools_helper(vm, reboot=False):
    # Exit if template
    if vm.config.template:
        status = 'VMware tools cannot be updated on a template'
        return status

    # Exit if VMware tools is already up to date
    if vm.guest.toolsStatus == "toolsOk":
        status = 'VMware tools is already up to date'
        return status

    # Exit if VM is not powered on
    if vm.summary.runtime.powerState != "poweredOn":
        status = 'VM must be powered on to upgrade tools'
        return status

    # Exit if VMware tools is either not running or not installed
    if vm.guest.toolsStatus in ["toolsNotRunning", "toolsNotInstalled"]:
        status = 'VMware tools is either not running or not installed'
        return status

    # If vmware tools is out of date, check major OS family
    # Upgrade tools on Linux and Windows guests
    if vm.guest.toolsStatus == "toolsOld":
        log.info('Upgrading VMware tools on {0}'.format(vm.name))
        try:
            if vm.guest.guestFamily == "windowsGuest" and not reboot:
                log.info('Reboot suppressed on {0}'.format(vm.name))
                task = vm.UpgradeTools('/S /v"/qn REBOOT=R"')
            elif vm.guest.guestFamily in ["linuxGuest", "windowsGuest"]:
                task = vm.UpgradeTools()
            else:
                status = 'Only Linux and Windows guests are currently supported'
                return status
            _wait_for_task(task, vm.name, "tools upgrade", 5, "info")
        except Exception as exc:
            log.error(
                'Error while upgrading VMware tools on VM {0}: {1}'.format(
                    vm.name,
                    exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            status = 'VMware tools upgrade failed'
            return status
        status = 'VMware tools upgrade succeeded'
        return status

    return 'VMware tools could not be upgraded'


def _get_hba_type(hba_type):
    if hba_type == "parallel":
        return vim.host.ParallelScsiHba
    elif hba_type == "block":
        return vim.host.BlockHba
    elif hba_type == "iscsi":
        return vim.host.InternetScsiHba
    elif hba_type == "fibre":
        return vim.host.FibreChannelHba


def test_vcenter_connection(kwargs=None, call=None):
    '''
    Test if the connection can be made to the vCenter server using
    the specified credentials inside ``/etc/salt/cloud.providers``
    or ``/etc/salt/cloud.providers.d/vmware.conf``

    CLI Example:

    .. code-block:: bash

        salt-cloud -f test_vcenter_connection my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The test_vcenter_connection function must be called with '
            '-f or --function.'
        )

    try:
        # Get the service instance object
        si = _get_si()
    except Exception as exc:
        return 'failed to connect: {0}'.format(exc)

    return 'connection successful'


def get_vcenter_version(kwargs=None, call=None):
    '''
    Show the vCenter Server version with build number.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_vcenter_version my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_vcenter_version function must be called with '
            '-f or --function.'
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
        raise SaltCloudSystemExit(
            'The list_datacenters function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_clusters function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_datastore_clusters function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_datastores function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_hosts function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_resourcepools function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_networks function must be called with '
            '-f or --function.'
        )

    networks = []
    network_properties = ["name"]

    network_list = _get_mors_with_properties(vim.Network, network_properties)

    for network in network_list:
        networks.append(network["name"])

    return {'Networks': networks}


def list_nodes_min(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the specified provider, with no details

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-vmware-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called '
            'with -f or --function.'
        )

    ret = {}
    vm_properties = ["name"]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        ret[vm["name"]] = True

    return ret


def list_nodes(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the specified provider, with basic fields

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes my-vmware-config

    To return a list of all VMs and templates present on ALL configured providers, with basic
    fields:

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called '
            'with -f or --function.'
        )

    ret = {}
    vm_properties = [
        "name",
        "guest.ipAddress",
        "config.guestFullName",
        "config.hardware.numCPU",
        "config.hardware.memoryMB",
        "summary.runtime.powerState"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        cpu = vm["config.hardware.numCPU"] if "config.hardware.numCPU" in vm else "N/A"
        ram = "{0} MB".format(vm["config.hardware.memoryMB"]) if "config.hardware.memoryMB" in vm else "N/A"
        vm_info = {
            'id': vm["name"],
            'image': "{0} (Detected)".format(vm["config.guestFullName"]) if "config.guestFullName" in vm else "N/A",
            'size': u"cpu: {0}\nram: {1}".format(cpu, ram),
            'state': str(vm["summary.runtime.powerState"]) if "summary.runtime.powerState" in vm else "N/A",
            'private_ips': [vm["guest.ipAddress"]] if "guest.ipAddress" in vm else [],
            'public_ips': []
        }
        ret[vm_info['id']] = vm_info

    return ret


def list_nodes_full(kwargs=None, call=None):
    '''
    Return a list of all VMs and templates that are on the specified provider, with full details

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_full my-vmware-config

    To return a list of all VMs and templates present on ALL configured providers, with full
    details:

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called '
            'with -f or --function.'
        )

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
        ret[vm["name"]] = _format_instance_info(vm)

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of all VMs and templates that are on the specified provider, with fields
    specified under ``query.selection`` in ``/etc/salt/cloud``

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_select my-vmware-config

    To return a list of all VMs and templates present on ALL configured providers, with
    fields specified under ``query.selection`` in ``/etc/salt/cloud``:

    CLI Example:

    .. code-block:: bash

        salt-cloud -S
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_select function must be called '
            'with -f or --function.'
        )

    ret = {}
    vm_properties = []
    selection = __opts__.get('query.selection')

    if not selection:
        raise SaltCloudSystemExit(
            'query.selection not found in /etc/salt/cloud'
        )

    if 'id' in selection:
        vm_properties.append("name")

    if 'image' in selection:
        vm_properties.append("config.guestFullName")

    if 'size' in selection:
        vm_properties.extend(["config.hardware.numCPU", "config.hardware.memoryMB"])

    if 'state' in selection:
        vm_properties.append("summary.runtime.powerState")

    if ('private_ips' or 'mac_address' or 'networks') in selection:
        vm_properties.append("guest.net")

    if 'devices' in selection:
        vm_properties.append("config.hardware.device")

    if 'storage' in selection:
        vm_properties.extend([
            "config.hardware.device",
            "summary.storage.committed",
            "summary.storage.uncommitted",
            "summary.storage.unshared"
        ])

    if 'files' in selection:
        vm_properties.append("layoutEx.file")

    if 'guest_id' in selection:
        vm_properties.append("config.guestId")

    if 'hostname' in selection:
        vm_properties.append("guest.hostName")

    if 'path' in selection:
        vm_properties.append("config.files.vmPathName")

    if 'tools_status' in selection:
        vm_properties.append("guest.toolsStatus")

    if not vm_properties:
        return {}
    elif 'name' not in vm_properties:
        vm_properties.append("name")

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        ret[vm["name"]] = _format_instance_info_select(vm, selection)
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
            'The show_instance action must be called with '
            '-a or --action.'
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
            return _format_instance_info(vm)


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
        raise SaltCloudSystemExit(
            'The list_folders function must be called with '
            '-f or --function.'
        )

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
        raise SaltCloudSystemExit(
            'The list_snapshots function must be called with '
            '-f or --function.'
        )

    ret = {}
    vm_properties = [
        "name",
        "rootSnapshot",
        "snapshot"
    ]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        if vm["rootSnapshot"]:
            if kwargs and kwargs.get('name') == vm["name"]:
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
            'The start action must be called with '
            '-a or --action.'
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
                task = vm["object"].PowerOn()
                _wait_for_task(task, name, "power on")
            except Exception as exc:
                log.error(
                    'Error while powering on VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
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
            'The stop action must be called with '
            '-a or --action.'
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
                task = vm["object"].PowerOff()
                _wait_for_task(task, name, "power off")
            except Exception as exc:
                log.error(
                    'Error while powering off VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
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
            'The suspend action must be called with '
            '-a or --action.'
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
                task = vm["object"].Suspend()
                _wait_for_task(task, name, "suspend")
            except Exception as exc:
                log.error(
                    'Error while suspending VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
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
            'The reset action must be called with '
            '-a or --action.'
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
                task = vm["object"].Reset()
                _wait_for_task(task, name, "reset")
            except Exception as exc:
                log.error(
                    'Error while resetting VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                return 'failed to reset'

    return 'reset'


def terminate(name, call=None):
    '''
    To do an immediate power off of a VM using its name. A ``SIGKILL``
    is issued to the vmx process of the VM

    CLI Example:

    .. code-block:: bash

        salt-cloud -a terminate vmname
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The terminate action must be called with '
            '-a or --action.'
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
                log.info('Terminating VM {0}'.format(name))
                vm["object"].Terminate()
            except Exception as exc:
                log.error(
                    'Error while terminating VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                return 'failed to terminate'

    return 'terminated'


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
                    _wait_for_task(task, name, "power off")
                except Exception as exc:
                    log.error(
                        'Error while powering off VM {0}: {1}'.format(
                            name,
                            exc
                        ),
                        # Show the traceback if the debug logging level is enabled
                        exc_info_on_loglevel=logging.DEBUG
                    )
                    return 'failed to destroy'
            try:
                log.info('Destroying VM {0}'.format(name))
                task = vm["object"].Destroy_Task()
                _wait_for_task(task, name, "destroy")
            except Exception as exc:
                log.error(
                    'Error while destroying VM {0}: {1}'.format(
                        name,
                        exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                return 'failed to destroy'

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
        'num_cpus', vm_, __opts__, default=None
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
        'power_on', vm_, __opts__, default=True
    )
    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    deploy = config.get_cloud_config_value(
        'deploy', vm_, __opts__, search_global=False, default=True
    )
    domain = config.get_cloud_config_value(
        'domain', vm_, __opts__, search_global=False, default='local'
    )

    if 'clonefrom' in vm_:
        # Clone VM/template from specified VM/template
        object_ref = _get_mor_by_property(vim.VirtualMachine, vm_['clonefrom'])
        if object_ref:
            clone_type = "template" if object_ref.config.template else "vm"
        else:
            raise SaltCloudSystemExit(
                'The VM/template that you have specified under clonefrom does not exist.'
            )

        # Either a cluster, or a resource pool must be specified when cloning from template.
        if resourcepool:
            resourcepool_ref = _get_mor_by_property(vim.ResourcePool, resourcepool)
            if not resourcepool_ref:
                log.error("Specified resource pool: '{0}' does not exist".format(resourcepool))
                if clone_type == "template":
                    raise SaltCloudSystemExit('You must specify a resource pool that exists.')
        elif cluster:
            cluster_ref = _get_mor_by_property(vim.ClusterComputeResource, cluster)
            if not cluster_ref:
                log.error("Specified cluster: '{0}' does not exist".format(cluster))
                if clone_type == "template":
                    raise SaltCloudSystemExit('You must specify a cluster that exists.')
            else:
                resourcepool_ref = cluster_ref.resourcePool
        elif clone_type == "template":
            raise SaltCloudSystemExit(
                'You must either specify a cluster or a resource pool when cloning from a template.'
            )
        else:
            log.debug("Using resource pool used by the {0} {1}".format(clone_type, vm_['clonefrom']))

        # Either a datacenter or a folder can be optionally specified
        # If not specified, the existing VM/template\'s parent folder is used.
        if folder:
            folder_ref = _get_mor_by_property(vim.Folder, folder)
            if not folder_ref:
                log.error("Specified folder: '{0}' does not exist".format(folder))
                log.debug("Using folder in which {0} {1} is present".format(clone_type, vm_['clonefrom']))
                folder_ref = object_ref.parent
        elif datacenter:
            datacenter_ref = _get_mor_by_property(vim.Datacenter, datacenter)
            if not datacenter_ref:
                log.error("Specified datacenter: '{0}' does not exist".format(datacenter))
                log.debug("Using datacenter folder in which {0} {1} is present".format(clone_type, vm_['clonefrom']))
                folder_ref = object_ref.parent
            else:
                folder_ref = datacenter_ref.vmFolder
        else:
            log.debug("Using folder in which {0} {1} is present".format(clone_type, vm_['clonefrom']))
            folder_ref = object_ref.parent

        # Create the relocation specs
        reloc_spec = vim.vm.RelocateSpec()

        if (resourcepool and resourcepool_ref) or (cluster and cluster_ref):
            reloc_spec.pool = resourcepool_ref

        # Either a datastore/datastore cluster can be optionally specified.
        # If not specified, the current datastore is used.
        if datastore:
            datastore_ref = _get_mor_by_property(vim.Datastore, datastore)
            if datastore_ref:
                # specific datastore has been specified
                reloc_spec.datastore = datastore_ref
            else:
                datastore_cluster_ref = _get_mor_by_property(vim.StoragePod, datastore)
                if not datastore_cluster_ref:
                    log.error("Specified datastore/datastore cluster: '{0}' does not exist".format(datastore))
                    log.debug("Using datastore used by the {0} {1}".format(clone_type, vm_['clonefrom']))
        else:
            log.debug("No datastore/datastore cluster specified")
            log.debug("Using datastore used by the {0} {1}".format(clone_type, vm_['clonefrom']))

        if host:
            host_ref = _get_mor_by_property(vim.HostSystem, host)
            if host_ref:
                reloc_spec.host = host_ref
            else:
                log.error("Specified host: '{0}' does not exist".format(host))

        # Create the config specs
        config_spec = vim.vm.ConfigSpec()

        if num_cpus:
            log.debug("Setting cpu to: {0}".format(num_cpus))
            config_spec.numCPUs = int(num_cpus)

        if memory:
            try:
                memory_num, memory_unit = findall(r"[^\W\d_]+|\d+.\d+|\d+", memory)
                if memory_unit.lower() == "mb":
                    memory_mb = int(memory_num)
                elif memory_unit.lower() == "gb":
                    memory_mb = int(float(memory_num)*1024.0)
                else:
                    err_msg = "Invalid memory type specified: '{0}'".format(memory_unit)
                    log.error(err_msg)
                    return {'Error': err_msg}
            except (TypeError, ValueError):
                memory_mb = int(memory)
            log.debug("Setting memory to: {0} MB".format(memory_mb))
            config_spec.memoryMB = memory_mb

        if devices:
            specs = _manage_devices(devices, object_ref)
            config_spec.deviceChange = specs['device_specs']

        if extra_config:
            for key, value in six.iteritems(extra_config):
                option = vim.option.OptionValue(key=key, value=value)
                config_spec.extraConfig.append(option)

        # Create the clone specs
        clone_spec = vim.vm.CloneSpec(
            template=template,
            location=reloc_spec,
            config=config_spec
        )

        if devices and 'network' in list(devices.keys()):
            if "Windows" not in object_ref.config.guestFullName:
                global_ip = vim.vm.customization.GlobalIPSettings()
                if 'dns_servers' in list(vm_.keys()):
                    global_ip.dnsServerList = vm_['dns_servers']

                identity = vim.vm.customization.LinuxPrep()
                hostName = vm_name.split('.')[0]
                domainName = vm_name.split('.', 1)[-1]
                identity.hostName = vim.vm.customization.FixedName(name=hostName)
                identity.domain = domainName if hostName != domainName else domain

                custom_spec = vim.vm.customization.Specification(
                    globalIPSettings=global_ip,
                    identity=identity,
                    nicSettingMap=specs['nics_map']
                )
                clone_spec.customization = custom_spec

        if not template:
            clone_spec.powerOn = power

        log.debug('clone_spec set to:\n{0}'.format(
            pprint.pformat(clone_spec))
        )

        try:
            log.info("Creating {0} from {1}({2})".format(vm_['name'], clone_type, vm_['clonefrom']))
            salt.utils.cloud.fire_event(
                'event',
                'requesting instance',
                'salt/cloud/{0}/requesting'.format(vm_['name']),
                {'kwargs': vm_},
                transport=__opts__['transport']
            )

            if datastore and not datastore_ref and datastore_cluster_ref:
                # datastore cluster has been specified so apply Storage DRS recomendations
                pod_spec = vim.storageDrs.PodSelectionSpec(storagePod=datastore_cluster_ref)

                storage_spec = vim.storageDrs.StoragePlacementSpec(
                    type='clone',
                    vm=object_ref,
                    podSelectionSpec=pod_spec,
                    cloneSpec=clone_spec,
                    cloneName=vm_name,
                    folder=folder_ref
                )

                # get si instance to refer to the content
                si = _get_si()

                # get recommended datastores
                recommended_datastores = si.content.storageResourceManager.RecommendDatastores(storageSpec=storage_spec)

                # apply storage DRS recommendations
                task = si.content.storageResourceManager.ApplyStorageDrsRecommendation_Task(recommended_datastores.recommendations[0].key)
                _wait_for_task(task, vm_name, "apply storage DRS recommendations", 5, 'info')
            else:
                # clone the VM/template
                task = object_ref.Clone(folder_ref, vm_name, clone_spec)
                _wait_for_task(task, vm_name, "clone", 5, 'info')
        except Exception as exc:
            err_msg = 'Error creating {0}: {1}'.format(vm_['name'], exc)
            log.error(
                err_msg,
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return {'Error': err_msg}

        new_vm_ref = _get_mor_by_property(vim.VirtualMachine, vm_name)

        # If it a template or if it does not need to be powered on then do not wait for the IP
        if not template and power:
            ip = _wait_for_ip(new_vm_ref, 20)
            if ip:
                log.info("[ {0} ] IPv4 is: {1}".format(vm_name, ip))
                # ssh or smb using ip and install salt only if deploy is True
                if deploy:
                    vm_['key_filename'] = key_filename
                    vm_['ssh_host'] = ip

                    salt.utils.cloud.bootstrap(vm_, __opts__)

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
        return data

    else:
        err_msg = "clonefrom option hasn\'t been specified. Exiting."
        log.error(err_msg)
        return {'Error': err_msg}


def create_datacenter(kwargs=None, call=None):
    '''
    Create a new data center in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_datacenter my-vmware-config name="MyNewDatacenter"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_datacenter function must be called with '
            '-f or --function.'
        )

    datacenter_name = kwargs.get('name') if kwargs and 'name' in kwargs else None

    if not datacenter_name:
        raise SaltCloudSystemExit(
            'You must specify name of the new datacenter to be created.'
        )

    if len(datacenter_name) >= 80 or len(datacenter_name) <= 0:
        raise SaltCloudSystemExit(
            'The datacenter name must be a non empty string of less than 80 characters.'
        )

    # Check if datacenter already exists
    datacenter_ref = _get_mor_by_property(vim.Datacenter, datacenter_name)
    if datacenter_ref:
        return {datacenter_name: 'datacenter already exists'}

    # Get the service instance
    si = _get_si()

    folder = si.content.rootFolder

    # Verify that the folder is of type vim.Folder
    if isinstance(folder, vim.Folder):
        try:
            folder.CreateDatacenter(name=datacenter_name)
        except Exception as exc:
            log.error(
                'Error creating datacenter {0}: {1}'.format(
                    datacenter_name,
                    exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return False

        log.debug("Created datacenter {0}".format(datacenter_name))
        return {datacenter_name: 'created'}

    return False


def create_cluster(kwargs=None, call=None):
    '''
    Create a new cluster under the specified datacenter in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_cluster my-vmware-config name="myNewCluster" datacenter="datacenterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_cluster function must be called with '
            '-f or --function.'
        )

    cluster_name = kwargs.get('name') if kwargs and 'name' in kwargs else None
    datacenter = kwargs.get('datacenter') if kwargs and 'datacenter' in kwargs else None

    if not cluster_name:
        raise SaltCloudSystemExit(
            'You must specify name of the new cluster to be created.'
        )

    if not datacenter:
        raise SaltCloudSystemExit(
            'You must specify name of the datacenter where the cluster should be created.'
        )

    if not isinstance(datacenter, vim.Datacenter):
        datacenter = _get_mor_by_property(vim.Datacenter, datacenter)
        if not datacenter:
            raise SaltCloudSystemExit(
                'The specified datacenter does not exist.'
            )

    # Check if cluster already exists
    cluster_ref = _get_mor_by_property(vim.ClusterComputeResource, cluster_name)
    if cluster_ref:
        return {cluster_name: 'cluster already exists'}

    cluster_spec = vim.cluster.ConfigSpecEx()
    folder = datacenter.hostFolder

    # Verify that the folder is of type vim.Folder
    if isinstance(folder, vim.Folder):
        try:
            folder.CreateClusterEx(name=cluster_name, spec=cluster_spec)
        except Exception as exc:
            log.error(
                'Error creating cluster {0}: {1}'.format(
                    cluster_name,
                    exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return False

        log.debug("Created cluster {0} under datacenter {1}".format(cluster_name, datacenter.name))
        return {cluster_name: 'created'}

    return False


def rescan_hba(kwargs=None, call=None):
    '''
    To rescan a specified HBA or all the HBAs on the Host System

    CLI Example:

    .. code-block:: bash

        salt-cloud -f rescan_hba my-vmware-config host="hostSystemName"
        salt-cloud -f rescan_hba my-vmware-config hba="hbaDeviceName" host="hostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The rescan_hba function must be called with '
            '-f or --function.'
        )

    hba = kwargs.get('hba') if kwargs and 'hba' in kwargs else None
    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify name of the host system.'
        )

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)

    try:
        if hba:
            log.info('Rescanning HBA {0} on host {1}'.format(hba, host_name))
            host_ref.configManager.storageSystem.RescanHba(hba)
            ret = 'rescanned HBA {0}'.format(hba)
        else:
            log.info('Rescanning all HBAs on host {0}'.format(host_name))
            host_ref.configManager.storageSystem.RescanAllHba()
            ret = 'rescanned all HBAs'
    except Exception as exc:
        log.error(
            'Error while rescaning HBA on host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to rescan HBA'}

    return {host_name: ret}


def upgrade_tools_all(call=None):
    '''
    To upgrade VMware Tools on all virtual machines present in
    the specified provider

    .. note::

        If the virtual machine is running Windows OS, this function
        will attempt to suppress the automatic reboot caused by a
        VMware Tools upgrade.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f upgrade_tools_all my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The upgrade_tools_all function must be called with '
            '-f or --function.'
        )

    ret = {}
    vm_properties = ["name"]

    vm_list = _get_mors_with_properties(vim.VirtualMachine, vm_properties)

    for vm in vm_list:
        ret[vm['name']] = _upg_tools_helper(vm['object'])

    return ret


def upgrade_tools(name, reboot=False, call=None):
    '''
    To upgrade VMware Tools on a specified virtual machine.

    .. note::

        If the virtual machine is running Windows OS, use ``reboot=True``
        to reboot the virtual machine after VMware tools upgrade. Default
        is ``reboot=False``

    CLI Example:

    .. code-block:: bash

        salt-cloud -a upgrade_tools vmname
        salt-cloud -a upgrade_tools vmname reboot=True
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The upgrade_tools action must be called with '
            '-a or --action.'
        )

    vm_ref = _get_mor_by_property(vim.VirtualMachine, name)

    return _upg_tools_helper(vm_ref, reboot)


def list_hosts_by_cluster(kwargs=None, call=None):
    '''
    List hosts for each cluster; or hosts for a specified cluster in
    this VMware environment

    To list hosts for each cluster:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts_by_cluster my-vmware-config

    To list hosts for a specified cluster:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts_by_cluster my-vmware-config cluster="clusterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_hosts_by_cluster function must be called with '
            '-f or --function.'
        )

    ret = {}
    cluster_name = kwargs.get('cluster') if kwargs and 'cluster' in kwargs else None
    cluster_properties = ["name"]

    cluster_list = _get_mors_with_properties(vim.ClusterComputeResource, cluster_properties)

    for cluster in cluster_list:
        ret[cluster['name']] = []
        for host in cluster['object'].host:
            if isinstance(host, vim.HostSystem):
                ret[cluster['name']].append(host.name)
        if cluster_name and cluster_name == cluster['name']:
            return {'Hosts by Cluster': {cluster_name: ret[cluster_name]}}

    return {'Hosts by Cluster': ret}


def list_clusters_by_datacenter(kwargs=None, call=None):
    '''
    List clusters for each datacenter; or clusters for a specified datacenter in
    this VMware environment

    To list clusters for each datacenter:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_clusters_by_datacenter my-vmware-config

    To list clusters for a specified datacenter:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_clusters_by_datacenter my-vmware-config datacenter="datacenterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_clusters_by_datacenter function must be called with '
            '-f or --function.'
        )

    ret = {}
    datacenter_name = kwargs.get('datacenter') if kwargs and 'datacenter' in kwargs else None
    datacenter_properties = ["name"]

    datacenter_list = _get_mors_with_properties(vim.Datacenter, datacenter_properties)

    for datacenter in datacenter_list:
        ret[datacenter['name']] = []
        for cluster in datacenter['object'].hostFolder.childEntity:
            if isinstance(cluster, vim.ClusterComputeResource):
                ret[datacenter['name']].append(cluster.name)
        if datacenter_name and datacenter_name == datacenter['name']:
            return {'Clusters by Datacenter': {datacenter_name: ret[datacenter_name]}}

    return {'Clusters by Datacenter': ret}


def list_hosts_by_datacenter(kwargs=None, call=None):
    '''
    List hosts for each datacenter; or hosts for a specified datacenter in
    this VMware environment

    To list hosts for each datacenter:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts_by_datacenter my-vmware-config

    To list hosts for a specified datacenter:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hosts_by_datacenter my-vmware-config datacenter="datacenterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_hosts_by_datacenter function must be called with '
            '-f or --function.'
        )

    ret = {}
    datacenter_name = kwargs.get('datacenter') if kwargs and 'datacenter' in kwargs else None
    datacenter_properties = ["name"]

    datacenter_list = _get_mors_with_properties(vim.Datacenter, datacenter_properties)

    for datacenter in datacenter_list:
        ret[datacenter['name']] = []
        for cluster in datacenter['object'].hostFolder.childEntity:
            if isinstance(cluster, vim.ClusterComputeResource):
                for host in cluster.host:
                    if isinstance(host, vim.HostSystem):
                        ret[datacenter['name']].append(host.name)
        if datacenter_name and datacenter_name == datacenter['name']:
            return {'Hosts by Datacenter': {datacenter_name: ret[datacenter_name]}}

    return {'Hosts by Datacenter': ret}


def list_hbas(kwargs=None, call=None):
    '''
    List all HBAs for each host system; or all HBAs for a specified host
    system; or HBAs of specified type for each host system; or HBAs of
    specified type for a specified host system in this VMware environment

    .. note::

        You can specify type as either ``parallel``, ``iscsi``, ``block``
        or ``fibre``.

    To list all HBAs for each host system:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hbas my-vmware-config

    To list all HBAs for a specified host system:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hbas my-vmware-config host="hostSystemName"

    To list HBAs of specified type for each host system:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hbas my-vmware-config type="HBAType"

    To list HBAs of specified type for a specified host system:

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_hbas my-vmware-config host="hostSystemName" type="HBAtype"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_hbas function must be called with '
            '-f or --function.'
        )

    ret = {}
    hba_type = kwargs.get('type').lower() if kwargs and 'type' in kwargs else None
    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None
    host_properties = [
        "name",
        "config.storageDevice.hostBusAdapter"
    ]

    if hba_type and hba_type not in ["parallel", "block", "iscsi", "fibre"]:
        raise SaltCloudSystemExit(
            'Specified hba type {0} currently not supported.'.format(hba_type)
        )

    host_list = _get_mors_with_properties(vim.HostSystem, host_properties)

    for host in host_list:
        ret[host['name']] = {}
        for hba in host['config.storageDevice.hostBusAdapter']:
            hba_spec = {
                'driver': hba.driver,
                'status': hba.status,
                'type': type(hba).__name__.rsplit(".", 1)[1]
            }
            if hba_type:
                if isinstance(hba, _get_hba_type(hba_type)):
                    if hba.model in ret[host['name']]:
                        ret[host['name']][hba.model][hba.device] = hba_spec
                    else:
                        ret[host['name']][hba.model] = {hba.device: hba_spec}
            else:
                if hba.model in ret[host['name']]:
                    ret[host['name']][hba.model][hba.device] = hba_spec
                else:
                    ret[host['name']][hba.model] = {hba.device: hba_spec}
        if host['name'] == host_name:
            return {'HBAs by Host': {host_name: ret[host_name]}}

    return {'HBAs by Host': ret}


def list_dvs(kwargs=None, call=None):
    '''
    List all the distributed virtual switches for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_dvs my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_dvs function must be called with '
            '-f or --function.'
        )

    distributed_vswitches = []
    dvs_properties = ["name"]

    dvs_list = _get_mors_with_properties(vim.DistributedVirtualSwitch, dvs_properties)

    for dvs in dvs_list:
        distributed_vswitches.append(dvs["name"])

    return {'Distributed Virtual Switches': distributed_vswitches}


def list_vapps(kwargs=None, call=None):
    '''
    List all the vApps for this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_vapps my-vmware-config
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_vapps function must be called with '
            '-f or --function.'
        )

    vapps = []
    vapp_properties = ["name"]

    vapp_list = _get_mors_with_properties(vim.VirtualApp, vapp_properties)

    for vapp in vapp_list:
        vapps.append(vapp["name"])

    return {'vApps': vapps}


def enter_maintenance_mode(kwargs=None, call=None):
    '''
    To put the specified host system in maintenance mode in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f enter_maintenance_mode my-vmware-config host="myHostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The enter_maintenance_mode function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)

    if not host_name or not host_ref:
        raise SaltCloudSystemExit(
            'You must specify a valid name of the host system.'
        )

    if host_ref.runtime.inMaintenanceMode:
        return {host_name: 'already in maintenance mode'}

    try:
        task = host_ref.EnterMaintenanceMode(timeout=0, evacuatePoweredOffVms=True)
        _wait_for_task(task, host_name, "enter maintenance mode", 1)
    except Exception as exc:
        log.error(
            'Error while moving host system {0} in maintenance mode: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to enter maintenance mode'}

    return {host_name: 'entered maintenance mode'}


def exit_maintenance_mode(kwargs=None, call=None):
    '''
    To take the specified host system out of maintenance mode in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f exit_maintenance_mode my-vmware-config host="myHostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The exit_maintenance_mode function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)

    if not host_name or not host_ref:
        raise SaltCloudSystemExit(
            'You must specify a valid name of the host system.'
        )

    if not host_ref.runtime.inMaintenanceMode:
        return {host_name: 'already not in maintenance mode'}

    try:
        task = host_ref.ExitMaintenanceMode(timeout=0)
        _wait_for_task(task, host_name, "exit maintenance mode", 1)
    except Exception as exc:
        log.error(
            'Error while moving host system {0} out of maintenance mode: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to exit maintenance mode'}

    return {host_name: 'exited maintenance mode'}


def create_folder(kwargs=None, call=None):
    '''
    Create the specified folder path in this VMware environment

    .. note::

        To create a Host and Cluster Folder under a Datacenter, specify
        ``path="/yourDatacenterName/host/yourFolderName"``

        To create a Network Folder under a Datacenter, specify
        ``path="/yourDatacenterName/network/yourFolderName"``

        To create a Storage Folder under a Datacenter, specify
        ``path="/yourDatacenterName/datastore/yourFolderName"``

        To create a VM and Template Folder under a Datacenter, specify
        ``path="/yourDatacenterName/vm/yourFolderName"``

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_folder my-vmware-config path="/Local/a/b/c"
        salt-cloud -f create_folder my-vmware-config path="/MyDatacenter/vm/MyVMFolder"
        salt-cloud -f create_folder my-vmware-config path="/MyDatacenter/host/MyHostFolder"
        salt-cloud -f create_folder my-vmware-config path="/MyDatacenter/network/MyNetworkFolder"
        salt-cloud -f create_folder my-vmware-config path="/MyDatacenter/storage/MyStorageFolder"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_folder function must be called with '
            '-f or --function.'
        )

    # Get the service instance object
    si = _get_si()

    folder_path = kwargs.get('path') if kwargs and 'path' in kwargs else None

    if not folder_path:
        raise SaltCloudSystemExit(
            'You must specify a non empty folder path.'
        )

    folder_refs = []
    inventory_path = '/'
    path_exists = True

    # Split the path in a list and loop over it to check for its existence
    for index, folder_name in enumerate(os.path.normpath(folder_path.strip('/')).split('/')):
        inventory_path = os.path.join(inventory_path, folder_name)
        folder_ref = si.content.searchIndex.FindByInventoryPath(inventoryPath=inventory_path)
        if isinstance(folder_ref, vim.Folder):
            # This is a folder that exists so just append and skip it
            log.debug("Path {0}/ exists in the inventory".format(inventory_path))
            folder_refs.append(folder_ref)
        elif isinstance(folder_ref, vim.Datacenter):
            # This is a datacenter that exists so just append and skip it
            log.debug("Path {0}/ exists in the inventory".format(inventory_path))
            folder_refs.append(folder_ref)
        else:
            path_exists = False
            if not folder_refs:
                # If this is the first folder, create it under the rootFolder
                log.debug("Creating folder {0} under rootFolder in the inventory".format(folder_name))
                folder_refs.append(si.content.rootFolder.CreateFolder(folder_name))
            else:
                # Create the folder under the parent folder
                log.debug("Creating path {0}/ in the inventory".format(inventory_path))
                folder_refs.append(folder_refs[index-1].CreateFolder(folder_name))

    if path_exists:
        return {inventory_path: 'specfied path already exists'}
    else:
        return {inventory_path: 'created the specified path'}


def create_snapshot(name, kwargs=None, call=None):
    '''
    Create a snapshot of the specified virtual machine in this VMware
    environment

    .. note::

        If the VM is powered on, the internal state of the VM (memory
        dump) is included in the snapshot by default which will also set
        the power state of the snapshot to "powered on". You can set
        ``memdump=False`` to override this. This field is ignored if
        the virtual machine is powered off or if the VM does not support
        snapshots with memory dumps. Default is ``memdump=True``

    .. note::

        If the VM is powered on when the snapshot is taken, VMware Tools
        can be used to quiesce the file system in the virtual machine by
        setting ``quiesce=True``. This field is ignored if the virtual
        machine is powered off; if VMware Tools are not available or if
        ``memdump=True``. Default is ``quiesce=False``

    CLI Example:

    .. code-block:: bash

        salt-cloud -a create_snapshot vmname snapshot_name="mySnapshot"
        salt-cloud -a create_snapshot vmname snapshot_name="mySnapshot" [description="My snapshot"] [memdump=False] [quiesce=True]
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The create_snapshot action must be called with '
            '-a or --action.'
        )

    snapshot_name = kwargs.get('snapshot_name') if kwargs and 'snapshot_name' in kwargs else None

    if not snapshot_name:
        raise SaltCloudSystemExit(
            'You must specify snapshot name for the snapshot to be created.'
        )

    memdump = _str_to_bool(kwargs.get('memdump', True))
    quiesce = _str_to_bool(kwargs.get('quiesce', False))

    vm_ref = _get_mor_by_property(vim.VirtualMachine, name)

    if vm_ref.summary.runtime.powerState != "poweredOn":
        log.debug('VM {0} is not powered on. Setting both memdump and quiesce to False'.format(name))
        memdump = False
        quiesce = False

    if memdump and quiesce:
        # Either memdump or quiesce should be set to True
        log.warning('You can only set either memdump or quiesce to True. Setting quiesce=False')
        quiesce = False

    desc = kwargs.get('description') if 'description' in kwargs else ''

    try:
        task = vm_ref.CreateSnapshot(snapshot_name, desc, memdump, quiesce)
        _wait_for_task(task, name, "create snapshot", 5, 'info')
    except Exception as exc:
        log.error(
            'Error while creating snapshot of {0}: {1}'.format(
                name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return 'failed to create snapshot'

    return {'Snapshot created successfully': _get_snapshots(vm_ref.snapshot.rootSnapshotList, vm_ref.snapshot.currentSnapshot)}


def revert_to_snapshot(name, kwargs=None, call=None):
    '''
    Revert virtual machine to it's current snapshot. If no snapshot
    exists, the state of the virtual machine remains unchanged

    .. note::

        The virtual machine will be powered on if the power state of
        the snapshot when it was created was set to "Powered On". Set
        ``power_off=True`` so that the virtual machine stays powered
        off regardless of the power state of the snapshot when it was
        created. Default is ``power_off=False``.

        If the power state of the snapshot when it was created was
        "Powered On" and if ``power_off=True``, the VM will be put in
        suspended state after it has been reverted to the snapshot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a revert_to_snapshot vmame [power_off=True]
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The revert_to_snapshot action must be called with '
            '-a or --action.'
        )

    suppress_power_on = _str_to_bool(kwargs.get('power_off', False))

    vm_ref = _get_mor_by_property(vim.VirtualMachine, name)

    if not vm_ref.rootSnapshot:
        log.error('VM {0} does not contain any current snapshots'.format(name))
        return 'revert failed'

    try:
        task = vm_ref.RevertToCurrentSnapshot(suppressPowerOn=suppress_power_on)
        _wait_for_task(task, name, "revert to snapshot", 5, 'info')

    except Exception as exc:
        log.error(
            'Error while reverting VM {0} to snapshot: {1}'.format(
                name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return 'revert failed'

    return 'reverted to current snapshot'


def remove_all_snapshots(name, kwargs=None, call=None):
    '''
    Remove all the snapshots present for the specified virtual machine.

    .. note::

        All the snapshots higher up in the hierarchy of the current snapshot tree
        are consolidated and their virtual disks are merged. To override this
        behavior and only remove all snapshots, set ``merge_snapshots=False``.
        Default is ``merge_snapshots=True``

    CLI Example:

    .. code-block:: bash

        salt-cloud -a remove_all_snapshots vmname [merge_snapshots=False]
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The remove_all_snapshots action must be called with '
            '-a or --action.'
        )

    consolidate = _str_to_bool(kwargs.get('merge_snapshots')) if kwargs and 'merge_snapshots' in kwargs else True

    vm_ref = _get_mor_by_property(vim.VirtualMachine, name)

    try:
        task = vm_ref.RemoveAllSnapshots()
        _wait_for_task(task, name, "remove snapshots", 5, 'info')
    except Exception as exc:
        log.error(
            'Error while removing snapshots on VM {0}: {1}'.format(
                name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return 'failed to remove snapshots'

    return 'removed all snapshots'


def add_host(kwargs=None, call=None):
    '''
    Add a host system to the specified cluster or datacenter in this VMware environment

    .. note::

        To use this function, you need to specify ``esxi_host_user`` and
        ``esxi_host_password`` under your provider configuration set up at
        ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

        .. code-block:: yaml

            vmware-vcenter01:
              provider: vmware
              user: "DOMAIN\\user"
              password: "verybadpass"
              url: "vcenter01.domain.com"

              # Required when adding a host system
              esxi_host_user: "root"
              esxi_host_password: "myhostpassword"
              # Optional fields that can be specified when adding a host system
              esxi_host_ssl_thumbprint: "12:A3:45:B6:CD:7E:F8:90:A1:BC:23:45:D6:78:9E:FA:01:2B:34:CD"

        The SSL thumbprint of the host system can be optionally specified by setting
        ``esxi_host_ssl_thumbprint`` under your provider configuration. To get the SSL
        thumbprint of the host system, execute the following command from a remote
        server:

        .. code-block:: bash

            echo -n | openssl s_client -connect <YOUR-HOSTSYSTEM-DNS/IP>:443 2>/dev/null | openssl x509 -noout -fingerprint -sha1

    CLI Example:

    .. code-block:: bash

        salt-cloud -f add_host my-vmware-config host="myHostSystemName" cluster="myClusterName"
        salt-cloud -f add_host my-vmware-config host="myHostSystemName" datacenter="myDatacenterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The add_host function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None
    cluster_name = kwargs.get('cluster') if kwargs and 'cluster' in kwargs else None
    datacenter_name = kwargs.get('datacenter') if kwargs and 'datacenter' in kwargs else None

    host_user = config.get_cloud_config_value(
        'esxi_host_user', get_configured_provider(), __opts__, search_global=False
    )
    host_password = config.get_cloud_config_value(
        'esxi_host_password', get_configured_provider(), __opts__, search_global=False
    )
    host_ssl_thumbprint = config.get_cloud_config_value(
        'esxi_host_ssl_thumbprint', get_configured_provider(), __opts__, search_global=False
    )

    if not host_user:
        raise SaltCloudSystemExit(
            'You must specify the ESXi host username in your providers config.'
        )

    if not host_password:
        raise SaltCloudSystemExit(
            'You must specify the ESXi host password in your providers config.'
        )

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify either the IP or DNS name of the host system.'
        )

    if (cluster_name and datacenter_name) or not(cluster_name or datacenter_name):
        raise SaltCloudSystemExit(
            'You must specify either the cluster name or the datacenter name.'
        )

    if cluster_name:
        cluster_ref = _get_mor_by_property(vim.ClusterComputeResource, cluster_name)
        if not cluster_ref:
            raise SaltCloudSystemExit(
                'Specified cluster does not exist.'
            )

    if datacenter_name:
        datacenter_ref = _get_mor_by_property(vim.Datacenter, datacenter_name)
        if not datacenter_ref:
            raise SaltCloudSystemExit(
                'Specified datacenter does not exist.'
            )

    spec = vim.host.ConnectSpec(
        hostName=host_name,
        userName=host_user,
        password=host_password,
    )

    if host_ssl_thumbprint:
        spec.sslThumbprint = host_ssl_thumbprint
    else:
        log.warning('SSL thumbprint has not been specified in provider configuration')
        try:
            log.debug('Trying to get the SSL thumbprint directly from the host system')
            p1 = subprocess.Popen(('echo', '-n'), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p2 = subprocess.Popen(('openssl', 's_client', '-connect', '{0}:443'.format(host_name)), stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p3 = subprocess.Popen(('openssl', 'x509', '-noout', '-fingerprint', '-sha1'), stdin=p2.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = salt.utils.to_str(p3.stdout.read())
            ssl_thumbprint = out.split('=')[-1].strip()
            log.debug('SSL thumbprint received from the host system: {0}'.format(ssl_thumbprint))
            spec.sslThumbprint = ssl_thumbprint
        except Exception as exc:
            log.error(
                'Error while trying to get SSL thumbprint of host {0}: {1}'.format(
                    host_name,
                    exc
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            return {host_name: 'failed to add host'}

    try:
        if cluster_name:
            task = cluster_ref.AddHost(spec=spec, asConnected=True)
            ret = 'added host system to cluster {0}'.format(cluster_name)
        if datacenter_name:
            task = datacenter_ref.hostFolder.AddStandaloneHost(spec=spec, addConnected=True)
            ret = 'added host system to datacenter {0}'.format(datacenter_name)
        _wait_for_task(task, host_name, "add host system", 5, 'info')
    except Exception as exc:
        if isinstance(exc, vim.fault.SSLVerifyFault):
            log.error('Authenticity of the host\'s SSL certificate is not verified')
            log.info('Try again after setting the esxi_host_ssl_thumbprint to {0} in provider configuration'.format(exc.thumbprint))
        log.error(
            'Error while adding host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to add host'}

    return {host_name: ret}


def remove_host(kwargs=None, call=None):
    '''
    Remove the specified host system from this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f remove_host my-vmware-config host="myHostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The remove_host function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify name of the host system.'
        )

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)
    if not host_ref:
        raise SaltCloudSystemExit(
            'Specified host system does not exist.'
        )

    try:
        if isinstance(host_ref.parent, vim.ComputeResource):
            # This is a standalone host system
            task = host_ref.parent.Destroy_Task()
        else:
            # This is a host system that is part of a Cluster
            task = host_ref.Destroy_Task()
        _wait_for_task(task, host_name, "remove host", 1, 'info')
    except Exception as exc:
        log.error(
            'Error while removing host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to remove host'}

    return {host_name: 'removed host from vcenter'}


def connect_host(kwargs=None, call=None):
    '''
    Connect the specified host system in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f connect_host my-vmware-config host="myHostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The connect_host function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify name of the host system.'
        )

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)
    if not host_ref:
        raise SaltCloudSystemExit(
            'Specified host system does not exist.'
        )

    if host_ref.runtime.connectionState == 'connected':
        return {host_name: 'host system already connected'}

    try:
        task = host_ref.ReconnectHost_Task()
        _wait_for_task(task, host_name, "connect host", 5, 'info')
    except Exception as exc:
        log.error(
            'Error while connecting host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to connect host'}

    return {host_name: 'connected host'}


def disconnect_host(kwargs=None, call=None):
    '''
    Disconnect the specified host system in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f disconnect_host my-vmware-config host="myHostSystemName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The disconnect_host function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify name of the host system.'
        )

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)
    if not host_ref:
        raise SaltCloudSystemExit(
            'Specified host system does not exist.'
        )

    if host_ref.runtime.connectionState == 'disconnected':
        return {host_name: 'host system already disconnected'}

    try:
        task = host_ref.DisconnectHost_Task()
        _wait_for_task(task, host_name, "disconnect host", 1, 'info')
    except Exception as exc:
        log.error(
            'Error while disconnecting host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to disconnect host'}

    return {host_name: 'disconnected host'}


def reboot_host(kwargs=None, call=None):
    '''
    Reboot the specified host system in this VMware environment

    .. note::

        If the host system is not in maintenance mode, it will not be rebooted. If you
        want to reboot the host system regardless of whether it is in maintenance mode,
        set ``force=True``. Default is ``force=False``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f reboot_host my-vmware-config host="myHostSystemName" [force=True]
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The reboot_host function must be called with '
            '-f or --function.'
        )

    host_name = kwargs.get('host') if kwargs and 'host' in kwargs else None
    force = _str_to_bool(kwargs.get('force')) if kwargs and 'force' in kwargs else False

    if not host_name:
        raise SaltCloudSystemExit(
            'You must specify name of the host system.'
        )

    host_ref = _get_mor_by_property(vim.HostSystem, host_name)
    if not host_ref:
        raise SaltCloudSystemExit(
            'Specified host system does not exist.'
        )

    if host_ref.runtime.connectionState == 'notResponding':
        raise SaltCloudSystemExit(
            'Specified host system cannot be rebooted in it\'s current state (not responding).'
        )

    if not host_ref.capability.rebootSupported:
        raise SaltCloudSystemExit(
            'Specified host system does not support reboot.'
        )

    if not host_ref.runtime.inMaintenanceMode:
        raise SaltCloudSystemExit(
            'Specified host system is not in maintenance mode. Specify force=True to '
            'force reboot even if there are virtual machines running or other operations '
            'in progress.'
        )

    try:
        host_ref.RebootHost_Task(force)
        _wait_for_host(host_ref, "reboot", 10, 'info')
    except Exception as exc:
        log.error(
            'Error while rebooting host {0}: {1}'.format(
                host_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {host_name: 'failed to reboot host'}

    return {host_name: 'rebooted host'}


def create_datastore_cluster(kwargs=None, call=None):
    '''
    Create a new datastore cluster for the specified datacenter in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f create_datastore_cluster my-vmware-config name="datastoreClusterName" datacenter="datacenterName"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_datastore_cluster function must be called with '
            '-f or --function.'
        )

    datastore_cluster_name = kwargs.get('name') if kwargs and 'name' in kwargs else None
    datacenter_name = kwargs.get('datacenter') if kwargs and 'datacenter' in kwargs else None

    if not datastore_cluster_name:
        raise SaltCloudSystemExit(
            'You must specify name of the new datastore cluster to be created.'
        )

    if len(datastore_cluster_name) >= 80 or len(datastore_cluster_name) <= 0:
        raise SaltCloudSystemExit(
            'The datastore cluster name must be a non empty string of less than 80 characters.'
        )

    if not datacenter_name:
        raise SaltCloudSystemExit(
            'You must specify name of the datacenter where the datastore cluster should be created.'
        )

    # Check if datastore cluster already exists
    datastore_cluster_ref = _get_mor_by_property(vim.StoragePod, datastore_cluster_name)
    if datastore_cluster_ref:
        return {datastore_cluster_name: 'datastore cluster already exists'}

    datacenter_ref = _get_mor_by_property(vim.Datacenter, datacenter_name)
    if not datacenter_ref:
        raise SaltCloudSystemExit(
            'The specified datacenter does not exist.'
        )

    try:
        datacenter_ref.datastoreFolder.CreateStoragePod(name=datastore_cluster_name)
    except Exception as exc:
        log.error(
            'Error creating datastore cluster {0}: {1}'.format(
                datastore_cluster_name,
                exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    return {datastore_cluster_name: 'created'}
