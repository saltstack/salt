==============================
Getting Started With Rackspace
==============================

Rackspace is a major public cloud platform which may be configured using either
the `rackspace` or the `openstack` driver, depending on your needs.

Please note that the `rackspace` driver is only intended for 1st gen instances,
aka, "the old cloud" at Rackspace. It is required for 1st gen instances, but
will *not* work with OpenStack-based instances. Unless you explicitly have a
reason to use it, it is highly recommended that you use the `openstack` driver
instead.


Dependencies
============
* Libcloud >= 0.13.2


Configuration
=============
To use the `openstack` driver (recommended), set up the cloud configuration at 
  ``/etc/salt/cloud.providers`` or 
  ``/etc/salt/cloud.providers.d/rackspace.conf``:

.. code-block:: yaml

    my-rackspace-config:
      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure Rackspace using the OpenStack plugin
      #
      identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
      compute_name: cloudServersOpenStack
      protocol: ipv4

      # Set the compute region:
      #
      compute_region: DFW

      # Configure Rackspace authentication credentials
      #
      user: myname
      tenant: 123456
      apikey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

      provider: openstack


To use the `rackspace` driver, set up the cloud configuration at 
  ``/etc/salt/cloud.providers`` or 
  ``/etc/salt/cloud.providers.d/rackspace.conf``:

.. code-block:: yaml

    my-rackspace-config:
      provider: rackspace
      # The Rackspace login user
      user: fred
      # The Rackspace user's apikey
      apikey: 901d3f579h23c8v73q9

The settings that follow are for using Rackspace with the `openstack` driver,
and will not work with the `rackspace` driver.


Compute Region
==============

Rackspace currently has six compute regions which may be used:

.. code-block:: bash

    DFW -> Dallas/Forth Worth
    ORD -> Chicago
    SYD -> Sydney
    LON -> London
    IAD -> Northern Virginia
    HKG -> Hong Kong

Note: Currently the LON region is only available with a UK account, and UK accounts cannot access other regions

Authentication
==============

The ``user`` is the same user as is used to log into the Rackspace Control 
Panel. The ``tenant`` and ``apikey`` can be found in the API Keys area of the 
Control Panel. The ``apikey`` will be labeled as API Key (and may need to be 
generated), and ``tenant`` will be labeled as Cloud Account Number.

An initial profile can be configured in ``/etc/salt/cloud.profiles`` or 
``/etc/salt/cloud.profiles.d/rackspace.conf``:

.. code-block:: yaml

    openstack_512:
        provider: my-rackspace-config
        size: 512 MB Standard
        image: Ubuntu 12.04 LTS (Precise Pangolin)

To instantiate a machine based on this profile:

.. code-block:: bash

    # salt-cloud -p openstack_512 myinstance

This will create a virtual machine at Rackspace with the name ``myinstance``.
This operation may take several minutes to complete, depending on the current 
load at the Rackspace data center.

Once the instance has been created with salt-minion installed, connectivity to 
it can be verified with Salt:

.. code-block:: bash

    # salt myinstance test.ping

RackConnect Environments
--------------------------------

Rackspace offers a hybrid hosting configuration option called RackConnect that
allows you to use a physical firewall appliance with your cloud servers. When
this service is in use the public_ip assigned by nova will be replaced by a NAT
ip on the firewall. For salt-cloud to work properly it must use the newly
assigned "access ip" instead of the Nova assigned public ip. You can enable that
capability by adding this to your profiles:

.. code-block:: yaml

    openstack_512:
        provider: my-openstack-config
        size: 512 MB Standard
        image: Ubuntu 12.04 LTS (Precise Pangolin)
        rackconnect: True

Managed Cloud Environments
--------------------------------

Rackspace offers a managed service level of hosting. As part of the managed
service level you have the ability to choose from base of lamp installations on
cloud server images.  The post build process for both the base and the lamp
installations used Chef to install things such as the cloud monitoring agent and
the cloud backup agent. It also takes care of installing the lamp stack if
selected. In order to prevent the post installation process from stomping over
the bootstrapping you can add the below to your profiles.

.. code-block:: yaml

    openstack_512:
        provider: my-rackspace-config
        size: 512 MB Standard
        image: Ubuntu 12.04 LTS (Precise Pangolin)
        managedcloud: True

First and Next Generation Images
--------------------------------

Rackspace provides two sets of virtual machine images, *first* and *next*
generation. As of ``0.8.9`` salt-cloud will default to using the *next*
generation images. To force the use of first generation images, on the profile 
configuration please add:

.. code-block:: yaml

    FreeBSD-9.0-512:
      provider: my-rackspace-config
      size: 512 MB Standard
      image: FreeBSD 9.0
      force_first_gen: True

