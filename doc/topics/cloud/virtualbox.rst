===============================
Getting Started With Virtualbox
===============================


The Virtualbox cloud module allows you to manage a **local** Virtualbox hypervisor. Remote hypervisors may come later on.


Dependencies
============

The virtualbox module for Salt Cloud requires the `Virtualbox SDK`_
which is contained in a virtualbox installation from

https://www.virtualbox.org/wiki/Downloads


Configuration
=============

The Virtualbox cloud module just needs to use the virtualbox driver for now. Virtualbox will be run as the running user.

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/virtualbox.conf``:

.. code-block:: yaml

    virtualbox-config:
       driver: virtualbox


Profiles
========

Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/virtualbox.conf``:

.. code-block:: yaml

    virtualbox-test:
        provider: virtualbox-config
        clonefrom: VM_to_clone_from
        # Optional
        power_on: True
        deploy: True
        ssh_username: a_username
        password: a_password
        sudo: a_username
        sudo_password: a_password
        # Example minion config
        minion:
            master: localhost
        make_master: True


``clonefrom`` **Mandatory**
    Enter the name of the VM/template to clone from.

So far only machines can only be cloned and automatically provisioned by Salt Cloud.

Provisioning
------------

In order to provision when creating a new machine ``power_on`` and ``deploy`` have to be ``True``.

Furthermore to connect to the VM ``ssh_username`` and ``password`` will have to be set.

``sudo`` and ``sudo_password`` are the credentials for getting root access in order to deploy salt


Actions
=======

``start``
  Attempt to boot a VM by name. VMs should have unique names in order to boot the correct one.

``stop``
  Attempt to stop a VM. This is akin to a force shutdown or 5 second press.

Functions
=========

``show_image``
  Show all available information about a VM given by the `image` parameter

  .. code-block:: bash

    $ salt-cloud -f show_image virtualbox image=my_vm_name

.. _Virtualbox SDK: http://download.virtualbox.org/virtualbox/SDKRef.pdf
