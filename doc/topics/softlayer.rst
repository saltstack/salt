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


The above items are all required; optional items may be added in future versions
of Salt Cloud.

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


The above items are all required; optional items may be added in future versions
of Salt Cloud.

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
