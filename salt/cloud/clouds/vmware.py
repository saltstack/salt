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
    from pyVmomi import vim
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


def _get_vm_list():
    '''
    Returns a list of all vms in the VMware environment
    '''
    # Get service instance object
    si = _get_si()

    # Create a object view
    obj_view = si.content.viewManager.CreateContainerView(si.content.rootFolder, [vim.VirtualMachine], True)

    vm_list = obj_view.view

    # Destroy the object view
    obj_view.Destroy()

    return vm_list


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

    # Get the inventory
    inv = _get_inv()

    for datacenter in inv.rootFolder.childEntity:
        if isinstance(datacenter, vim.Datacenter):
            # This is a datacenter
            datacenters.append(datacenter.name)

    return {'Datacenters': datacenters}


def list_clusters(kwargs=None, call=None):
    '''
    List all the clusters for each datacenter in this VMware environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_clusters my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_clusters function must be called with -f or --function.'
        )
        return False

    datacenters = {}

    # Get the inventory
    inv = _get_inv()

    for datacenter in inv.rootFolder.childEntity:
        if isinstance(datacenter, vim.Datacenter):
            # This is a datacenter
            clusters = []

            # Create a new view for each datacenter
            obj_view = inv.viewManager.CreateContainerView(datacenter, [], True)
            for cluster in obj_view.view:
                if isinstance(cluster, vim.ClusterComputeResource):
                    # This is a cluster
                    clusters.append(cluster.name)

            # Destroy the view after use for each datacenter
            obj_view.Destroy()

            datacenters[datacenter.name] = clusters
  
    return {'Datacenters': datacenters}


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

    # Get the inventory
    inv = _get_inv()

    for datacenter in inv.rootFolder.childEntity:
        if isinstance(datacenter, vim.Datacenter):
            # This is a datacenter
            for datastore_cluster in datacenter.datastoreFolder.childEntity:
                if isinstance(datastore_cluster, vim.StoragePod):
                    # This is a datastore cluster
                    datastore_clusters.append(datastore_cluster.name)
  
    return {'Datastore Clusters': datastore_clusters}


def list_datastores(kwargs=None, call=None):
    '''
    List all the datastores for this VMware environment

    .. note::

        If you have a lot of datastores in your environment, this may some time to return.

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

    # Get the inventory
    inv = _get_inv()

    # Create a object view
    obj_view = inv.viewManager.CreateContainerView(inv.rootFolder, [], True)
    for datastore in obj_view.view:
        if isinstance(datastore, vim.Datastore):
            # This is a datastore
            datastores.append(datastore.name)

    # Destroy the object view
    obj_view.Destroy()

    return {'Datastores': datastores}


def list_hosts(kwargs=None, call=None):
    '''
    List all the hosts for this VMware environment

    .. note::

        If you have a lot of hosts in your environment, this may some time to return.

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

    # Get the inventory
    inv = _get_inv()

    # Create a object view
    obj_view = inv.viewManager.CreateContainerView(inv.rootFolder, [], True)
    for host in obj_view.view:
        if isinstance(host, vim.HostSystem):
            # This is a host
            hosts.append(host.name)

    # Destroy the object view
    obj_view.Destroy()

    return {'Hosts': hosts}


def list_resourcepools(kwargs=None, call=None):
    '''
    List all the resource pools for this VMware environment

    .. note::

        If you have a lot of resource pools in your environment, this may some time to return.

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

    # Get the inventory
    inv = _get_inv()

    # Create a object view
    obj_view = inv.viewManager.CreateContainerView(inv.rootFolder, [], True)
    for resource_pool in obj_view.view:
        if isinstance(resource_pool, vim.ResourcePool):
            # This is a Resource Pool
            resource_pools.append(resource_pool.name)

    # Destroy the object view
    obj_view.Destroy()

    return {'Resource Pools': resource_pools}


def list_networks(kwargs=None, call=None):
    '''
    List all the standard networks for this VMware environment

    .. note::

        If you have a lot of networks in your environment, this may some time to return.

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

    # Get the inventory
    inv = _get_inv()

    # Create a object view
    obj_view = inv.viewManager.CreateContainerView(inv.rootFolder, [], True)
    for network in obj_view.view:
        if isinstance(network, vim.Network):
            # This is a network
            networks.append(network.name)

    # Destroy the object view
    obj_view.Destroy()

    return {'Networks': networks}


def list_nodes_min(kwargs=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with no details

    .. note::

        The list returned does not include templates.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-vmware-config
    '''
    if call != 'function':
        log.error(
            'The list_nodes_min function must be called with -f or --function.'
        )
        return False

    ret = {}
    vm_list = _get_vm_list()

    for vm in vm_list:
        if not vm.summary.config.template:
            # It is not a template
            ret[vm.name] = True

    return ret
