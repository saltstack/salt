.. _salt-cloud:

==========
Salt Cloud
==========

.. raw:: html
 :file: index.html

Getting Started
===============

Salt Cloud is built-in to Salt and is configured on and executed from your Salt Master.

Define a Provider
-----------------

The first step is to add the credentials for your cloud host. Credentials
and other settings provided by the cloud host are stored in provider configuration files.
Provider configurations contain the details needed to connect to a cloud host such as EC2, GCE, Rackspace, etc.,
and any global options that you want set on your cloud minions (such as the location of your Salt Master).

On your Salt Master, browse to ``/etc/salt/cloud.providers.d/`` and create a file called ``<provider>.provider.conf``,
replacing ``<provider>`` with ``ec2``, ``softlayer``, and so on. The name helps you identify the contents, and is not
important as long as the file ends in ``.conf``.

Next, browse to the :ref:`Provider specifics <cloud-provider-specifics>` and add any required settings for your
cloud host to this file. Here is an example for Amazon EC2:

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

The required configuration varies between cloud hosts so make sure you read the provider specifics.

List Cloud Provider Options
---------------------------

You can now query the cloud provider you configured for available locations,
images, and sizes. This information is used when you set up VM profiles.

.. code-block:: bash

    salt-cloud --list-locations <provider_name>  # my-ec2 in the previous example
    salt-cloud --list-images <provider_name>
    salt-cloud --list-sizes <provider_name>

Replace ``<provider_name>`` with the name of the provider configuration you defined.

Create VM Profiles
------------------

On your Salt Master, browse to ``/etc/salt/cloud.profiles.d/`` and create a file called ``<provider>.profiles.conf``,
replacing ``<provider>`` with ``ec2``, ``softlayer``, and so on. The file must end in ``.conf``.

You can now add any custom profiles you'd like to define to this file. Here are a few examples:

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

Notice that the ``provider`` in our profile matches the provider name that we defined? That is how Salt Cloud
knows how to connect to create a VM with these attributes.

Create VMs
----------

VMs are created by calling ``salt-cloud`` with the following options:

.. code-block:: bash

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

Using Salt Cloud
================
.. toctree::
    :maxdepth: 3

    Command Line Reference <../../ref/cli/salt-cloud>
    Basic <basic>
    Profiles <profiles>
    Maps <map>
    Actions <action>
    Functions <function>

Core Configuration
==================

.. toctree::
    :maxdepth: 3

    Installing salt cloud <install/index>
    Core Configuration <config>

Windows Configuration
=====================
.. toctree::
    :maxdepth: 3

        Windows Configuration <windows>

.. _cloud-provider-specifics:

Cloud Provider Specifics
========================
.. toctree::
    :maxdepth: 3

        Getting Started With Aliyun <aliyun>
        Getting Started With Azure <azure>
        Getting Started With DigitalOcean <digitalocean>
        Getting Started With EC2 <aws>
        Getting Started With GoGrid <gogrid>
        Getting Started With Google Compute Engine <gce>
        Getting Started With HP Cloud <hpcloud>
        Getting Started With Joyent <joyent>
        Getting Started With LXC <lxc>
        Getting Started With Linode <linode>
        Getting Started With OpenNebula <opennebula>
        Getting Started With OpenStack <openstack>
        Getting Started With Parallels <parallels>
        Getting Started With Profitbricks <profitbricks>
        Getting Started With Proxmox <proxmox>
        Getting Started With Rackspace <rackspace>
        Getting Started With Saltify <saltify>
        Getting Started With Scaleway <scaleway>
        Getting Started With SoftLayer <softlayer>
        Getting Started With Vexxhost <vexxhost>
        Getting Started With Virtualbox <virtualbox>
        Getting Started With VMware <vmware>
        Getting Started With vSphere <vsphere>


Miscellaneous Options
=====================

.. toctree::
    :maxdepth: 3

    Miscellaneous <misc>

Troubleshooting Steps
=====================
.. toctree::
    :maxdepth: 3

        Troubleshooting <troubleshooting>

Extending Salt Cloud
====================
.. toctree::
    :maxdepth: 3

    Adding Cloud Providers <cloud>
    Adding OS Support <deploy>

Using Salt Cloud from Salt
==========================
.. toctree::
    :maxdepth: 3

    Using Salt Cloud from Salt <salt>

Feature Comparison
==================
.. toctree::
    :maxdepth: 3

    Features <features>

Tutorials
=========
.. toctree::
    :maxdepth: 3

    Using Salt Cloud with the Event Reactor <reactor>
