"""
Salt state to create, update VMware ESXi Virtual Machines.

Dependencies
============

- pyVmomi
- jsonschema

States
======

vm_configured
-------------

Enforces correct virtual machine configuration. Creates, updates and registers
a virtual machine.

This state identifies the action which should be taken for the virtual machine
and applies that action via the create, update, register state functions.

Supported proxies: esxvm


Example:

1. Get the virtual machine ``my_vm`` status with an ``esxvm`` proxy:

Proxy minion configuration for ``esxvm`` proxy:

.. code-block:: yaml

    proxy:
      proxytype: esxvm
      datacenter: my_dc
      vcenter: vcenter.fake.com
      mechanism: sspi
      domain: fake.com
      principal: host

State configuration:

.. code-block:: yaml

      myvm_state:
        esxvm.vm_configured:
        - vm_name: my_vm
        - cpu: {{ {'count': 4, 'cores_per_socket': 2} }}
        - memory: {{ {'size': 16384, 'unit': 'MB'} }}
        - image: rhel7_64Guest
        - version: vmx-12
        - interfaces: {{ [{
                           'adapter': 'Network adapter 1',
                           'name': 'my_pg1',
                           'switch_type': 'distributed',
                           'adapter_type': 'vmxnet3',
                           'mac': '00:50:56:00:01:02,
                           'connectable': { 'start_connected': true,
                                            'allow_guest_control': true,
                                            'connected': true}},
                           {
                           'adapter': 'Network adapter 2',
                           'name': 'my_pg2',
                           'switch_type': 'distributed',
                           'adapter_type': 'vmxnet3',
                           'mac': '00:50:56:00:01:03',
                           'connectable': { 'start_connected': true,
                                            'allow_guest_control': true,
                                            'connected': true}}
                      ] }}
        - disks: {{ [{
                      'adapter': 'Hard disk 1',
                      'unit': 'MB',
                      'size': 51200,
                      'filename': 'my_vm/sda.vmdk',
                      'datastore': 'my_datastore',
                      'address': '0:0',
                      'thin_provision': true,
                      'eagerly_scrub': false,
                      'controller': 'SCSI controller 0'},
                      {
                      'adapter': 'Hard disk 2',
                      'unit': 'MB',
                      'size': 10240,
                      'filename': 'my_vm/sdb.vmdk',
                      'datastore': 'my_datastore',
                      'address': '0:1',
                      'thin_provision': true,
                      'eagerly_scrub': false,
                      'controller': 'SCSI controller 0'}
                ] }}
        - scsi_devices: {{ [{
                             'adapter': 'SCSI controller 0',
                             'type': 'paravirtual',
                             'bus_sharing': 'no_sharing',
                             'bus_number': 0}
                            ] }}
        - serial_ports: {{ [{
                             'adapter': 'Serial port 1',
                             'type': 'network',
                             'yield': false,
                             'backing': {
                                         'uri': 'my_uri',
                                         'direction': 'server',
                                         'filename': 'my_file'},
                              'connectable': {
                                              'start_connected': true,
                                              'allow_guest_control': true,
                                              'connected': true}}
                             ] }}
        - datacenter: {{ 'my_dc' }}
        - datastore: 'my_datastore'
        - placement: {{ {'cluster': 'my_cluster'} }}
        - cd_dvd_drives: {{ [] }}
        - advanced_configs: {{ {'my_param': '1'} }}
        - template: false
        - tools: false
        - power_on: false
        - deploy: false


vm_updated
----------

Updates a virtual machine to a given configuration.

vm_created
----------

Creates a virtual machine with a given configuration.

vm_registered
-------------

Registers a virtual machine with its configuration file path.

Dependencies
============

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on
    certain versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream
    dependency in pyVmomi 6.0 that is not supported in Python versions
    2.7 to 2.7.8. If the version of Python is not in the supported range,
    you will need to install an earlier version of pyVmomi.
    See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==6.0.0.2016.4

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against. To be able to connect through SSPI you must
use pyvmomi 6.0.0.2016.4 or above. The ESXVM State Module was tested with
this version.

About
-----

This state module was written to be used in conjunction with Salt's
:mod:`ESXi Proxy Minion <salt.proxy.esxi>` For a tutorial on how to use Salt's
ESXi Proxy Minion, please refer to the
:ref:`ESXi Proxy Minion Tutorial <tutorial-esxi-proxy>` for
configuration examples, dependency installation instructions, how to run remote
execution functions against ESXi hosts via a Salt Proxy Minion, and a larger state
example.
"""


import logging
import sys

import salt.exceptions
from salt.config.schemas.esxvm import ESXVirtualMachineConfigSchema

# External libraries
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

try:
    from pyVmomi import VmomiSupport

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_JSONSCHEMA:
        return False, "State module did not load: jsonschema not found"
    if not HAS_PYVMOMI:
        return False, "State module did not load: pyVmomi not found"

    # We check the supported vim versions to infer the pyVmomi version
    if (
        "vim25/6.0" in VmomiSupport.versionMap
        and sys.version_info > (2, 7)
        and sys.version_info < (2, 7, 9)
    ):

        return (
            False,
            "State module did not load: Incompatible versions "
            "of Python and pyVmomi present. See Issue #29537.",
        )
    return True


def vm_configured(
    name,
    vm_name,
    cpu,
    memory,
    image,
    version,
    interfaces,
    disks,
    scsi_devices,
    serial_ports,
    datacenter,
    datastore,
    placement,
    cd_dvd_drives=None,
    sata_controllers=None,
    advanced_configs=None,
    template=None,
    tools=True,
    power_on=False,
    deploy=False,
):
    """
    Selects the correct operation to be executed on a virtual machine, non
    existing machines will be created, existing ones will be updated if the
    config differs.
    """
    result = {"name": name, "result": None, "changes": {}, "comment": ""}

    log.trace("Validating virtual machine configuration")
    schema = ESXVirtualMachineConfigSchema.serialize()
    log.trace("schema = %s", schema)
    try:
        jsonschema.validate(
            {
                "vm_name": vm_name,
                "cpu": cpu,
                "memory": memory,
                "image": image,
                "version": version,
                "interfaces": interfaces,
                "disks": disks,
                "scsi_devices": scsi_devices,
                "serial_ports": serial_ports,
                "cd_dvd_drives": cd_dvd_drives,
                "sata_controllers": sata_controllers,
                "datacenter": datacenter,
                "datastore": datastore,
                "placement": placement,
                "template": template,
                "tools": tools,
                "power_on": power_on,
                "deploy": deploy,
            },
            schema,
        )
    except jsonschema.exceptions.ValidationError as exc:
        raise salt.exceptions.InvalidConfigError(exc)

    service_instance = __salt__["vsphere.get_service_instance_via_proxy"]()
    try:
        __salt__["vsphere.get_vm"](
            vm_name, vm_properties=["name"], service_instance=service_instance
        )
    except salt.exceptions.VMwareObjectRetrievalError:
        vm_file = __salt__["vsphere.get_vm_config_file"](
            vm_name, datacenter, placement, datastore, service_instance=service_instance
        )
        if vm_file:
            if __opts__["test"]:
                result.update(
                    {
                        "comment": "The virtual machine {} will be registered.".format(
                            vm_name
                        )
                    }
                )
                __salt__["vsphere.disconnect"](service_instance)
                return result
            result = vm_registered(
                vm_name, datacenter, placement, vm_file, power_on=power_on
            )
            return result
        else:
            if __opts__["test"]:
                result.update(
                    {
                        "comment": "The virtual machine {} will be created.".format(
                            vm_name
                        )
                    }
                )
                __salt__["vsphere.disconnect"](service_instance)
                return result
            if template:
                result = vm_cloned(name)
            else:
                result = vm_created(
                    name,
                    vm_name,
                    cpu,
                    memory,
                    image,
                    version,
                    interfaces,
                    disks,
                    scsi_devices,
                    serial_ports,
                    datacenter,
                    datastore,
                    placement,
                    cd_dvd_drives=cd_dvd_drives,
                    advanced_configs=advanced_configs,
                    power_on=power_on,
                )
            return result

    result = vm_updated(
        name,
        vm_name,
        cpu,
        memory,
        image,
        version,
        interfaces,
        disks,
        scsi_devices,
        serial_ports,
        datacenter,
        datastore,
        cd_dvd_drives=cd_dvd_drives,
        sata_controllers=sata_controllers,
        advanced_configs=advanced_configs,
        power_on=power_on,
    )
    __salt__["vsphere.disconnect"](service_instance)

    log.trace(result)
    return result


def vm_cloned(name):
    """
    Clones a virtual machine from a template virtual machine if it doesn't
    exist and a template is defined.
    """
    result = {"name": name, "result": True, "changes": {}, "comment": ""}

    return result


def vm_updated(
    name,
    vm_name,
    cpu,
    memory,
    image,
    version,
    interfaces,
    disks,
    scsi_devices,
    serial_ports,
    datacenter,
    datastore,
    cd_dvd_drives=None,
    sata_controllers=None,
    advanced_configs=None,
    power_on=False,
):
    """
    Updates a virtual machine configuration if there is a difference between
    the given and deployed configuration.
    """
    result = {"name": name, "result": None, "changes": {}, "comment": ""}

    service_instance = __salt__["vsphere.get_service_instance_via_proxy"]()
    current_config = __salt__["vsphere.get_vm_config"](
        vm_name, datacenter=datacenter, objects=False, service_instance=service_instance
    )

    diffs = __salt__["vsphere.compare_vm_configs"](
        {
            "name": vm_name,
            "cpu": cpu,
            "memory": memory,
            "image": image,
            "version": version,
            "interfaces": interfaces,
            "disks": disks,
            "scsi_devices": scsi_devices,
            "serial_ports": serial_ports,
            "datacenter": datacenter,
            "datastore": datastore,
            "cd_drives": cd_dvd_drives,
            "sata_controllers": sata_controllers,
            "advanced_configs": advanced_configs,
        },
        current_config,
    )
    if not diffs:
        result.update(
            {
                "result": True,
                "changes": {},
                "comment": "Virtual machine {} is already up to date".format(vm_name),
            }
        )
        return result

    if __opts__["test"]:
        comment = (
            "State vm_updated will update virtual machine '{}' "
            "in datacenter '{}':\n{}".format(
                vm_name,
                datacenter,
                "\n".join(
                    [
                        ":\n".join([key, difference.changes_str])
                        for key, difference in diffs.items()
                    ]
                ),
            )
        )
        result.update({"result": None, "comment": comment})
        __salt__["vsphere.disconnect"](service_instance)
        return result

    try:
        changes = __salt__["vsphere.update_vm"](
            vm_name,
            cpu,
            memory,
            image,
            version,
            interfaces,
            disks,
            scsi_devices,
            serial_ports,
            datacenter,
            datastore,
            cd_dvd_drives=cd_dvd_drives,
            sata_controllers=sata_controllers,
            advanced_configs=advanced_configs,
            service_instance=service_instance,
        )
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc)
        if service_instance:
            __salt__["vsphere.disconnect"](service_instance)
        result.update({"result": False, "comment": str(exc)})
        return result

    if power_on:
        try:
            __salt__["vsphere.power_on_vm"](vm_name, datacenter)
        except salt.exceptions.VMwarePowerOnError as exc:
            log.error("Error: %s", exc)
            if service_instance:
                __salt__["vsphere.disconnect"](service_instance)
            result.update({"result": False, "comment": str(exc)})
            return result
        changes.update({"power_on": True})

    __salt__["vsphere.disconnect"](service_instance)

    result = {
        "name": name,
        "result": True,
        "changes": changes,
        "comment": "Virtual machine {} was updated successfully".format(vm_name),
    }

    return result


def vm_created(
    name,
    vm_name,
    cpu,
    memory,
    image,
    version,
    interfaces,
    disks,
    scsi_devices,
    serial_ports,
    datacenter,
    datastore,
    placement,
    ide_controllers=None,
    sata_controllers=None,
    cd_dvd_drives=None,
    advanced_configs=None,
    power_on=False,
):
    """
    Creates a virtual machine with the given properties if it doesn't exist.
    """
    result = {"name": name, "result": None, "changes": {}, "comment": ""}

    if __opts__["test"]:
        result["comment"] = "Virtual machine {} will be created".format(vm_name)
        return result

    service_instance = __salt__["vsphere.get_service_instance_via_proxy"]()
    try:
        info = __salt__["vsphere.create_vm"](
            vm_name,
            cpu,
            memory,
            image,
            version,
            datacenter,
            datastore,
            placement,
            interfaces,
            disks,
            scsi_devices,
            serial_ports=serial_ports,
            ide_controllers=ide_controllers,
            sata_controllers=sata_controllers,
            cd_drives=cd_dvd_drives,
            advanced_configs=advanced_configs,
            service_instance=service_instance,
        )
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc)
        if service_instance:
            __salt__["vsphere.disconnect"](service_instance)
        result.update({"result": False, "comment": str(exc)})
        return result

    if power_on:
        try:
            __salt__["vsphere.power_on_vm"](
                vm_name, datacenter, service_instance=service_instance
            )
        except salt.exceptions.VMwarePowerOnError as exc:
            log.error("Error: %s", exc)
            if service_instance:
                __salt__["vsphere.disconnect"](service_instance)
            result.update({"result": False, "comment": str(exc)})
            return result
        info["power_on"] = power_on

    changes = {"name": vm_name, "info": info}
    __salt__["vsphere.disconnect"](service_instance)
    result = {
        "name": name,
        "result": True,
        "changes": changes,
        "comment": "Virtual machine {} created successfully".format(vm_name),
    }

    return result


def vm_registered(vm_name, datacenter, placement, vm_file, power_on=False):
    """
    Registers a virtual machine if the machine files are available on
    the main datastore.
    """
    result = {"name": vm_name, "result": None, "changes": {}, "comment": ""}

    vmx_path = "{}{}".format(vm_file.folderPath, vm_file.file[0].path)
    log.trace("Registering virtual machine with vmx file: %s", vmx_path)
    service_instance = __salt__["vsphere.get_service_instance_via_proxy"]()
    try:
        __salt__["vsphere.register_vm"](
            vm_name, datacenter, placement, vmx_path, service_instance=service_instance
        )
    except salt.exceptions.VMwareMultipleObjectsError as exc:
        log.error("Error: %s", exc)
        if service_instance:
            __salt__["vsphere.disconnect"](service_instance)
        result.update({"result": False, "comment": str(exc)})
        return result
    except salt.exceptions.VMwareVmRegisterError as exc:
        log.error("Error: %s", exc)
        if service_instance:
            __salt__["vsphere.disconnect"](service_instance)
        result.update({"result": False, "comment": str(exc)})
        return result

    if power_on:
        try:
            __salt__["vsphere.power_on_vm"](
                vm_name, datacenter, service_instance=service_instance
            )
        except salt.exceptions.VMwarePowerOnError as exc:
            log.error("Error: %s", exc)
            if service_instance:
                __salt__["vsphere.disconnect"](service_instance)
            result.update({"result": False, "comment": str(exc)})
            return result
    __salt__["vsphere.disconnect"](service_instance)
    result.update(
        {
            "result": True,
            "changes": {"name": vm_name, "power_on": power_on},
            "comment": "Virtual machine {} registered successfully".format(vm_name),
        }
    )

    return result
