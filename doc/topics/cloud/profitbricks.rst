=================================
Getting Started With ProfitBricks
=================================

ProfitBricks provides an enterprise-grade Infrastructure as a Service (IaaS)
solution that can be managed through a browser-based "Data Center Designer"
(DCD) tool or via an easy to use API. A unique feature of the ProfitBricks
platform is that it allows you to define your own settings for cores, memory,
and disk size without being tied to a particular server size.

Dependencies
============

* profitbricks >= 4.1.1

Configuration
=============

* Using the new format, set up the cloud configuration at
  ``/etc/salt/cloud.providers`` or
  ``/etc/salt/cloud.providers.d/profitbricks.conf``:

.. code-block:: yaml

    my-profitbricks-config:
      driver: profitbricks

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
      # delete_volumes is forcing a deletion of all volumes attached to a server on a deletion of a server
      delete_volumes: true
      # Connect to public LAN ID 1.
      public_lan: 1
      ssh_public_key: /path/to/id_rsa.pub
      ssh_private_key: /path/to/id_rsa


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

A new data center can be created with the following command:

.. code-block:: bash

    salt-cloud -f create_datacenter my-profitbricks-config name=example location=us/las description="my description"


Authentication
==============

The ``username`` and ``password`` are the same as those used to log into the
ProfitBricks "Data Center Designer".

Profiles
========

Here is an example of a profile:

.. code-block:: yaml

    profitbricks_staging
      provider: my-profitbricks-config
      size: Micro Instance
      image_alias: 'ubuntu:latest'
      # image or image_alias must be provided
      # image: 2f98b678-6e7e-11e5-b680-52540066fee9
      cores: 2
      ram: 4096
      public_lan: 1
      private_lan: 2
      ssh_public_key: /path/to/id_rsa.pub
      ssh_private_key: /path/to/id_rsa
      ssh_interface: private_lan

    profitbricks_production:
      provider: my-profitbricks-config
      image: Ubuntu-15.10-server-2016-05-01
      image_password: MyPassword1
      disk_type: SSD
      disk_size: 40
      cores: 8
      cpu_family: INTEL_XEON
      ram: 32768
      public_lan: 1
      public_ips:
        - 172.217.18.174
      private_lan: 2
      private_ips:
        - 192.168.100.10
      public_firewall_rules:
        Allow SSH:
          protocol: TCP
          source_ip: 1.2.3.4
          port_range_start: 22
          port_range_end: 22
        Allow Ping:
          protocol: ICMP
          icmp_type: 8
      ssh_public_key: /path/to/id_rsa.pub
      ssh_private_key: /path/to/id_rsa
      ssh_interface: private_lan
      volumes:
        db_data:
          disk_size: 500
        db_log:
          disk_size: 50
          disk_type: SSD

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations my-profitbricks-config

Images can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-profitbricks-config

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-profitbricks-config

.. versionchanged:: 2019.2.0

    One or more public IP address can be reserved with the following command:

    .. code-block:: bash

        # salt-cloud -f reserve_ipblock  my-profitbricks-config location='us/ewr' size=1

Profile Specifics:
------------------

The following list explains some of the important properties.

- ``size`` - Can be one of the options listed in the output of the following
  command:

  .. code-block:: bash

      salt-cloud --list-sizes my-profitbricks-config

- ``image`` - Can be one of the options listed in the output of the following
  command:

  .. code-block:: bash

      salt-cloud --list-images my-profitbricks-config

- ``image_alias`` - Can be one of the options listed in the output of the
  following command:

  .. code-block:: bash

     salt-cloud -f list_images my-profitbricks-config

- ``disk_size`` - This option allows you to override the size of the disk as
  defined by the size. The disk size is set in gigabytes (GB).

- ``disk_type`` - This option allow the disk type to be set to HDD or SSD. The
  default is HDD.

  .. versionadded:: 2019.2.0

- ``image_password`` - A password is set on the image for the "root" or
  "Administrator" account.  This field may only be set during volume creation.
  Only valid with ProfitBricks supplied HDD (not ISO) images. The password must
  contain at least 8 and no more than 50 characters. Only these characters are
  allowed: [a-z][A-Z][0-9]

- ``cores`` - This option allows you to override the number of CPU cores as
  defined by the size.

- ``ram`` - This option allows you to override the amount of RAM defined by the
  size. The value must be a multiple of 256, e.g. 256, 512, 768, 1024, and so
  forth.

- ``public_lan`` - This option will connect the server to the specified public
  LAN. If no LAN exists, then a new public LAN will be created. The value
  accepts a LAN ID (integer).

  .. versionadded:: 2019.2.0

- ``public_ips`` - Public IPs assigned to the NIC in the public LAN.

- ``public_firewall_rules`` - This option allows for a list of firewall rules
  assigned to the public network interface.

  .. code-block:: yaml

      Firewall Rule Name:
        protocol: <protocol> (TCP, UDP, ICMP)
        source_mac: <source-mac>
        source_ip: <source-ip>
        target_ip: <target-ip>
        port_range_start: <port-range-start>
        port_range_end: <port-range-end>
        icmp_type: <icmp-type>
        icmp_code: <icmp-code>

- ``private_lan`` - This option will connect the server to the specified
  private LAN. If no LAN exists, then a new private LAN will be created. The
  value accepts a LAN ID (integer).

  .. versionadded:: 2019.2.0

- ``private_ips`` - Private IPs assigned in the private LAN. NAT setting is
  ignored when this setting is active.

- ``private_firewall_rules`` - This option allows for a list of firewall rules
  assigned to the private network interface.

  .. code-block:: yaml

      Firewall Rule Name:
        protocol: <protocol> (TCP, UDP, ICMP)
        source_mac: <source-mac>
        source_ip: <source-ip>
        target_ip: <target-ip>
        port_range_start: <port-range-start>
        port_range_end: <port-range-end>
        icmp_type: <icmp-type>
        icmp_code: <icmp-code>

- ``ssh_private_key`` - Full path to the SSH private key file

- ``ssh_public_key`` - Full path to the SSH public key file

- ``ssh_interface`` - This option will use the private LAN IP for node
  connections (such as as bootstrapping the node) instead of the public LAN IP.
  The value accepts 'private_lan'.

- ``cpu_family`` - This option allow the CPU family to be set to AMD_OPTERON or
  INTEL_XEON.  The default is AMD_OPTERON.

- ``volumes`` - This option allows a list of additional volumes by name that
  will be created and attached to the server. Each volume requires 'disk_size'
  and, optionally, 'disk_type'. The default is HDD.

- ``deploy`` - Set to ``False`` if Salt should not be installed on the node.

- ``wait_for_timeout`` - The timeout to wait in seconds for provisioning
  resources such as servers.  The default wait_for_timeout is 15 minutes.

For more information concerning cloud profiles, see :ref:`here
<salt-cloud-profiles>`.
