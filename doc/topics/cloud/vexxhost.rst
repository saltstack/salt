=============================
Getting Started with VEXXHOST
=============================

`VEXXHOST <https://vexxhost.com/>`_ is a cloud computing host which provides
`Canadian cloud computing <https://vexxhost.com//cloud-computing>`_ services
which are based in Monteral and use the libcloud OpenStack driver.  VEXXHOST
currently runs the Havana release of OpenStack.  When provisioning new
instances, they automatically get a public IP and private IP address.
Therefore, you do not need to assign a floating IP to access your instance
after it's booted.


Cloud Provider Configuration
============================

To use the `openstack` driver for the VEXXHOST public cloud, you will need to
set up the cloud provider configuration file as in the example below:

``/etc/salt/cloud.providers.d/vexxhost.conf``:
In order to use the VEXXHOST public cloud, you will need to setup a cloud
provider configuration file as in the example below which uses the OpenStack
driver.

.. code-block:: yaml

    my-vexxhost-config:
      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure VEXXHOST using the OpenStack plugin
      #
      identity_url: http://auth.api.thenebulacloud.com:5000/v2.0/tokens
      compute_name: nova

      # Set the compute region:
      #
      compute_region: na-yul-nhs1

      # Configure VEXXHOST authentication credentials
      #
      user: your-tenant-id
      password: your-api-key
      tenant: your-tenant-name

      # keys to allow connection to the instance launched
      #
      ssh_key_name: yourkey
      ssh_key_file: /path/to/key/yourkey.priv

      driver: openstack

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Authentication
==============

All of the authentication fields that you need can be found by logging into
your VEXXHOST customer center.  Once you've logged in, you will need to click
on "CloudConsole" and then click on "API Credentials".


Cloud Profile Configuration
===========================

In order to get the correct image UUID and the instance type to use in the
cloud profile, you can run the following command respectively:

.. code-block:: bash

    # salt-cloud --list-images=vexxhost-config
    # salt-cloud --list-sizes=vexxhost-config

Once you have that, you can go ahead and create a new cloud profile.  This
profile will build an Ubuntu 12.04 LTS `nb.2G` instance.

``/etc/salt/cloud.profiles.d/vh_ubuntu1204_2G.conf``:

.. code-block:: yaml

    vh_ubuntu1204_2G:
      provider: my-vexxhost-config
      image: 4051139f-750d-4d72-8ef0-074f2ccc7e5a
      size: nb.2G

Provision an instance
=====================

To create an instance based on the sample profile that we created above, you
can run the following `salt-cloud` command.

.. code-block:: bash

    # salt-cloud -p vh_ubuntu1204_2G vh_instance1

Typically, instances are provisioned in under 30 seconds on the VEXXHOST public
cloud.  After the instance provisions, it will be set up a minion and then
return all the instance information once it's complete.

Once the instance has been setup, you can test connectivity to it by running
the following command:

.. code-block:: bash

    # salt vh_instance1 test.version

You can now continue to provision new instances and they will all automatically
be set up as minions of the master you've defined in the configuration file.
