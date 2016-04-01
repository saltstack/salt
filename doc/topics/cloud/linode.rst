===========================
Getting Started With Linode
===========================

Linode is a public cloud host with a focus on Linux instances.

Starting with the 2015.8.0 release of Salt, the Linode driver uses Linode's
native REST API. There are no external dependencies required to use the
Linode driver.

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
      ssh_pubkey: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKHEOLLbeXgaqRQT9NBAopVz366SdYc0KKX33vAnq+2R user@host
      ssh_key_file: ~/.ssh/id_ed25519
      driver: linode

The password needs to be 8 characters and contain lowercase, uppercase, and
numbers.

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    linode_1024:
      provider: my-linode-config
      size: Linode 2048
      image: CentOS 7
      location: London, England, UK

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


Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations my-linode-config
    my-linode-config:
        ----------
        linode:
            ----------
            Atlanta, GA, USA:
                ----------
                abbreviation:
                    atlanta
                id:
                    4
            Dallas, TX, USA:
                ----------
                abbreviation:
                    dallas
                id:
                    2
    ...SNIP...


Cloning
=======

When salt-cloud accesses Linode via linode-python it can clone machines.

It is safest to clone a stopped machine. To stop a machine run

.. code-block:: bash

    salt-cloud -a stop machine_to_clone

To create a new machine based on another machine, add an entry to your linode
cloud profile that looks like this:

.. code-block:: yaml

    li-clone:
      provider: my-linode-config
      clonefrom: machine_to_clone
      script_args: -C -F

Then run salt-cloud as normal, specifying ``-p li-clone``. The profile name can
be anything; It doesn't have to be ``li-clone``.

``clonefrom:`` is the name of an existing machine in Linode from which to clone.
``Script_args: -C -F`` is necessary to avoid re-deploying Salt via salt-bootstrap.
``-C`` will just re-deploy keys so the new minion will not have a duplicate key
or minion_id on the Master, and ``-F`` will force a rewrite of the Minion config
file on the new Minion. If ``-F`` isn't provided, the new Minion will have the
``machine_to_clone``'s Minion ID, instead of its own Minion ID, which can cause
problems.

.. note::

    `Pull Request #733`_ to the salt-bootstrap repo makes the ``-F`` argument
    non-necessary. Once that change is released into a stable version of the
    Bootstrap Script, the ``-C`` argument will be sufficient for the ``script_args``
    setting.

.. _Pull Request #733: https://github.com/saltstack/salt-bootstrap/pull/733

If the ``machine_to_clone`` does not have Salt installed on it, refrain from using
the ``script_args: -C -F`` altogether, because the new machine will need to have
Salt installed.
