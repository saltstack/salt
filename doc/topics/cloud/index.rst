Salt Cloud Documentation
========================

.. toctree::
    :maxdepth: 3
    :glob:
    :hidden:

    *
    install/index

Salt cloud is a public cloud provisioning tool. Salt cloud is made to integrate
Salt into cloud providers in a clean way so that minions on public cloud
systems can be quickly and easily modeled and provisioned.

Salt cloud allows for cloud based minions to be managed via virtual machine
maps and profiles. This means that individual cloud VMs can be created, or
large groups of cloud VMs can be created at once or managed.

Virtual machines created with Salt cloud install salt on the target virtual
machine and assign it to the specified master. This means that virtual
machines can be provisioned and then potentially never logged into.

While Salt Cloud has been made to work with Salt, it is also a generic
cloud management platform and can be used to manage non Salt centric clouds.

Getting Started
===============

* :doc:`Installing salt cloud <install/index>`

Some quick guides covering getting started with each of the various cloud
providers.

* :doc:`Getting Started With Azure <azure>`
* :doc:`Getting Started With Digital Ocean <digitalocean>`
* :doc:`Getting Started With EC2 <aws>`
* :doc:`Getting Started With GoGrid <gogrid>`
* :doc:`Getting Started With Google Compute Engine <gce>`
* :doc:`Getting Started With Joyent <joyent>`
* :doc:`Getting Started With Linode <linode>`
* :doc:`Getting Started With OpenStack <openstack>`
* :doc:`Getting Started With Parallels <parallels>`
* :doc:`Getting Started With Rackspace <rackspace>`
* :doc:`Getting Started With SoftLayer <softlayer>`

Core Configuration
==================

The core configuration of Salt cloud is handled in the cloud configuration
file. This file is comprised of global configurations for interfacing with
cloud providers.

* :doc:`Core Configuration <config>`

Windows Configuration
=====================

Salt Cloud may be used to spin up a Windows minion, and then install the Salt
Minion client on that instance. At this time, Salt Cloud itself still needs to
be run from a Linux or Unix machine.

* :doc:`Windows Configuration <windows>`

Using Salt Cloud
================

Salt cloud works via profiles and maps. Simple profiles for cloud VMs are
defined and can be used directly, or a map can be defined specifying
a large group of virtual machines to create.

* :doc:`Profiles <profiles>`
* :doc:`Maps <map>`

Once a VM has been deployed, a number of actions may be available to perform
on it, depending on the specific cloud provider.

* :doc:`Actions <action>`

Depending on your cloud provider, a number of functions may also be available
which do not require a VM to be specified.

* :doc:`Functions <function>`

Miscellaneous Options
=====================

* :doc:`Miscellaneous <misc>`

Troubleshooting Steps
=====================

* :doc:`Troubleshooting <troubleshooting>`

Extending Salt Cloud
====================

Salt Cloud extensions work in a way similar to Salt modules. Therefore
extending Salt cloud to manage more public cloud providers and operating
systems is easy.

* :doc:`Adding Cloud Providers <cloud>`
* :doc:`Adding OS Support <deploy>`

Using Salt Cloud from Salt
==========================

Several Salt Cloud modules exist within Salt itself in order to manage cloud
instances using Salt's own powerful feature set.

* :doc:`Using Salt Cloud from Salt <salt>`

Feature Comparison
==================

A table is available which compares various features available across all
supported cloud providers.

* :doc:`Features <features>`

Legacy Releases
===============

.. versionchanged:: 2014.1.0 (Hydrogen)
    Release notes will be part of Salt's main release notes starting with
    Salt's 2014.1.0 (Hydrogen) release.

* :doc:`Legacy Release Notes <releases/index>`

Reference
=========

* :doc:`Command-line interface </ref/cli/salt-cloud>`

* :doc:`Full table of contents </contents>`
