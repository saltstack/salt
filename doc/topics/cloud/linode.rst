===========================
Getting Started With Linode
===========================

Linode is a public cloud provider with a focus on Linux instances.

Dependencies
============
The Linode driver for Salt Cloud requires Libcloud 0.13.2 or higher to be
installed.


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
