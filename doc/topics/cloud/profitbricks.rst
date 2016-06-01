=================================
Getting Started With ProfitBricks
=================================

ProfitBricks provides an enterprise-grade Infrastructure as a Service (IaaS)
solution that can be managed through a browser-based "Data Center Designer"
(DCD) tool or via an easy to use API. A unique feature of the ProfitBricks
platform is that it allows you to define your own settings for cores, memory,
and disk size without being tied to a particular instance size.

Dependencies
============

* profitbricks >= 2.3.0

Configuration
=============

* Using the new format, set up the cloud configuration at
  ``/etc/salt/cloud.providers`` or
  ``/etc/salt/cloud.providers.d/profitbricks.conf``:

.. code-block:: yaml

    my-profitbricks-config:
      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure ProfitBricks authentication credentials
      #
      username: user@domain.com
      password: 123456
      # datacenter is the UUID of a pre-existing virtual data center.
      datacenter: 9e6709a0-6bf9-4bd6-8692-60349c70ce0e
      # Connect to public LAN ID 1.
      public_lan: 1
      ssh_public_key: /path/to/id_rsa.pub
      ssh_private_key: /path/to/id_rsa

      driver: profitbricks


.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.


Virtual Data Center
===================

ProfitBricks uses the concept of Virtual Data Centers. These are logically
separated from one another and allow you to have a self-contained environment
for all servers, volumes, networking, snapshots, and so forth.

A list of existing virtual data centers can be retrieved with the following command:

.. code-block:: bash

    salt-cloud -f list_datacenters my-profitbricks-config

Authentication
==============

The ``username`` and ``password`` are the same as those used to log into the
ProfitBricks "Data Center Designer".

Profiles
========

Here is an example of a profile:

.. code-block:: yaml

    profitbricks_production:
      provider: my-profitbricks-config
      size: Micro Instance
      image: 2f98b678-6e7e-11e5-b680-52540066fee9
      disk_size: 10
      disk_type: SSD
      cores: 2
      ram: 4096
      public_lan: 1
      private_lan: 2
      ssh_public_key: /path/to/id_rsa.pub
      ssh_private_key: /path/to/id_rsa
      ssh_interface: private_lan

The following list explains some of the important properties.

size
    Can be one of the options listed in the output of the following command:

.. code-block:: bash

    salt-cloud --list-sizes my-profitbricks

image
    Can be one of the options listed in the output of the following command:

.. code-block:: bash

    salt-cloud --list-images my-profitbricks

disk_size
    This option allows you to override the size of the disk as defined by the
    size. The disk size is set in gigabytes (GB).

disk_type
    This option allow the disk type to be set to HDD or SSD. The default is
    HDD.

cores
    This option allows you to override the number of CPU cores as defined by
    the size.

ram
    This option allows you to override the amount of RAM defined by the size.
    The value must be a multiple of 256, e.g. 256, 512, 768, 1024, and so
    forth.

public_lan
    This option will connect the instance to the specified public LAN. If no
    LAN exists, then a new public LAN will be created. The value accepts a LAN
    ID (integer).
    
private_lan
    This option will connect the instance to the specified private LAN. If no
    LAN exists, then a new private LAN will be created. The value accepts a LAN
    ID (integer).

ssh_private_key
    Full path to the SSH private key file.

ssh_public_key
    Full path to the SSH public key file.

ssh_interface
    This option will use the private LAN IP for node connections (such as
    as bootstrapping the node) instead of the public LAN IP. The value accepts
    'private_lan'.

deploy
    Set to False if Salt should not be installed on the node.

wait_for_timeout
    The timeout to wait in seconds for provisioning resources such as servers.
    The default wait_for_timeout is 15 minutes.

For more information concerning cloud profiles, see :doc:`here
</topics/cloud/profiles>`.
