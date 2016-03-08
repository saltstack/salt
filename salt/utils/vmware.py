# -*- coding: utf-8 -*-
'''
Connection library for VMware

.. versionadded:: 2015.8.2

This is a base library used by a number of VMware services such as VMware
ESX, ESXi, and vCenter servers.

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>

Dependencies
~~~~~~~~~~~~

- pyVmomi Python Module
- ESXCLI: This dependency is only needed to use the ``esxcli`` function. No other
  functions in this module rely on ESXCLI.

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original VMware utils file
was developed against.

ESXCLI
------

This dependency is only needed to use the ``esxcli`` function. At the time of this
writing, no other functions in this module rely on ESXCLI.

The ESXCLI package is also referred to as the VMware vSphere CLI, or vCLI. VMware
provides vCLI package installation instructions for `vSphere 5.5`_ and
`vSphere 6.0`_.

.. _vSphere 5.5: http://pubs.vmware.com/vsphere-55/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html
.. _vSphere 6.0: http://pubs.vmware.com/vsphere-60/index.jsp#com.vmware.vcli.getstart.doc/cli_install.4.2.html

Once all of the required dependencies are in place and the vCLI package is
installed, you can check to see if you can connect to your ESXi host or vCenter
server by running the following command:

.. code-block:: bash

    esxcli -s <host-location> -u <username> -p <password> system syslog config get

If the connection was successful, ESXCLI was successfully installed on your system.
You should see output related to the ESXi host's syslog configuration.

'''

# Import Python Libs
from __future__ import absolute_import
import atexit
import logging
import time

# Import Salt Libs
from salt.exceptions import SaltSystemExit
import salt.modules.cmdmod
import salt.utils


# Import Third Party Libs
try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if PyVmomi is installed.
    '''
    if HAS_PYVMOMI:
        return True
    else:
        return False, 'Missing dependency: The salt.utils.vmware module requires pyVmomi.'


def esxcli(host, user, pwd, cmd, protocol=None, port=None, esxi_host=None):
    '''
    Shell out and call the specified esxcli commmand, parse the result
    and return something sane.

    :param host: ESXi or vCenter host to connect to
    :param user: User to connect as, usually root
    :param pwd: Password to connect with
    :param port: TCP port
    :param cmd: esxcli command and arguments
    :param esxi_host: If `host` is a vCenter host, then esxi_host is the
                      ESXi machine on which to execute this command
    :return: Dictionary
    '''

    esx_cmd = salt.utils.which('esxcli')
    if not esx_cmd:
        log.error('Missing dependency: The salt.utils.vmware.esxcli function requires ESXCLI.')
        return False

    # Set default port and protocol if none are provided.
    if port is None:
        port = 443
    if protocol is None:
        protocol = 'https'

    if not esxi_host:
        # Then we are connecting directly to an ESXi server,
        # 'host' points at that server, and esxi_host is a reference to the
        # ESXi instance we are manipulating
        esx_cmd += ' -s {0} -u {1} -p \'{2}\' ' \
                   '--protocol={3} --portnumber={4} {5}'.format(host,
                                                                user,
                                                                pwd,
                                                                protocol,
                                                                port,
                                                                cmd)
    else:
        esx_cmd += ' -s {0} -h {1} -u {2} -p \'{3}\' ' \
                   '--protocol={4} --portnumber={5} {6}'.format(host,
                                                                esxi_host,
                                                                user,
                                                                pwd,
                                                                protocol,
                                                                port,
                                                                cmd)

    ret = salt.modules.cmdmod.run_all(esx_cmd, output_loglevel='quiet')

    return ret


def get_service_instance(host, username, password, protocol=None, port=None):
    '''
    Authenticate with a vCenter server or ESX/ESXi host and return the service instance object.

    host
        The location of the vCenter server or ESX/ESXi host.

    username
        The username used to login to the vCenter server or ESX/ESXi host.

    password
        The password used to login to the vCenter server or ESX/ESXi host.

    protocol
        Optionally set to alternate protocol if the vCenter server or ESX/ESXi host is not
        using the default protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the vCenter server or ESX/ESXi host is not
        using the default port. Default port is ``443``.
    '''
    if protocol is None:
        protocol = 'https'
    if port is None:
        port = 443

    try:
        service_instance = SmartConnect(
            host=host,
            user=username,
            pwd=password,
            protocol=protocol,
            port=port
        )
    except Exception as exc:
        default_msg = 'Could not connect to host \'{0}\'. ' \
                      'Please check the debug log for more information.'.format(host)
        try:
            if (isinstance(exc, vim.fault.HostConnectFault) and '[SSL: CERTIFICATE_VERIFY_FAILED]' in exc.msg) or '[SSL: CERTIFICATE_VERIFY_FAILED]' in str(exc):
                import ssl
                default_context = ssl._create_default_https_context
                ssl._create_default_https_context = ssl._create_unverified_context
                service_instance = SmartConnect(
                    host=host,
                    user=username,
                    pwd=password,
                    protocol=protocol,
                    port=port
                )
                ssl._create_default_https_context = default_context
            else:
                err_msg = exc.msg if hasattr(exc, 'msg') else default_msg
                log.debug(exc)
                raise SaltSystemExit(err_msg)

        except Exception as exc:
            if 'certificate verify failed' in str(exc):
                import ssl
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                context.verify_mode = ssl.CERT_NONE
                service_instance = SmartConnect(
                    host=host,
                    user=username,
                    pwd=password,
                    protocol=protocol,
                    port=port,
                    sslContext=context
                )
            else:
                err_msg = exc.msg if hasattr(exc, 'msg') else default_msg
                log.debug(exc)
                raise SaltSystemExit(err_msg)

    atexit.register(Disconnect, service_instance)

    return service_instance


def _get_dvs(service_instance, dvs_name):
    '''
    Return a reference to a Distributed Virtual Switch object.

    :param service_instance: PyVmomi service instance
    :param dvs_name: Name of DVS to return
    :return: A PyVmomi DVS object
    '''
    switches = list_dvs(service_instance)
    if dvs_name in switches:
        inventory = get_inventory(service_instance)
        container = inventory.viewManager.CreateContainerView(inventory.rootFolder, [vim.DistributedVirtualSwitch], True)
        for item in container.view:
            if item.name == dvs_name:
                return item

    return None


def _get_pnics(host_reference):
    '''
    Helper function that returns a list of PhysicalNics and their information.
    '''
    return host_reference.config.network.pnic


def _get_vnics(host_reference):
    '''
    Helper function that returns a list of VirtualNics and their information.
    '''
    return host_reference.config.network.vnic


def _get_vnic_manager(host_reference):
    '''
    Helper function that returns a list of Virtual NicManagers
    and their information.
    '''
    return host_reference.configManager.virtualNicManager


def _get_dvs_portgroup(dvs, portgroup_name):
    '''
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    '''
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def _get_dvs_uplink_portgroup(dvs, portgroup_name):
    '''
    Return a portgroup object corresponding to the portgroup name on the dvs

    :param dvs: DVS object
    :param portgroup_name: Name of portgroup to return
    :return: Portgroup object
    '''
    for portgroup in dvs.portgroup:
        if portgroup.name == portgroup_name:
            return portgroup

    return None


def get_hardware_grains(service_instance):
    '''
    Return hardware info for standard minion grains if the service_instance is a HostAgent type

    service_instance
        The service instance object to get hardware info for

    .. versionadded:: Carbon
    '''
    hw_grain_data = {}
    if get_inventory(service_instance).about.apiType == 'HostAgent':
        view = service_instance.content.viewManager.CreateContainerView(service_instance.RetrieveContent().rootFolder,
                                                                        [vim.HostSystem], True)
        if view:
            if view.view:
                if len(view.view) > 0:
                    hw_grain_data['manufacturer'] = view.view[0].hardware.systemInfo.vendor
                    hw_grain_data['productname'] = view.view[0].hardware.systemInfo.model

                    for _data in view.view[0].hardware.systemInfo.otherIdentifyingInfo:
                        if _data.identifierType.key == 'ServiceTag':
                            hw_grain_data['serialnumber'] = _data.identifierValue

                    hw_grain_data['osfullname'] = view.view[0].summary.config.product.fullName
                    hw_grain_data['osmanufacturer'] = view.view[0].summary.config.product.vendor
                    hw_grain_data['osrelease'] = view.view[0].summary.config.product.version
                    hw_grain_data['osbuild'] = view.view[0].summary.config.product.build
                    hw_grain_data['os_family'] = view.view[0].summary.config.product.name
                    hw_grain_data['os'] = view.view[0].summary.config.product.name
                    hw_grain_data['mem_total'] = view.view[0].hardware.memorySize /1024/1024
                    hw_grain_data['biosversion'] = view.view[0].hardware.biosInfo.biosVersion
                    hw_grain_data['biosreleasedate'] = view.view[0].hardware.biosInfo.releaseDate.date().strftime('%m/%d/%Y')
                    hw_grain_data['cpu_model'] = view.view[0].hardware.cpuPkg[0].description
                    hw_grain_data['kernel'] = view.view[0].summary.config.product.productLineId
                    hw_grain_data['num_cpu_sockets'] = view.view[0].hardware.cpuInfo.numCpuPackages
                    hw_grain_data['num_cpu_cores'] = view.view[0].hardware.cpuInfo.numCpuCores
                    hw_grain_data['num_cpus'] = hw_grain_data['num_cpu_sockets'] * hw_grain_data['num_cpu_cores']
                    hw_grain_data['ip_interfaces'] = {}
                    hw_grain_data['ip4_interfaces'] = {}
                    hw_grain_data['ip6_interfaces'] = {}
                    hw_grain_data['hwaddr_interfaces'] = {}
                    for _vnic in view.view[0].configManager.networkSystem.networkConfig.vnic:
                        hw_grain_data['ip_interfaces'][_vnic.device] = []
                        hw_grain_data['ip4_interfaces'][_vnic.device] = []
                        hw_grain_data['ip6_interfaces'][_vnic.device] = []

                        hw_grain_data['ip_interfaces'][_vnic.device].append(_vnic.spec.ip.ipAddress)
                        hw_grain_data['ip4_interfaces'][_vnic.device].append(_vnic.spec.ip.ipAddress)
                        if _vnic.spec.ip.ipV6Config:
                            hw_grain_data['ip6_interfaces'][_vnic.device].append(_vnic.spec.ip.ipV6Config.ipV6Address)
                        hw_grain_data['hwaddr_interfaces'][_vnic.device] = _vnic.spec.mac
                    hw_grain_data['host'] = view.view[0].configManager.networkSystem.dnsConfig.hostName
                    hw_grain_data['domain'] = view.view[0].configManager.networkSystem.dnsConfig.domainName
                    hw_grain_data['fqdn'] = '{0}{1}{2}'.format(
                            view.view[0].configManager.networkSystem.dnsConfig.hostName,
                            ('.' if view.view[0].configManager.networkSystem.dnsConfig.domainName else ''),
                            view.view[0].configManager.networkSystem.dnsConfig.domainName)

                    for _pnic in view.view[0].configManager.networkSystem.networkInfo.pnic:
                        hw_grain_data['hwaddr_interfaces'][_pnic.device] = _pnic.mac

                    hw_grain_data['timezone'] = view.view[0].configManager.dateTimeSystem.dateTimeInfo.timeZone.name
                view = None
    return hw_grain_data


def get_inventory(service_instance):
    '''
    Return the inventory of a Service Instance Object.

    service_instance
        The Service Instance Object for which to obtain inventory.
    '''
    return service_instance.RetrieveContent()


def get_content(service_instance, obj_type, property_list=None, container_ref=None):
    '''
    Returns the content of the specified type of object for a Service Instance.

    For more information, please see:
    http://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch5_PropertyCollector.7.6.html

    service_instance
        The Service Instance from which to obtain content.

    obj_type
        The type of content to obtain.

    property_list
        An optional list of object properties to used to return even more filtered content results.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.
    '''
    # Start at the rootFolder if container starting point not specified
    if not container_ref:
        container_ref = service_instance.content.rootFolder

    # Create an object view
    obj_view = service_instance.content.viewManager.CreateContainerView(
        container_ref, [obj_type], True)

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
    content = service_instance.content.propertyCollector.RetrieveContents([filter_spec])

    # Destroy the object view
    obj_view.Destroy()

    return content


def get_mor_by_property(service_instance, object_type, property_value, property_name='name', container_ref=None):
    '''
    Returns the first managed object reference having the specified property value.

    service_instance
        The Service Instance from which to obtain managed object references.

    object_type
        The type of content for which to obtain managed object references.

    property_value
        The name of the property for which to obtain the managed object reference.

    property_name
        An object property used to return the specified object reference results. Defaults to ``name``.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.
    '''
    # Get list of all managed object references with specified property
    object_list = get_mors_with_properties(service_instance, object_type, property_list=[property_name], container_ref=container_ref)

    for obj in object_list:
        if obj[property_name] == property_value:
            return obj['object']

    return None


def get_mors_with_properties(service_instance, object_type, property_list=None, container_ref=None):
    '''
    Returns a list containing properties and managed object references for the managed object.

    service_instance
        The Service Instance from which to obtain managed object references.

    object_type
        The type of content for which to obtain managed object references.

    property_list
        An optional list of object properties used to return even more filtered managed object reference results.

    container_ref
        An optional reference to the managed object to search under. Can either be an object of type Folder, Datacenter,
        ComputeResource, Resource Pool or HostSystem. If not specified, default behaviour is to search under the inventory
        rootFolder.
    '''
    # Get all the content
    content = get_content(service_instance, object_type, property_list=property_list, container_ref=container_ref)

    object_list = []
    for obj in content:
        properties = {}
        for prop in obj.propSet:
            properties[prop.name] = prop.val
            properties['object'] = obj.obj
        object_list.append(properties)

    return object_list


def get_network_adapter_type(adapter_type):
    '''
    Return the network adapter type.

    adpater_type
        The adapter type from which to obtain the network adapter type.
    '''
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


def list_objects(service_instance, vim_object, properties=None):
    '''
    Returns a simple list of objects from a given service instance.

    service_instance
        The Service Instance for which to obtain a list of objects.

    object_type
        The type of content for which to obtain information.

    property_list
        An optional list of object properties used to return reference results.
        If not provided, defaults to ``name``.
    '''
    if properties is None:
        properties = ['name']

    items = []
    item_list = get_mors_with_properties(service_instance, vim_object, properties)
    for item in item_list:
        items.append(item['name'])
    return items


def list_datacenters(service_instance):
    '''
    Returns a list of datacenters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datacenters.
    '''
    return list_objects(service_instance, vim.Datacenter)


def list_clusters(service_instance):
    '''
    Returns a list of clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain clusters.
    '''
    return list_objects(service_instance, vim.ClusterComputeResource)


def list_datastore_clusters(service_instance):
    '''
    Returns a list of datastore clusters associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastore clusters.
    '''
    return list_objects(service_instance, vim.StoragePod)


def list_datastores(service_instance):
    '''
    Returns a list of datastores associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain datastores.
    '''
    return list_objects(service_instance, vim.Datastore)


def list_hosts(service_instance):
    '''
    Returns a list of hosts associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain hosts.
    '''
    return list_objects(service_instance, vim.HostSystem)


def list_resourcepools(service_instance):
    '''
    Returns a list of resource pools associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain resource pools.
    '''
    return list_objects(service_instance, vim.ResourcePool)


def list_networks(service_instance):
    '''
    Returns a list of networks associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain networks.
    '''
    return list_objects(service_instance, vim.Network)


def list_vms(service_instance):
    '''
    Returns a list of VMs associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain VMs.
    '''
    return list_objects(service_instance, vim.VirtualMachine)


def list_folders(service_instance):
    '''
    Returns a list of folders associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain folders.
    '''
    return list_objects(service_instance, vim.Folder)


def list_dvs(service_instance):
    '''
    Returns a list of distributed virtual switches associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    '''
    return list_objects(service_instance, vim.DistributedVirtualSwitch)


def list_vapps(service_instance):
    '''
    Returns a list of vApps associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain vApps.
    '''
    return list_objects(service_instance, vim.VirtualApp)


def list_portgroups(service_instance):
    '''
    Returns a list of distributed virtual portgroups associated with a given service instance.

    service_instance
        The Service Instance Object from which to obtain distributed virtual switches.
    '''
    return list_objects(service_instance, vim.dvs.DistributedVirtualPortgroup)


def wait_for_task(task, instance_name, task_type, sleep_seconds=1, log_level='debug'):
    '''
    Waits for a task to be completed.

    task
        The task to wait for.

    instance_name
        The name of the ESXi host, vCenter Server, or Virtual Machine that the task is being run on.

    task_type
        The type of task being performed. Useful information for debugging purposes.

    sleep_seconds
        The number of seconds to wait before querying the task again. Defaults to ``1`` second.

    log_level
        The level at which to log task information. Default is ``debug``, but ``info`` is also supported.
    '''
    time_counter = 0
    start_time = time.time()
    while task.info.state == 'running' or task.info.state == 'queued':
        if time_counter % sleep_seconds == 0:
            msg = '[ {0} ] Waiting for {1} task to finish [{2} s]'.format(instance_name, task_type, time_counter)
            if log_level == 'info':
                log.info(msg)
            else:
                log.debug(msg)
        time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        time_counter += 1
    if task.info.state == 'success':
        msg = '[ {0} ] Successfully completed {1} task in {2} seconds'.format(instance_name, task_type, time_counter)
        if log_level == 'info':
            log.info(msg)
        else:
            log.debug(msg)
    else:
        raise Exception(task.info.error)
