.. _installation-ubuntu:

======
Ubuntu
======

.. _installation-ubuntu-repo:

Installation from the Official SaltStack Repository
===================================================

Packages for Ubuntu 16 (Xenial), Ubuntu 14 (Trusty), and Ubuntu 12 (Precise)
are available in the SaltStack repository.

Instructions are at https://repo.saltstack.com/#ubuntu.

Installation from the Community-Maintained Repository
=====================================================

The PPA is no longer maintained, and shouldn't be used. Please use the Official 
Salt Stack repository instead.

Install Packages
================

Install the Salt master, minion or other packages from the repository with
the `apt-get` command. These examples each install one of Salt components, but
more than one package name may be given at a time:

- ``apt-get install salt-api``
- ``apt-get install salt-cloud``
- ``apt-get install salt-master``
- ``apt-get install salt-minion``
- ``apt-get install salt-ssh``
- ``apt-get install salt-syndic``

.. _ubuntu-config:

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
