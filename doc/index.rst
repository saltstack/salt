:orphan:

.. _contents:

Salt Cloud Documentation
========================

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

* :doc:`Installing salt cloud <topics/install/index>`

Some quick guides covering getting started with Amazon AWS, Rackspace, and
Parallels.

* :doc:`Getting Started With AWS <topics/aws>`
* :doc:`Getting Started With Rackspace <topics/rackspace>`
* :doc:`Getting Started With Parallels <topics/parallels>`

Core Configuration
==================

The core configuration of Salt cloud is handled in the cloud configuration
file. This file is comprised of global configurations for interfacing with
cloud providers.

* :doc:`Core Configuration <topics/config>`

Using Salt Cloud
================

Salt cloud works via profiles and maps. Simple profiles for cloud VMs are
defined and can be used directly, or a map can be defined specifying
a large group of virtual machines to create.

* :doc:`Profiles <topics/profiles>`
* :doc:`Maps <topics/map>`

Once a VM has been deployed, a number of actions may be available to perform
on it, depending on the specific cloud provider.

* :doc:`Actions <topics/action>`

Depending on your cloud provider, a number of functions may also be available
which do not require a VM to be specified.

* :doc:`Functions <topics/function>`

Miscellaneous Options
=====================

* :doc:`Miscellaneous <topics/misc>`

Extending Salt Cloud
====================

Salt cloud extensions work in a way similar to Salt modules. Therefore
extending Salt cloud to manage more public cloud providers and operating
systems is easy.

* :doc:`Adding Cloud Providers <topics/cloud>`
* :doc:`Adding OS Support <topics/deploy>`

Releases
========

* :doc:`Release Notes <topics/releases/index>`

Reference
=========

* :doc:`contents`
