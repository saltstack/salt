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

    data_centers = []

    # Get the inventory
    inv = _get_inv()

    for object in inv.rootFolder.childEntity:
        if hasattr(object, 'vmFolder'):
          # This is a datacenter
          data_centers.append(object.name)

    return data_centers


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

    data_centers = {}

    # Get the inventory
    inv = _get_inv()

    for object in inv.rootFolder.childEntity:
        if hasattr(object, 'vmFolder'):
            # This is a datacenter
            datacenter = object.name
            clusters = []
            for cluster in object.hostFolder.childEntity:
                clusters.append(cluster.name)
            #data_centers.append(object.name)
            log.info(clusters)
            data_centers[datacenter] = clusters
  
    return data_centers
