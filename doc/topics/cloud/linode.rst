===========================
Getting Started With Linode
===========================

Linode is a public cloud provider with a focus on Linux instances.

Dependencies
============
* linode-python >= 1.1.1

OR

* Libcloud >= 0.13.2

This driver supports accessing Linode via linode-python or Apache Libcloud.
Linode-python is recommended, it is more full-featured than Libcloud.  In
particular using linode-python enables stopping, starting, and cloning
machines.

Driver selection is automatic.  If linode-python is present it will be used.
If it is absent, salt-cloud will fall back to Libcloud.  If neither are present
salt-cloud will abort.

NOTE: linode-python 1.1.1 or later is recommended. Earlier versions of linode-python
should work but leak sensitive information into the debug logs.

Linode-python can be downloaded from
https://github.com/tjfontaine/linode-python or installed via pip.

Configuration
=============
Linode requires a single API key, but the default root password for new 
instances also needs to be set:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-linode-config:
      apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
      password: F00barbaz
      provider: linode

The password needs to be 8 characters and contain lowercase, uppercase and 
numbers.

Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    linode_1024:
      provider: my-linode-config
      size: Linode 1024
      image: Arch Linux 2013.06

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-linode-config
    my-linode-config:
        ----------
        linode:
            ----------
            Linode 1024:
                ----------
                bandwidth:
                    2000
                disk:
                    49152
                driver:
                get_uuid:
                id:
                    1
                name:
                    Linode 1024
                price:
                    20.0
                ram:
                    1024
                uuid:
                    03e18728ce4629e2ac07c9cbb48afffb8cb499c4
    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-linode-config
    my-linode-config:
        ----------
        linode:
            ----------
            Arch Linux 2013.06:
                ----------
                driver:
                extra:
                    ----------
                    64bit:
                        1
                    pvops:
                        1
                get_uuid:
                id:
                    112
                name:
                    Arch Linux 2013.06
                uuid:
                    8457f92eaffc92b7666b6734a96ad7abe1a8a6dd
    ...SNIP...


Cloning
=======

When salt-cloud accesses Linode via linode-python it can clone machines.

It is safest to clone a stopped machine.  To stop a machine run

.. code-block:: bash

    salt-cloud -a stop machine_to_clone

To create a new machine based on another machine, add an entry to your linode
cloud profile that looks like this:

.. code-block:: yaml

    li-clone:
      provider: linode
      clonefrom: machine_to_clone
      script_args: -C

Then run salt-cloud as normal, specifying `-p li-clone`.  The profile name can
be anything--it doesn't have to be `li-clone`.

`Clonefrom:` is the name of an existing machine in Linode from which to clone.
`Script_args: -C` is necessary to avoid re-deploying Salt via salt-bootstrap.
`-C` will just re-deploy keys so the new minion will not have a duplicate key
or minion_id on the master.

