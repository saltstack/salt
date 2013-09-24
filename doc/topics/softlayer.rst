==============================
Getting Started With SoftLayer
==============================

SoftLayer is a public cloud provider, and baremetal hardware hosting provider.

Dependencies
============
The SoftLayer driver for Salt Cloud requires the softlayer package, which is
available at PyPi:

https://pypi.python.org/pypi/SoftLayer

This package can be installed using `pip` or `easy_install`:

.. code-block:: bash

  # pip install softlayer
  # easy_install softlayer


Configuration
=============
Set up the cloud config at ``/etc/salt/cloud.providers``:

.. code-block:: yaml

  # Note: These examples are for /etc/salt/cloud.providers

    my-softlayer:
      # Set up the location of the salt master
      minion:
        master: saltmaster.example.com

      # Set the SoftLayer access credentials (see below)
      user: MYUSER1138
      apikey: 'e3b68aa711e6deadc62d5b76355674beef7cc3116062ddbacafe5f7e465bfdc9'

      provider: softlayer


    my-softlayer-hw:
      # Set up the location of the salt master
      minion:
        master: saltmaster.example.com

      # Set the SoftLayer access credentials (see below)
      user: MYUSER1138
      apikey: 'e3b68aa711e6deadc62d5b76355674beef7cc3116062ddbacafe5f7e465bfdc9'

      provider: softlayer-hw


Access Credentials
==================
The `user` setting is the same user as is used to log into the SoftLayer
Administration area. The `apikey` setting is found inside the Admin area after
logging in:

* Hover over the `Administrative` menu item.
* Click the `API Access` link.
* The `apikey` is located next to the `user` setting.


Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_softlayer_ubuntu:
      provider: my-softlayer
      image: UBUNTU_LATEST
      cpu_number: 1
      ram: 1024
      disk_size: 100
      local_disk: True
      hourly_billing: True
      domain: example.com
      location: sjc01
      # Optional
      max_net_speed: 1000
      private_vlan: 396
      private_network: True
      private_ssh: True


Most of the above items are required; optional items are specified below.

image
-----
Images to build an instance can be found using the `--list-images` option:

.. code-block:: bash

    # salt-cloud --list-images my-softlayer

The setting used will be labeled as `template`.

cpu_number
----------
This is the number of CPU cores that will be used for this instance. This
number may be dependent upon the image that is used. For instance:

.. code-block:: yaml

    Red Hat Enterprise Linux 6 - Minimal Install (64 bit) (1 - 4 Core):
        ----------
        name:
            Red Hat Enterprise Linux 6 - Minimal Install (64 bit) (1 - 4 Core)
        template:
            REDHAT_6_64
    Red Hat Enterprise Linux 6 - Minimal Install (64 bit) (5 - 100 Core):
        ----------
        name:
            Red Hat Enterprise Linux 6 - Minimal Install (64 bit) (5 - 100 Core)
        template:
            REDHAT_6_64

Note that the template (meaning, the `image` option) for both of these is the
same, but the names suggests how many CPU cores are supported.

ram
---
This is the amount of memory, in megabytes, that will be allocated to this
instance.

disk_size
---------
The amount of disk space that will be allocated to this image, in megabytes.

local_disk
----------
When true the disks for the computing instance will be provisioned on the host
which it runs, otherwise SAN disks will be provisioned.

hourly_billing
--------------
When true the computing instance will be billed on hourly usage, otherwise it
will be billed on a monthly basis.

domain
------
The domain name that will be used in the FQDN (Fully Qualified Domain Name) for
this instance. The `domain` setting will be used in conjunction with the
instance name to form the FQDN.

location
--------
Images to build an instance can be found using the `--list-locations` option:

.. code-block:: bash

    # salt-cloud --list-location my-softlayer

max_net_speed
-------------
Specifies the connection speed for the instance's network components. This
setting is optional. By default, this is set to 10.

public_vlan
-----------
If it is necessary for an instance to be created within a specific frontend
VLAN, the ID for that VLAN can be specified in either the provider or profile
configuration.

This ID can be queried using the `list_vlans` function, as described below. This
setting is optional.

private_vlan
------------
If it is necessary for an instance to be created within a specific backend VLAN,
the ID for that VLAN can be specified in either the provider or profile
configuration.

This ID can be queried using the `list_vlans` function, as described below. This
setting is optional.

private_network
---------------
If a server is to only be used internally, meaning it does not have a public
VLAN associated with it, this value would be set to True. This setting is
optional. The default is False.

private_ssh
-----------
Whether to run the deploy script on the server using the public IP address
or the private IP address. If set to True, Salt Cloud will attempt to SSH into
the new server using the private IP address. The default is False. This
settions is optional.


The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p base_softlayer_ubuntu myserver

Using the above configuration, this will create `myserver.example.com`.

Once the instance has been created with salt-minion installed, connectivity to 
it can be verified with Salt:

.. code-block:: bash

    # salt 'myserver.example.com' test.ping


Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    base_softlayer_hw_centos:
      provider: my-softlayer-hw
      # CentOS 6.0 - Minimal Install (64 bit)
      image: 13963
      # 2 x 2.0 GHz Core Bare Metal Instance - 2 GB Ram
      size: 1921
      # 250GB SATA II
      hdd: 19
      # San Jose 01
      location: 168642
      domain: example.com
      # Optional
      vlan: 396
      port_speed: 273
      banwidth: 248


Most of the above items are required; optional items are specified below.

image
-----
Images to build an instance can be found using the `--list-images` option:

.. code-block:: bash

    # salt-cloud --list-images my-softlayer-hw

A list of `id`s and names will be provided. The `name` will describe the
operating system and architecture. The `id` will be the setting to be used in
the profile.

size
----
Sizes to build an instance can be found using the `--list-sizes` option:

.. code-block:: bash

    # salt-cloud --list-sizes my-softlayer-hw

A list of `id`s and names will be provided. The `name` will describe the speed
and quantity of CPU cores, and the amount of memory that the hardware will
contain. The `id` will be the setting to be used in the profile.


hdd
---
There are currently two sizes of hard disk drive (HDD) that are available for
hardware instances on SoftLayer:

.. code-block:: yaml

    19: 250GB SATA II
    1267: 500GB SATA II

The `hdd` setting in the profile will be either 19 or 1267. Other sizes may be
added in the future.

location
--------
Locations to build an instance can be found using the `--list-images` option:

.. code-block:: bash

    # salt-cloud --list-locations my-softlayer-hw

A list of IDs and names will be provided. The `location` will describe the
location in human terms. The `id` will be the setting to be used in the profile.

domain
------
The domain name that will be used in the FQDN (Fully Qualified Domain Name) for
this instance. The `domain` setting will be used in conjunction with the
instance name to form the FQDN.

vlan
----
If it is necessary for an instance to be created within a specific VLAN, the ID
for that VLAN can be specified in either the provider or profile configuration.

This ID can be queried using the `list_vlans` function, as described below.

port_speed
----------
Specifies the speed for the instance's network port. This setting refers to an
ID within the SoftLayer API, which sets the port speed. This setting is
optional. The default is 273, or, 100 Mbps Public & Private Networks. The
following settings are available:

* 273: 100 Mbps Public & Private Networks
* 274: 1 Gbps Public & Private Networks
* 21509: 10 Mbps Dual Public & Private Networks (up to 20 Mbps)
* 21513: 100 Mbps Dual Public & Private Networks (up to 200 Mbps)
* 2314: 1 Gbps Dual Public & Private Networks (up to 2 Gbps)
* 272: 10 Mbps Public & Private Networks

bandwidth
---------
Specifies the network bandwidth available for the instance. This setting refers
to an ID within the SoftLayer API, which sets the bandwidth. This setting is
optional. The default is 248, or, 5000 GB Bandwidth. The following settings are
available:

* 248: 5000 GB Bandwidth
* 129: 6000 GB Bandwidth
* 130: 8000 GB Bandwidth
* 131: 10000 GB Bandwidth
* 36: Unlimited Bandwidth (10 Mbps Uplink)
* 125: Unlimited Bandwidth (100 Mbps Uplink)


Actions
=======
The following actions are currently supported by the SoftLayer Salt Cloud
driver.

show_instance
-------------
This action is a thin wrapper around `--full-query`, which displays details on a 
single instance only. In an environment with several machines, this will save a 
user from having to sort through all instance data, just to examine a single 
instance.

.. code-block:: bash

    $ salt-cloud -a show_instance myinstance


Functions
=========
The following functions are currently supported by the SoftLayer Salt Cloud
driver.

list_vlans
----------
This function lists all VLANs associated with the account, and all known data
from the SoftLayer API concerning those VLANs.

.. code-block:: bash

    $ salt-cloud -f list_vlans my-softlayer
    $ salt-cloud -f list_vlans my-softlayer-hw

The `id` returned in this list is necessary for the `vlan` option when creating
an instance.


Optional Products for SoftLayer HW
==================================
The softlayer-hw provider supports the ability to add optional products, which
are supported by SoftLayer's API. These products each have an ID associated with
them, that can be passed into Salt Cloud with the `optional_products` option:

.. code-block:: yaml

    softlayer_hw_test:
      provider: my-softlayer-hw
      # CentOS 6.0 - Minimal Install (64 bit)
      image: 13963
      # 2 x 2.0 GHz Core Bare Metal Instance - 2 GB Ram
      size: 1921
      # 250GB SATA II
      hdd: 19
      # San Jose 01
      location: 168642
      domain: example.com
      optional_products:
        # MySQL for Linux
        - id: 28
        # Business Continuance Insurance
        - id: 104

These values can be manually obtained by looking at the source of an order page
on the SoftLayer web interface. For convenience, many of these values are listed
here:

Public Secondary IP Addresses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 22: 4 Public IP Addresses    
* 23: 8 Public IP Addresses     

Primary IPv6 Addresses
~~~~~~~~~~~~~~~~~~~~~~
* 17129: 1 IPv6 Address    

Public Static IPv6 Addresses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 1481: /64 Block Static Public IPv6 Addresses    

OS-Specific Addon
~~~~~~~~~~~~~~~~~
* 17139: XenServer Advanced for XenServer 6.x
* 17141: XenServer Enterprise for XenServer 6.x
* 2334: XenServer Advanced for XenServer 5.6
* 2335: XenServer Enterprise for XenServer 5.6
* 13915: Microsoft WebMatrix
* 21276: VMware vCenter 5.1 Standard

Control Panel Software
~~~~~~~~~~~~~~~~~~~~~~
* 121: cPanel/WHM with Fantastico and RVskin
* 20778: Parallels Plesk Panel 11 (Linux) 100 Domain w/ Power Pack
* 20786: Parallels Plesk Panel 11 (Windows) 100 Domain w/ Power Pack
* 20787: Parallels Plesk Panel 11 (Linux) Unlimited Domain w/ Power Pack
* 20792: Parallels Plesk Panel 11 (Windows) Unlimited Domain w/ Power Pack
* 2340: Parallels Plesk Panel 10 (Linux) 100 Domain w/ Power Pack
* 2339: Parallels Plesk Panel 10 (Linux) Unlimited Domain w/ Power Pack
* 13704: Parallels Plesk Panel 10 (Windows) Unlimited Domain w/ Power Pack

Database Software
~~~~~~~~~~~~~~~~~
* 29: MySQL 5.0 for Windows
* 28: MySQL for Linux
* 21501: Riak 1.x
* 20893: MongoDB
* 30: Microsoft SQL Server 2005 Express
* 92: Microsoft SQL Server 2005 Workgroup
* 90: Microsoft SQL Server 2005 Standard
* 94: Microsoft SQL Server 2005 Enterprise
* 1330: Microsoft SQL Server 2008 Express
* 1340: Microsoft SQL Server 2008 Web
* 1337: Microsoft SQL Server 2008 Workgroup
* 1334: Microsoft SQL Server 2008 Standard
* 1331: Microsoft SQL Server 2008 Enterprise
* 2179: Microsoft SQL Server 2008 Express R2
* 2173: Microsoft SQL Server 2008 Web R2
* 2183: Microsoft SQL Server 2008 Workgroup R2
* 2180: Microsoft SQL Server 2008 Standard R2
* 2176: Microsoft SQL Server 2008 Enterprise R2

Anti-Virus & Spyware Protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 594: McAfee VirusScan Anti-Virus - Windows
* 414: McAfee Total Protection - Windows

Insurance
~~~~~~~~~
* 104: Business Continuance Insurance

Monitoring
~~~~~~~~~~
* 55: Host Ping
* 56: Host Ping and TCP Service Monitoring

Notification
~~~~~~~~~~~~
* 57: Email and Ticket

Advanced Monitoring
~~~~~~~~~~~~~~~~~~~
* 2302: Monitoring Package - Basic
* 2303: Monitoring Package - Advanced
* 2304: Monitoring Package - Premium Application

Response
~~~~~~~~
* 58: Automated Notification
* 59: Automated Reboot from Monitoring
* 60: 24x7x365 NOC Monitoring, Notification, and Response

Intrusion Detection & Protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 413: McAfee Host Intrusion Protection w/Reporting

Hardware & Software Firewalls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 411: APF Software Firewall for Linux
* 894: Microsoft Windows Firewall
* 410: 10Mbps Hardware Firewall
* 409: 100Mbps Hardware Firewall
* 408: 1000Mbps Hardware Firewall

