=============================
Getting Started With HP Cloud
=============================

HP Cloud is a major public cloud platform and uses the libcloud
`openstack` driver. The current version of OpenStack that HP Cloud
uses is Havana. When an instance is booted, it must have a
floating IP added to it in order to connect to it and further below
you will see an example that adds context to this statement.

Set up a cloud provider configuration file
==========================================

To use the `openstack` driver for HP Cloud, set up the cloud
provider configuration file as in the example shown below:

``/etc/salt/cloud.providers.d/hpcloud.conf``:

.. code-block:: yaml

    hpcloud-config:
      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure HP Cloud using the OpenStack plugin
      #
      identity_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/tokens
      compute_name: Compute
      protocol: ipv4

      # Set the compute region:
      #
      compute_region: region-b.geo-1

      # Configure HP Cloud authentication credentials
      #
      user: myname
      tenant: myname-project1
      password: xxxxxxxxx

      # keys to allow connection to the instance launched
      #
      ssh_key_name: yourkey
      ssh_key_file: /path/to/key/yourkey.priv

      driver: openstack


The subsequent example that follows is using the openstack driver.

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Compute Region
==============

Originally, HP Cloud, in its OpenStack Essex version (1.0), had 3
availability zones in one region, US West (region-a.geo-1), which
each behaved each as a region.

This has since changed, and the current OpenStack Havana version of
HP Cloud (1.1) now has simplified this and now has two regions to choose from:

.. code-block:: bash

    region-a.geo-1 -> US West
    region-b.geo-1 -> US East

Authentication
==============

The ``user`` is the same user as is used to log into the HP Cloud management
UI. The ``tenant`` can be found in the upper left under "Project/Region/Scope".
It is often named the same as ``user`` albeit with a ``-project1`` appended.
The ``password`` is of course what you created your account with. The management
UI also has other information such as being able to select US East or US West.

Set up a cloud profile config file
==================================

The profile shown below is a know working profile for an Ubuntu instance. The
profile configuration file is stored in the following location:

``/etc/salt/cloud.profiles.d/hp_ae1_ubuntu.conf``:

.. code-block:: yaml

    hp_ae1_ubuntu:
        provider: hp_ae1
        image: 9302692b-b787-4b52-a3a6-daebb79cb498
        ignore_cidr: 10.0.0.1/24
        networks:
          - floating: Ext-Net
        size: standard.small
        ssh_key_file: /root/keys/test.key
        ssh_key_name: test
        ssh_username: ubuntu

Some important things about the example above:

* The ``image`` parameter can use either the image name or image ID which you can obtain by running in the example below (this case US East):

.. code-block:: bash

    # salt-cloud --list-images hp_ae1

* The parameter ``ignore_cidr`` specifies a range of addresses to ignore when trying to connect to the instance. In this case, it's the range of IP addresses used for an private IP of the instance.

* The parameter ``networks`` is very important to include. In previous versions of Salt Cloud, this is what made it possible for salt-cloud to be able to attach a floating IP to the instance in order to connect to the instance and set up the minion. The current version of salt-cloud doesn't require it, though having it is of no harm either. Newer versions of salt-cloud will use this, and without it, will attempt to find a list of floating IP addresses to use regardless.

* The ``ssh_key_file`` and ``ssh_key_name`` are the keys that will make it possible to connect to the instance to set up the minion

* The ``ssh_username`` parameter, in this case, being that the image used will be ubuntu, will make it possible to not only log in but install the minion


Launch an instance
==================

To instantiate a machine based on this profile (example):

.. code-block:: bash

    # salt-cloud -p hp_ae1_ubuntu ubuntu_instance_1


After several minutes, this will create an instance named ubuntu_instance_1
running in HP Cloud in the US East region and will set up the minion and then
return information about the instance once completed.

Manage the instance
===================

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    # salt ubuntu_instance_1 ping

SSH to the instance
===================

Additionally, the instance can be accessed via SSH using the floating IP assigned to it

.. code-block:: bash

    # ssh ubuntu@<floating ip>

Using a private IP
==================

Alternatively, in the cloud profile, using the private IP to log into the instance to set up the minion is another option, particularly if salt-cloud is running within the cloud on an instance that is on the same network with all the other instances (minions)

The example below is a modified version of the previous example. Note the use of ``ssh_interface``:

.. code-block:: yaml

    hp_ae1_ubuntu:
        provider: hp_ae1
        image: 9302692b-b787-4b52-a3a6-daebb79cb498
        size: standard.small
        ssh_key_file: /root/keys/test.key
        ssh_key_name: test
        ssh_username: ubuntu
        ssh_interface: private_ips

With this setup, salt-cloud will use the private IP address to ssh into the instance and set up the salt-minion
