.. _salt-cloud-qs:

=====================
Salt Cloud Quickstart
=====================

Salt Cloud is built-in to Salt, and the easiest way to run Salt Cloud is
directly from your Salt Master.

Note that if you installed Salt via `Salt Bootstrap`_, it may not have
automatically installed salt-cloud for you. Use your distribution's package
manager to install the ``salt-cloud`` package from the same repo that you
used to install Salt.  These repos will automatically be setup by Salt Bootstrap.

Alternatively, the ``-L`` option can be passed to the `Salt Bootstrap`_ script when
installing Salt. The ``-L`` option will install ``salt-cloud`` and the required
``libcloud`` package.

.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap

This quickstart walks you through the basic steps of setting up a cloud host
and defining some virtual machines to create.

.. note:: Salt Cloud has its own process and does not rely on the Salt Master,
   so it can be installed on a standalone minion instead of your Salt Master.

Define a Provider
-----------------
The first step is to add the credentials for your cloud host. Credentials and
other settings provided by the cloud host are stored in provider configuration
files. Provider configurations contain the details needed to connect to a cloud
host such as EC2, GCE, Rackspace, etc., and any global options that you want
set on your cloud minions (such as the location of your Salt Master).

On your Salt Master, browse to ``/etc/salt/cloud.providers.d/`` and create
a file called ``<provider>.conf``, replacing ``<provider>`` with
``ec2``, ``softlayer``, and so on. The name helps you identify the contents,
and is not important as long as the file ends in ``.conf``.

Next, browse to the :ref:`Provider specifics <cloud-provider-specifics>` and
add any required settings for your cloud host to this file. Here is an example
for Amazon EC2:

.. code-block:: yaml

    my-ec2:
      driver: ec2
      # Set the EC2 access credentials (see below)
      #
      id: 'HJGRYCILJLKJYG'
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      # Make sure this key is owned by root with permissions 0400.
      #
      private_key: /etc/salt/my_test_key.pem
      keyname: my_test_key
      securitygroup: default
      # Optional: Set up the location of the Salt Master
      #
      minion:
        master: saltmaster.example.com

The required configuration varies between cloud hosts so make sure you read the
provider specifics.

List Cloud Provider Options
---------------------------
You can now query the cloud provider you configured for available locations,
images, and sizes. This information is used when you set up VM profiles.

.. code-block:: console

    salt-cloud --list-locations <provider_name>  # my-ec2 in the previous example
    salt-cloud --list-images <provider_name>
    salt-cloud --list-sizes <provider_name>

Replace ``<provider_name>`` with the name of the provider configuration you defined.

Create VM Profiles
------------------
On your Salt Master, browse to ``/etc/salt/cloud.profiles.d/`` and create
a file called ``<profile>.conf``, replacing ``<profile>`` with
``ec2``, ``softlayer``, and so on. The file must end in ``.conf``.

You can now add any custom profiles you'd like to define to this file. Here are
a few examples:

.. code-block:: yaml

    micro_ec2:
      provider: my-ec2
      image: ami-d514f291
      size: t1.micro

    medium_ec2:
      provider: my-ec2
      image: ami-d514f291
      size: m3.medium

    large_ec2:
      provider: my-ec2
      image: ami-d514f291
      size: m3.large

Notice that the ``provider`` in our profile matches the provider name that we
defined? That is how Salt Cloud knows how to connect to a cloud host to
create a VM with these attributes.

Create VMs
----------
VMs are created by calling ``salt-cloud`` with the following options:

.. code-block:: console

    salt-cloud -p <profile> <name1> <name2> ...

For example:

.. code-block:: bash

    salt-cloud -p micro_ec2 minion1 minion2

Destroy VMs
-----------
Add a ``-d`` and the minion name you provided to destroy:

.. code-block:: bash

    salt-cloud -d minion1 minion2

Query VMs
---------
You can view details about the VMs you've created using ``--query``:

.. code-block:: bash

    salt-cloud --query

Cloud Map
---------
Now that you know how to create and destoy individual VMs, next you should
learn how to use a cloud map to create a number of VMs at once.

Cloud maps let you define a map of your infrastructure and quickly provision
any number of VMs. On subsequent runs, any VMs that do not exist are created,
and VMs that are already configured are left unmodified.

See :ref:`Cloud Map File <salt-cloud-map>`.
