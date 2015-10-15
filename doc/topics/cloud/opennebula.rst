===============================
Getting Started with OpenNebula
===============================

OpenNebula is an open-source solution for the comprehensive management of virtualized data centers to enable the mixed
use of private, public, and hybrid IaaS clouds.


Dependencies
============
The driver requires Python's ``lxml`` library to be installed. It also requires an OpenNebula installation running
version ``4.12``.


Configuration
=============
The following example illustrates some of the options that can be set. These parameters are discussed in more detail
below.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-opennebula-provider:
      # Set up the location of the salt master
      #
      minion:
        master: saltmaster.example.com

      # Define xml_rpc setting which Salt-Cloud uses to connect to the OpenNebula API. Required.
      #
      xml_rpc: http://localhost:2633/RPC2

      # Define the OpenNebula access credentials. This can be the main "oneadmin" user that OpenNebula uses as the
      # OpenNebula main admin, or it can be a user defined in the OpenNebula instance. Required.
      #
      user: oneadmin
      password: JHGhgsayu32jsa

      # Define the private key location that is used by OpenNebula to access new VMs. This setting is required if
      # provisioning new VMs or accessing VMs previously created with the associated public key.
      #
      private_key: /path/to/private/key

      driver: opennebula


Access Credentials
==================
The Salt Cloud driver for OpenNebula was written using OpenNebula's native XML RPC API. Every interaction with
OpenNebula's API requires a ``username`` and ``password`` to make the connection from the machine running Salt Cloud
to API running on the OpenNebula instance. Based on the access credentials passed in, OpenNebula filters the commands
that the user can perform or the information for which the user can query. For example, the images that a user can
view with a ``--list-images`` command are the images that the connected user and the connected user's groups can access.


Key Pairs
=========
Salt Cloud needs to be able to access a virtual machine in order to install the Salt Minion by using a public/private
key pair. The virtual machine will need to be seeded with the public key, which is laid down by the OpenNebula
template. Salt Cloud then uses the corresponding private key, provided by the ``private_key`` setting in the cloud
provider file, to SSH into the new virtual machine.

To seed the virtual machine with the public key, the public key must be added to the OpenNebula template. If using the
OpenNebula web interface, navigate to the template, then click ``Update``. Click the ``Context`` tab. Under the
``Network & SSH`` section, click ``Add SSH Contextualization`` and paste the public key in the ``Public Key`` box.
Don't forget to save your changes by clicking the green ``Update`` button.

.. note::

    The key pair must not have a pass-phrase.


Cloud Profiles
==============
Set up an initial profile at either ``/etc/salt/cloud.profiles`` or the ``/etc/salt/cloud.profiles.d/`` directory.

.. code-block:: yaml

    my-opennebula-profile:
      provider: my-opennebula-provider
      image: Ubuntu-14.04

The profile can now be realized with a salt command:

.. code-block:: bash

    salt-cloud -p my-opennebula-profile my-new-vm

This will create a new instance named ``my-new-vm`` in OpenNebula. The minion that is installed on this instance will
have a minion id of ``my-new-vm``. If the command was executed on the salt-master, its Salt key will automatically be
signed on the master.

Once the instance has been created with salt-minion installed, connectivity to it can be verified with Salt:

.. code-block:: bash

    salt my-new-vm test.ping

OpenNebula uses an image --> template --> virtual machine paradigm where the template draws on the image, or disk,
and virtual machines are created from templates. Because of this, there is no need to define a ``size`` in the cloud
profile. The size of the virtual machine is defined in the template.


.. _opennebula-required-settings:

Required Settings
=================
The following settings are always required for OpenNebula:

.. code-block:: yaml

    my-opennebula-config:
      xml_rpc: http://localhost:26633/RPC2
      user: oneadmin
      password: JHGhgsayu32jsa
      driver: opennebula


Required Settings for VM Deployment
-----------------------------------
The settings defined in the :ref:`opennebula-required-settings` section are required for all interactions with
OpenNebula. However, when deploying a virtual machine via Salt Cloud, an additional setting, ``private_key``, is also
required:

.. code-block:: yaml

    my-opennebula-config:
      private_key: /path/to/private/key


Listing Images
==============
Images can be queried on OpenNebula by passing the ``--list-images`` argument to Salt Cloud:

.. code-block:: bash

    salt-cloud --list-images opennebula


Listing Locations
=================
In OpenNebula, locations are defined as ``hosts``. Locations, or "hosts", can be querried on OpenNebula by passing the
``--list-locations`` argument to Salt Cloud:

.. code-block:: bash

    salt-cloud --list-locations opennebula

Listing Sizes
=============
Sizes are defined by templates in OpenNebula. As such, the ``--list-sizes`` call returns an empty dictionary since
there are no sizes to return.


Additional OpenNebula API Functionality
=======================================
The Salt Cloud driver for OpenNebula was written using OpenNebula's native XML RPC API. As such, many ``--function``
and ``--action`` calls were added to the OpenNebula driver to enhance support for an OpenNebula infrastructure with
additional control from Salt Cloud. See the :py:mod:`OpenNebula function definitions <salt.cloud.clouds.opennebula>`
for more information.
