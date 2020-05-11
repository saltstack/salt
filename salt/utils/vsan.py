# -*- coding: utf-8 -*-
'''
Connection library for VMware vSAN endpoint

This library used the vSAN extension of the VMware SDK
used to manage vSAN related objects

:codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstaley.com>

Dependencies
~~~~~~~~~~~~

- pyVmomi Python Module

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

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
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import sys
import logging
import ssl

# Import Salt Libs
from salt.ext import six
from salt.exceptions import VMwareApiError, VMwareRuntimeError, \
        VMwareObjectRetrievalError
import salt.utils.vmware

try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


try:
    from salt.ext.vsan import vsanapiutils
    HAS_PYVSAN = True
except ImportError:
    HAS_PYVSAN = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if PyVmomi is installed.
    '''
    if HAS_PYVSAN and HAS_PYVMOMI:
        return True
    else:
        return False, 'Missing dependency: The salt.utils.vsan module ' \
                'requires pyvmomi and the pyvsan extension library'


def vsan_supported(service_instance):
    '''
    Returns whether vsan is supported on the vCenter:
        api version needs to be 6 or higher

    service_instance
        Service instance to the host or vCenter
    '''
    try:
        api_version = service_instance.content.about.apiVersion
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    if int(api_version.split('.')[0]) < 6:
        return False
    return True


def get_vsan_cluster_config_system(service_instance):
    '''
    Returns a vim.cluster.VsanVcClusterConfigSystem object

    service_instance
        Service instance to the host or vCenter
    '''

    #TODO Replace when better connection mechanism is available

    #For python 2.7.9 and later, the defaul SSL conext has more strict
    #connection handshaking rule. We may need turn of the hostname checking
    #and client side cert verification
    context = None
    if sys.version_info[:3] > (2, 7, 8):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    stub = service_instance._stub
    vc_mos = vsanapiutils.GetVsanVcMos(stub, context=context)
    return vc_mos['vsan-cluster-config-system']


def get_vsan_disk_management_system(service_instance):
    '''
    Returns a vim.VimClusterVsanVcDiskManagementSystem object

    service_instance
        Service instance to the host or vCenter
    '''

    #TODO Replace when better connection mechanism is available

    #For python 2.7.9 and later, the defaul SSL conext has more strict
    #connection handshaking rule. We may need turn of the hostname checking
    #and client side cert verification
    context = None
    if sys.version_info[:3] > (2, 7, 8):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    stub = service_instance._stub
    vc_mos = vsanapiutils.GetVsanVcMos(stub, context=context)
    return vc_mos['vsan-disk-management-system']


def get_host_vsan_system(service_instance, host_ref, hostname=None):
    '''
    Returns a host's vsan system

    service_instance
        Service instance to the host or vCenter

    host_ref
        Refernce to ESXi host

    hostname
        Name of ESXi host. Default value is None.
    '''
    if not hostname:
        hostname = salt.utils.vmware.get_managed_object_name(host_ref)
    traversal_spec = vmodl.query.PropertyCollector.TraversalSpec(
        path='configManager.vsanSystem',
        type=vim.HostSystem,
        skip=False)
    objs = salt.utils.vmware.get_mors_with_properties(
        service_instance, vim.HostVsanSystem, property_list=['config.enabled'],
        container_ref=host_ref, traversal_spec=traversal_spec)
    if not objs:
        raise VMwareObjectRetrievalError('Host\'s \'{0}\' VSAN system was '
                                         'not retrieved'.format(hostname))
    log.trace('[%s] Retrieved VSAN system', hostname)
    return objs[0]['object']


def create_diskgroup(service_instance, vsan_disk_mgmt_system,
                     host_ref, cache_disk, capacity_disks):
    '''
    Creates a disk group

    service_instance
        Service instance to the host or vCenter

    vsan_disk_mgmt_system
        vim.VimClusterVsanVcDiskManagemenetSystem representing the vSan disk
        management system retrieved from the vsan endpoint.

    host_ref
        vim.HostSystem object representing the target host the disk group will
        be created on

    cache_disk
        The vim.HostScsidisk to be used as a cache disk. It must be an ssd disk.

    capacity_disks
        List of vim.HostScsiDisk objects representing of disks to be used as
        capacity disks. Can be either ssd or non-ssd. There must be a minimum
        of 1 capacity disk in the list.
    '''
    hostname = salt.utils.vmware.get_managed_object_name(host_ref)
    cache_disk_id = cache_disk.canonicalName
    log.debug(
        'Creating a new disk group with cache disk \'%s\' on host \'%s\'',
        cache_disk_id, hostname
    )
    log.trace('capacity_disk_ids = %s', [c.canonicalName for c in capacity_disks])
    spec = vim.VimVsanHostDiskMappingCreationSpec()
    spec.cacheDisks = [cache_disk]
    spec.capacityDisks = capacity_disks
    # All capacity disks must be either ssd or non-ssd (mixed disks are not
    # supported)
    spec.creationType = 'allFlash' if getattr(capacity_disks[0], 'ssd') \
            else 'hybrid'
    spec.host = host_ref
    try:
        task = vsan_disk_mgmt_system.InitializeDiskMappings(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.fault.MethodNotFound as exc:
        log.exception(exc)
        raise VMwareRuntimeError('Method \'{0}\' not found'.format(exc.method))
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    _wait_for_tasks([task], service_instance)
    return True


def add_capacity_to_diskgroup(service_instance, vsan_disk_mgmt_system,
                              host_ref, diskgroup, new_capacity_disks):
    '''
    Adds capacity disk(s) to a disk group.

    service_instance
        Service instance to the host or vCenter

    vsan_disk_mgmt_system
        vim.VimClusterVsanVcDiskManagemenetSystem representing the vSan disk
        management system retrieved from the vsan endpoint.

    host_ref
        vim.HostSystem object representing the target host the disk group will
        be created on

    diskgroup
        The vsan.HostDiskMapping object representing the host's diskgroup where
        the additional capacity needs to be added

    new_capacity_disks
        List of vim.HostScsiDisk objects representing the disks to be added as
        capacity disks. Can be either ssd or non-ssd. There must be a minimum
        of 1 new capacity disk in the list.
    '''
    hostname = salt.utils.vmware.get_managed_object_name(host_ref)
    cache_disk = diskgroup.ssd
    cache_disk_id = cache_disk.canonicalName
    log.debug(
        'Adding capacity to disk group with cache disk \'%s\' on host \'%s\'',
        cache_disk_id, hostname
    )
    log.trace(
        'new_capacity_disk_ids = %s',
        [c.canonicalName for c in new_capacity_disks]
    )
    spec = vim.VimVsanHostDiskMappingCreationSpec()
    spec.cacheDisks = [cache_disk]
    spec.capacityDisks = new_capacity_disks
    # All new capacity disks must be either ssd or non-ssd (mixed disks are not
    # supported); also they need to match the type of the existing capacity
    # disks; we assume disks are already validated
    spec.creationType = 'allFlash' if getattr(new_capacity_disks[0], 'ssd') \
            else 'hybrid'
    spec.host = host_ref
    try:
        task = vsan_disk_mgmt_system.InitializeDiskMappings(spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.fault.MethodNotFound as exc:
        log.exception(exc)
        raise VMwareRuntimeError('Method \'{0}\' not found'.format(exc.method))
    except vmodl.RuntimeFault as exc:
        raise VMwareRuntimeError(exc.msg)
    _wait_for_tasks([task], service_instance)
    return True


def remove_capacity_from_diskgroup(service_instance, host_ref, diskgroup,
                                   capacity_disks, data_evacuation=True,
                                   hostname=None,
                                   host_vsan_system=None):
    '''
    Removes capacity disk(s) from a disk group.

    service_instance
        Service instance to the host or vCenter

    host_vsan_system
        ESXi host's VSAN system

    host_ref
        Reference to the ESXi host

    diskgroup
        The vsan.HostDiskMapping object representing the host's diskgroup from
        where the capacity needs to be removed

    capacity_disks
        List of vim.HostScsiDisk objects representing the capacity disks to be
        removed. Can be either ssd or non-ssd. There must be a minimum
        of 1 capacity disk in the list.

    data_evacuation
        Specifies whether to gracefully evacuate the data on the capacity disks
        before removing them from the disk group. Default value is True.

    hostname
        Name of ESXi host. Default value is None.

    host_vsan_system
        ESXi host's VSAN system. Default value is None.
    '''
    if not hostname:
        hostname = salt.utils.vmware.get_managed_object_name(host_ref)
    cache_disk = diskgroup.ssd
    cache_disk_id = cache_disk.canonicalName
    log.debug(
        'Removing capacity from disk group with cache disk \'%s\' on host \'%s\'',
        cache_disk_id, hostname
    )
    log.trace('capacity_disk_ids = %s',
              [c.canonicalName for c in capacity_disks])
    if not host_vsan_system:
        host_vsan_system = get_host_vsan_system(service_instance,
                                                host_ref, hostname)
    # Set to evacuate all data before removing the disks
    maint_spec = vim.HostMaintenanceSpec()
    maint_spec.vsanMode = vim.VsanHostDecommissionMode()
    if data_evacuation:
        maint_spec.vsanMode.objectAction = \
                vim.VsanHostDecommissionModeObjectAction.evacuateAllData
    else:
        maint_spec.vsanMode.objectAction = \
                vim.VsanHostDecommissionModeObjectAction.noAction
    try:
        task = host_vsan_system.RemoveDisk_Task(disk=capacity_disks,
                                                maintenanceSpec=maint_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    salt.utils.vmware.wait_for_task(task, hostname, 'remove_capacity')
    return True


def remove_diskgroup(service_instance, host_ref, diskgroup, hostname=None,
                     host_vsan_system=None, erase_disk_partitions=False,
                     data_accessibility=True):
    '''
    Removes a disk group.

    service_instance
        Service instance to the host or vCenter

    host_ref
        Reference to the ESXi host

    diskgroup
        The vsan.HostDiskMapping object representing the host's diskgroup from
        where the capacity needs to be removed

    hostname
        Name of ESXi host. Default value is None.

    host_vsan_system
        ESXi host's VSAN system. Default value is None.

    data_accessibility
        Specifies whether to ensure data accessibility. Default value is True.
    '''
    if not hostname:
        hostname = salt.utils.vmware.get_managed_object_name(host_ref)
    cache_disk_id = diskgroup.ssd.canonicalName
    log.debug('Removing disk group with cache disk \'%s\' on '
              'host \'%s\'', cache_disk_id, hostname)
    if not host_vsan_system:
        host_vsan_system = get_host_vsan_system(
            service_instance, host_ref, hostname)
    # Set to evacuate all data before removing the disks
    maint_spec = vim.HostMaintenanceSpec()
    maint_spec.vsanMode = vim.VsanHostDecommissionMode()
    object_action = vim.VsanHostDecommissionModeObjectAction
    if data_accessibility:
        maint_spec.vsanMode.objectAction = \
                object_action.ensureObjectAccessibility
    else:
        maint_spec.vsanMode.objectAction = object_action.noAction
    try:
        task = host_vsan_system.RemoveDiskMapping_Task(
            mapping=[diskgroup], maintenanceSpec=maint_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    salt.utils.vmware.wait_for_task(task, hostname, 'remove_diskgroup')
    log.debug('Removed disk group with cache disk \'%s\' on host \'%s\'',
              cache_disk_id, hostname)
    return True


def get_cluster_vsan_info(cluster_ref):
    '''
    Returns the extended cluster vsan configuration object
    (vim.VsanConfigInfoEx).

    cluster_ref
        Reference to the cluster
    '''

    cluster_name = salt.utils.vmware.get_managed_object_name(cluster_ref)
    log.trace('Retrieving cluster vsan info of cluster \'%s\'', cluster_name)
    si = salt.utils.vmware.get_service_instance_from_managed_object(
        cluster_ref)
    vsan_cl_conf_sys = get_vsan_cluster_config_system(si)
    try:
        return vsan_cl_conf_sys.VsanClusterGetConfig(cluster_ref)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)


def reconfigure_cluster_vsan(cluster_ref, cluster_vsan_spec):
    '''
    Reconfigures the VSAN system of a cluster.

    cluster_ref
        Reference to the cluster

    cluster_vsan_spec
        Cluster VSAN reconfigure spec (vim.vsan.ReconfigSpec).
    '''
    cluster_name = salt.utils.vmware.get_managed_object_name(cluster_ref)
    log.trace('Reconfiguring vsan on cluster \'%s\': %s',
              cluster_name, cluster_vsan_spec)
    si = salt.utils.vmware.get_service_instance_from_managed_object(
        cluster_ref)
    vsan_cl_conf_sys = salt.utils.vsan.get_vsan_cluster_config_system(si)
    try:
        task = vsan_cl_conf_sys.VsanClusterReconfig(cluster_ref,
                                                    cluster_vsan_spec)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    _wait_for_tasks([task], si)


def _wait_for_tasks(tasks, service_instance):
    '''
    Wait for tasks created via the VSAN API
    '''
    log.trace('Waiting for vsan tasks: {0}',
              ', '.join([six.text_type(t) for t in tasks]))
    try:
        vsanapiutils.WaitForTasks(tasks, service_instance)
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    log.trace('Tasks %s finished successfully',
              ', '.join([six.text_type(t) for t in tasks]))
