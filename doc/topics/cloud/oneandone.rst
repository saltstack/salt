==========================
Getting Started With 1and1
==========================

1&1 is one of the world’s leading Web hosting providers. 1&1 currently offers
a wide range of Web hosting products, including email solutions and high-end
servers in 10 different countries including Germany, Spain, Great Britain
and the United States.  From domains to 1&1 MyWebsite to eBusiness solutions
like Cloud Hosting and Web servers for complex tasks, 1&1 is well placed to deliver
a high quality service to its customers. All 1&1 products are hosted in
1&1‘s high-performance, green data centers in the USA and Europe.

Dependencies
============

* 1and1 >= 1.2.0

Configuration
=============

* Using the new format, set up the cloud configuration at
  ``/etc/salt/cloud.providers`` or
  ``/etc/salt/cloud.providers.d/oneandone.conf``:

.. code-block:: yaml

    my-oneandone-config:
      driver: oneandone

      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure oneandone authentication credentials
      #
      api_token: <api_token>
      ssh_private_key: /path/to/id_rsa
      ssh_public_key: /path/to/id_rsa.pub

Authentication
==============

The ``api_key`` is used for API authorization. This token can be obtained
from the CloudPanel in the Management section below Users.

Profiles
========

Here is an example of a profile:

.. code-block:: yaml

    oneandone_fixed_size:
      provider: my-oneandone-config
      description: Small instance size server
      fixed_instance_size: S
      appliance_id: 8E3BAA98E3DFD37857810E0288DD8FBA

    oneandone_custom_size:
      provider: my-oneandone-config
      description: Custom size server
      vcore: 2
      cores_per_processor: 2
      ram: 8
      appliance_id: 8E3BAA98E3DFD37857810E0288DD8FBA
      hdds:
      -
        is_main: true
        size: 20
      -
        is_main: false
        size: 20

The following list explains some of the important properties.

fixed_instance_size_id
    When creating a server, either ``fixed_instance_size_id`` or custom hardware params
    containing ``vcore``, ``cores_per_processor``, ``ram``, and ``hdds`` must be provided.
    Can be one of the IDs listed among the output of the following command:

.. code-block:: bash

    salt-cloud --list-sizes oneandone

vcore
    Total amount of processors.

cores_per_processor
    Number of cores per processor.

ram
    RAM memory size in GB.

hdds
    Hard disks.

appliance_id
    ID of the image that will be installed on server.
    Can be one of the IDs listed in the output of the following command:

.. code-block:: bash

    salt-cloud --list-images oneandone

datacenter_id
    ID of the datacenter where the server will be created.
    Can be one of the IDs listed in the output of the following command:

.. code-block:: bash

    salt-cloud --list-locations oneandone

description
    Description of the server.

password
    Password of the server. Password must contain more than 8 characters
    using uppercase letters, numbers and other special symbols.

power_on
    Power on server after creation. Default is set to true.

firewall_policy_id
    Firewall policy ID. If it is not provided, the server will assign
    the best firewall policy, creating a new one if necessary. If the parameter
    is sent with a 0 value, the server will be created with all ports blocked.

ip_id
    IP address ID.

load_balancer_id
    Load balancer ID.

monitoring_policy_id
    Monitoring policy ID.

deploy
    Set to False if Salt should not be installed on the node.

wait_for_timeout
    The timeout to wait in seconds for provisioning resources such as servers.
    The default wait_for_timeout is 15 minutes.

public_key_ids
    List of public key IDs (ssh key).

Functions
=========

* Create an SSH key

.. code-block:: bash

    sudo salt-cloud -f create_ssh_key my-oneandone-config name='SaltTest' description='SaltTestDescription'

* Create a block storage

.. code-block:: bash

    sudo salt-cloud -f create_block_storage my-oneandone-config name='SaltTest2' description='SaltTestDescription' size=50 datacenter_id='5091F6D8CBFEF9C26ACE957C652D5D49'

For more information concerning cloud profiles, see :ref:`here
<salt-cloud-profiles>`.
