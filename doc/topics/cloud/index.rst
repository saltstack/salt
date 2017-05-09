.. _salt-cloud:

==========
Salt Cloud
==========

.. raw:: html
 :file: index.html

Configuration
=============
Salt Cloud provides a powerful interface to interact with cloud hosts. This
interface is tightly integrated with Salt, and new virtual machines
are automatically connected to your Salt master after creation.

Since Salt Cloud is designed to be an automated system, most configuration
is done using the following YAML configuration files:

- ``/etc/salt/cloud``: The main configuration file, contains global settings
  that apply to all cloud hosts. See :ref:`Salt Cloud Configuration
  <salt-cloud-config>`.

- ``/etc/salt/cloud.providers.d/*.conf``: Contains settings that configure
  a specific cloud host, such as credentials, region settings, and so on. Since
  configuration varies significantly between each cloud host, a separate file
  should be created for each cloud host. In Salt Cloud, a provider is
  synonymous with a cloud host (Amazon EC2, Google Compute Engine, Rackspace,
  and so on).  See :ref:`Provider Specifics <cloud-provider-specifics>`.

- ``/etc/salt/cloud.profiles.d/*.conf``: Contains settings that define
  a specific VM type. A profile defines the systems specs and image, and any
  other settings that are specific to this VM type. Each specific VM type is
  called a profile, and multiple profiles can be defined in a profile file.
  Each profile references a parent provider that defines the cloud host in
  which the VM is created (the provider settings are in the provider
  configuration explained above).  Based on your needs, you might define
  different profiles for web servers, database servers, and so on. See :ref:`VM
  Profiles <cloud-provider-specifics>`.

Configuration Inheritance
=========================
Configuration settings are inherited in order from the cloud config =>
providers => profile.

.. image:: /_static/cloud-settings-inheritance.png
   :align: center
   :width: 40%

For example, if you wanted to use the same image for
all virtual machines for a specific provider, the image name could be placed in
the provider file. This value is inherited by all profiles that use that
provider, but is overridden if a image name is defined in the profile.

Most configuration settings can be defined in any file, the main difference
being how that setting is inherited.

QuickStart
==========
The :ref:`Salt Cloud Quickstart <salt-cloud-qs>` walks you through defining
a provider, a VM profile, and shows you how to create virtual machines using Salt Cloud.

Note that if you installed Salt via `Salt Bootstrap`_, it may not have
automatically installed salt-cloud for you. Use your distribution's package
manager to install the ``salt-cloud`` package from the same repo that you
used to install Salt.  These repos will automatically be setup by Salt Bootstrap.

If there is no salt-cloud package, install with ``pip install salt-cloud``.

.. _`Salt Bootstrap`: https://github.com/saltstack/salt-bootstrap

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
        Getting Started With Azure Arm <azurearm>
        Getting Started With DigitalOcean <digitalocean>
        Getting Started With Dimension Data <dimensiondata>
        Getting Started With EC2 <aws>
        Getting Started With GoGrid <gogrid>
        Getting Started With Google Compute Engine <gce>
        Getting Started With HP Cloud <hpcloud>
        Getting Started With Joyent <joyent>
        Getting Started With Linode <linode>
        Getting Started With LXC <lxc>
        Getting Started With OpenNebula <opennebula>
        Getting Started With OpenStack <openstack>
        Getting Started With Parallels <parallels>
        Getting Started With ProfitBricks <profitbricks>
        Getting Started With Proxmox <proxmox>
        Getting Started With Rackspace <rackspace>
        Getting Started With Scaleway <scaleway>
        Getting Started With Saltify <saltify>
        Getting Started With SoftLayer <softlayer>
        Getting Started With Vexxhost <vexxhost>
        Getting Started With Virtualbox <virtualbox>
        Getting Started With VMware <vmware>


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

    QuickStart <qs>
    Using Salt Cloud with the Event Reactor <reactor>
