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


def _get_inv():
    '''
    Authenticate with vCenter server and return its inventory.
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

    return si.RetrieveContent()


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
    List the data centers for this VMware environment

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
    List the clusters for this VMware environment

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
            for cluster in datacenter.hostFolder.childEntity:
                if isinstance(cluster, vim.ClusterComputeResource):
                    # This is a cluster
                    clusters.append(cluster.name)
            datacenters[datacenter.name] = { 'Clusters': clusters}
  
    return {'Datacenters': datacenters}


def list_datastore_clusters(kwargs=None, call=None):
    '''
    List the datastore clusters for this VMware environment

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


def list_hosts(kwargs=None, call=None):
    '''
    List the hosts for this VMware environment

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
    object_view = inv.viewManager.CreateContainerView(inv.rootFolder, [], True)
    for host in object_view.view:
        if isinstance(host, vim.HostSystem):
            # This is a host
            hosts.append(host.name)

    # Destroy the object view
    object_view.Destroy()

    return {'Hosts': hosts}
