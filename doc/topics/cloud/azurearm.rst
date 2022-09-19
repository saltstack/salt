==============================
Getting Started With Azure ARM
==============================

.. versionadded:: 2016.11.0

.. warning::

    This cloud provider will be removed from Salt in version 3007 in favor of
    the `saltext.azurerm Salt Extension
    <https://github.com/salt-extensions/saltext-azurerm>`_

Azure is a cloud service by Microsoft providing virtual machines, SQL services,
media services, and more. Azure ARM (aka, the Azure Resource Manager) is a next
generation version of the Azure portal and API. This document describes how to
use Salt Cloud to create a virtual machine on Azure ARM, with Salt installed.

More information about Azure is located at `http://www.windowsazure.com/
<http://www.windowsazure.com/>`_.


Dependencies
============
* `azure <https://pypi.org/project/azure>`_ >= 2.0.0rc6
* `azure-common <https://pypi.org/project/azure-common>`_ >= 1.1.4
* `azure-mgmt <https://pypi.org/project/azure-mgmt>`_ >= 0.30.0rc6
* `azure-mgmt-compute <https://pypi.org/project/azure-mgmt-compute>`_ >= 0.33.0
* `azure-mgmt-network <https://pypi.org/project/azure-mgmt-network>`_ >= 0.30.0rc6
* `azure-mgmt-resource <https://pypi.org/project/azure-mgmt-resource>`_ >= 0.30.0
* `azure-mgmt-storage <https://pypi.org/project/azure-mgmt-storage>`_ >= 0.30.0rc6
* `azure-mgmt-web <https://pypi.org/project/azure-mgmt-web>`_ >= 0.30.0rc6
* `azure-storage <https://pypi.org/project/azure-storage>`_ >= 0.32.0
* `msrestazure <https://pypi.org/project/msrestazure/>`_ >= 0.4.21
* A Microsoft Azure account
* `Salt <https://github.com/saltstack/salt>`_


Installation Tips
=================
Because the ``azure`` library requires the ``cryptography`` library, which is
compiled on-the-fly by ``pip``, you may need to install the development tools
for your operating system.

Before you install ``azure`` with ``pip``, you should make sure that the
required libraries are installed.

Debian
------
For Debian and Ubuntu, the following command will ensure that the required
dependencies are installed:

.. code-block:: bash

    sudo apt-get install build-essential libssl-dev libffi-dev python-dev

Red Hat
-------
For Fedora and RHEL-derivatives, the following command will ensure that the
required dependencies are installed:

.. code-block:: bash

    sudo yum install gcc libffi-devel python-devel openssl-devel


Configuration
=============

Set up the provider config at ``/etc/salt/cloud.providers.d/azurearm.conf``:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers.d/azurearm.conf

    my-azurearm-config:
      driver: azurearm
      master: salt.example.com
      subscription_id: 01234567-890a-bcde-f012-34567890abdc

      # https://apps.dev.microsoft.com/#/appList
      username: <username>@<subdomain>.onmicrosoft.com
      password: verybadpass
      location: westus
      resource_group: my_rg

      # Optional
      network_resource_group: my_net_rg
      cleanup_disks: True
      cleanup_vhds: True
      cleanup_data_disks: True
      cleanup_interfaces: True
      custom_data: 'This is custom data'
      expire_publisher_cache: 604800  # 7 days
      expire_offer_cache: 518400  # 6 days
      expire_sku_cache: 432000  # 5 days
      expire_version_cache: 345600  # 4 days
      expire_group_cache: 14400  # 4 hours
      expire_interface_cache: 3600  # 1 hour
      expire_network_cache: 3600  # 1 hour

Cloud Profiles
==============
Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    azure-ubuntu-pass:
      provider: my-azure-config
      image: Canonical|UbuntuServer|14.04.5-LTS|14.04.201612050
      size: Standard_D1_v2
      location: eastus
      ssh_username: azureuser
      ssh_password: verybadpass

    azure-ubuntu-key:
      provider: my-azure-config
      image: Canonical|UbuntuServer|14.04.5-LTS|14.04.201612050
      size: Standard_D1_v2
      location: eastus
      ssh_username: azureuser
      ssh_publickeyfile: /path/to/ssh_public_key.pub

    azure-win2012:
      provider: my-azure-config
      image: MicrosoftWindowsServer|WindowsServer|2012-R2-Datacenter|latest
      size: Standard_D1_v2
      location: westus
      win_username: azureuser
      win_password: verybadpass

These options are described in more detail below. Once configured, the profile
can be realized with a salt command:

.. code-block:: bash

    salt-cloud -p azure-ubuntu newinstance

This will create an salt minion instance named ``newinstance`` in Azure. If
the command was executed on the salt-master, its Salt key will automatically
be signed on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt newinstance test.version


Profile Options
===============
The following options are currently available for Azure ARM.

provider
--------
The name of the provider as configured in
`/etc/salt/cloud.providers.d/azure.conf`.

image
-----
Required. The name of the image to use to create a VM. Available images can be
viewed using the following command:

.. code-block:: bash

    salt-cloud --list-images my-azure-config

As you will see in ``--list-images``, image names are comprised of the following
fields, separated by the pipe (``|``) character:

.. code-block:: yaml

    publisher: For example, Canonical or MicrosoftWindowsServer
    offer: For example, UbuntuServer or WindowsServer
    sku: Such as 14.04.5-LTS or 2012-R2-Datacenter
    version: Such as 14.04.201612050 or latest

It is possible to specify the URL or resource ID path of a custom image that you
have access to, such as:

.. code-block:: yaml

    https://<mystorage>.blob.core.windows.net/system/Microsoft.Compute/Images/<mystorage>/template-osDisk.01234567-890a-bcdef0123-4567890abcde.vhd

or:

.. code-block:: yaml

    /subscriptions/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX/resourceGroups/myRG/providers/Microsoft.Compute/images/myImage

size
----
Required. The name of the size to use to create a VM. Available sizes can be
viewed using the following command:

.. code-block:: bash

    salt-cloud --list-sizes my-azure-config

location
--------
Required. The name of the location to create a VM in. Available locations can
be viewed using the following command:

.. code-block:: bash

    salt-cloud --list-locations my-azure-config

ssh_username
------------
Required for Linux. The admin user to add on the instance. It is also used to log
into the newly-created VM to install Salt.

ssh_keyfile
-----------
Required if using SSH key authentication. The path on the Salt master to the SSH private
key used during the minion bootstrap process.

ssh_publickeyfile
-----------------
Use either ``ssh_publickeyfile`` or ``ssh_password``. The path on the Salt master to the
SSH public key which will be pushed to the Linux VM.

ssh_password
------------
Use either ``ssh_publickeyfile`` or ``ssh_password``. The password for the admin user on
the newly-created Linux virtual machine.

win_username
------------
Required for Windows. The user to use to log into the newly-created Windows VM
to install Salt.

win_password
------------
Required for Windows. The password to use to log into the newly-created Windows
VM to install Salt.

win_installer
-------------
Required for Windows. The path to the Salt installer to be uploaded.

resource_group
--------------
Required. The resource group that all VM resources (VM, network interfaces,
etc) will be created in.

network_resource_group
----------------------
Optional. If specified, then the VM will be connected to the virtual network
in this resource group, rather than the parent resource group of the instance.
The VM interfaces and IPs will remain in the configured ``resource_group`` with
the VM.

network
-------
Required. The virtual network that the VM will be spun up in.

subnet
------
Optional. The subnet inside the virtual network that the VM will be spun up in.
Default is ``default``.

allocate_public_ip
------------------
Optional. Default is ``False``. If set to ``True``, a public IP will
be created and assigned to the VM.

load_balancer
-------------
Optional. The load-balancer for the VM's network interface to join. If
specified the backend_pool option need to be set.

backend_pool
------------
Optional. Required if the load_balancer option is set. The load-balancer's
Backend Pool the VM's network interface will join.

iface_name
----------
Optional. The name to apply to the VM's network interface. If not supplied, the
value will be set to ``<VM name>-iface0``.

dns_servers
-----------
Optional. A **list** of the DNS servers to configure for the network interface
(will be set on the VM by the DHCP of the VNET).

.. code-block:: yaml

    my-azurearm-profile:
      provider: azurearm-provider
      network: mynetwork
      dns_servers:
        - 10.1.1.4
        - 10.1.1.5

availability_set
----------------
Optional. If set, the VM will be added to the specified availability set.

volumes
-------

Optional. A list of dictionaries describing data disks to attach to the
instance can be specified using this setting. The data disk dictionaries are
passed entirely to the `Azure DataDisk object
<https://docs.microsoft.com/en-us/python/api/azure.mgmt.compute.v2017_12_01.models.datadisk?view=azure-python>`_,
so ad-hoc options can be handled as long as they are valid properties of the
object.

.. code-block:: yaml

    volumes:
    - disk_size_gb: 50
      caching: ReadWrite
    - disk_size_gb: 100
      caching: ReadWrite
      managed_disk:
        storage_account_type: Standard_LRS

cleanup_disks
-------------
Optional. Default is ``False``. If set to ``True``, disks will be cleaned up
when the VM that they belong to is deleted.

cleanup_vhds
------------
Optional. Default is ``False``. If set to ``True``, VHDs will be cleaned up
when the VM and disk that they belong to are deleted. Requires ``cleanup_disks``
to be set to ``True``.

cleanup_data_disks
------------------
Optional. Default is ``False``. If set to ``True``, data disks (non-root
volumes) will be cleaned up whtn the VM that they are attached to is deleted.
Requires ``cleanup_disks`` to be set to ``True``.

cleanup_interfaces
------------------
Optional. Default is ``False``. Normally when a VM is deleted, its associated
interfaces and IPs are retained. This is useful if you expect the deleted VM
to be recreated with the same name and network settings. If you would like
interfaces and IPs to be deleted when their associated VM is deleted, set this
to ``True``.

userdata
--------
Optional. Any custom cloud data that needs to be specified. How this data is
used depends on the operating system and image that is used. For instance,
Linux images that use ``cloud-init`` will import this data for use with that
program. Some Windows images will create a file with a copy of this data, and
others will ignore it. If a Windows image creates a file, then the location
will depend upon the version of Windows. This will be ignored if the
``userdata_file`` is specified.

userdata_file
-------------
Optional. The path to a file to be read and submitted to Azure as user data.
How this is used depends on the operating system that is being deployed. If
used, any ``userdata`` setting will be ignored.

userdata_sendkeys
-----------------
Optional. Set to ``True`` in order to generate salt minion keys and provide
them as variables to the userdata script when running it through the template
renderer. The keys can be referenced as ``{{opts['priv_key']}}`` and
``{{opts['pub_key']}}``.

userdata_template
-----------------
Optional. Enter the renderer, such as ``jinja``, to be used for the userdata
script template.

wait_for_ip_timeout
-------------------
Optional. Default is ``600``. When waiting for a VM to be created, Salt Cloud
will attempt to connect to the VM's IP address until it starts responding. This
setting specifies the maximum time to wait for a response.

wait_for_ip_interval
--------------------
Optional. Default is ``10``. How long to wait between attempts to connect to
the VM's IP.

wait_for_ip_interval_multiplier
-------------------------------
Optional. Default is ``1``. Increase the interval by this multiplier after
each request; helps with throttling.

expire_publisher_cache
----------------------
Optional. Default is ``604800``. When fetching image data using
``--list-images``, a number of web calls need to be made to the Azure ARM API.
This is normally very fast when performed using a VM that exists inside Azure
itself, but can be very slow when made from an external connection.

By default, the publisher data will be cached, and only updated every ``604800``
seconds (7 days). If you need the publisher cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the publisher
cache.

expire_offer_cache
------------------
Optional. Default is ``518400``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the offer data will be cached, and only updated every ``518400``
seconds (6 days). If you need the offer cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the publiser
cache.

expire_sku_cache
----------------
Optional. Default is ``432000``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the sku data will be cached, and only updated every ``432000``
seconds (5 days). If you need the sku cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the sku
cache.

expire_version_cache
--------------------
Optional. Default is ``345600``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the version data will be cached, and only updated every ``345600``
seconds (4 days). If you need the version cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the version
cache.

expire_group_cache
------------------
Optional. Default is ``14400``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the resource group data will be cached, and only updated every
``14400`` seconds (4 hours). If you need the resource group cache to be updated
at a different frequency, change this setting. Setting it to ``0`` will turn
off the resource group cache.

expire_interface_cache
----------------------
Optional. Default is ``3600``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the interface data will be cached, and only updated every ``3600``
seconds (1 hour). If you need the interface cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the interface
cache.

expire_network_cache
--------------------
Optional. Default is ``3600``. See ``expire_publisher_cache`` for details on
why this exists.

By default, the network data will be cached, and only updated every ``3600``
seconds (1 hour). If you need the network cache to be updated at a different
frequency, change this setting. Setting it to ``0`` will turn off the network
cache.


Other Options
=============
Other options relevant to Azure ARM.

storage_account
---------------
Required for actions involving an Azure storage account.

storage_key
-----------
Required for actions involving an Azure storage account.


Show Instance
=============
This action is a thin wrapper around ``--full-query``, which displays details on
a single instance only. In an environment with several machines, this will save
a user from having to sort through all instance data, just to examine a single
instance.

.. code-block:: bash

    salt-cloud -a show_instance myinstance
