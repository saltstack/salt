:orphan:

.. _contents:

Salt Cloud Documentation
========================

Salt cloud is a public cloud provisioning tool. Salt cloud is made to integrate
Salt into cloud providers in a clean way so that minions on public cloud
systems can be quickly and easily modeled and provissioned.

Salt cloud allows for cloud based minions to be managed via virtual machine
maps and profiles. This means that individual cloud vms can be created, or
large groups of cloud vms can be created at once or managed.

Virtual machines created with Salt cloud install salt on the target virtual
machine and assign it to the specified master. This means that virtual
machines can be provisioned and then potentially never logged into.

Using Salt Cloud
================

Salt cloud works via profiles and maps. Simple profiles for cloud vms are
defined and can be used directly, or a map can be defined specifying
a large group of virtual machines to create.

1.  :doc:`Profiles <topics/profiles>`
2.  :doc:`Maps <topics/map>`

Extending Salt Cloud
====================

Salt cloud extenstions work in a way similar to Salt modules. Therefore
extending Salt cloud to manage more public cloud providers and operating
systems is easy.

1.  :doc:`Adding Cloud Providers <topics/cloud>`
2.  :doc:`Adding OS Support <topics/deploy>`
