===========================
Getting Started With Linode
===========================

Linode is a public cloud host with a focus on Linux instances.


Dependencies
============
This driver requires the Python ``requests`` library to be installed.


Provider Configuration
======================

Configuration Options
---------------------

.. glossary::

    ``apikey``
        **(Required)** The key to use to authenticate with the Linode API.

    ``password``
        **(Required)** The default password to set on new VMs. Must be 8 characters with at least one lowercase, uppercase, and numeric.

    ``api_version``
        The version of the Linode API to interact with. Defaults to ``v3``.

    ``poll_interval``
        The rate of time in milliseconds to poll the Linode API for changes. Defaults to ``500``.

    ``ratelimit_sleep``
        The time in seconds to wait before retrying after a ratelimit has been enforced. Defaults to ``0``.


Example Configuration
---------------------

Set up the provider cloud configuration file at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.

.. code-block:: yaml

    my-linode-provider:
        driver: linode
        api_version: v4
        apikey: f4ZsmwtB1c7f85Jdu43RgXVDFlNjuJaeIYV8QMftTqKScEB2vSosFSr...
        password: F00barbaz

For use with APIv3 (deprecated):

.. code-block:: yaml

    my-linode-provider-v3:
        driver: linode
        apikey: f4ZsmwtB1c7f85Jdu43RgXVDFlNjuJaeIYV8QMftTqKScEB2vSosFSr...
        password: F00barbaz

Profile Configuration
=====================

Configuration Options
---------------------

.. glossary::

    ``image``
        **(Required)** The image to deploy the boot disk from. This should be an image ID
        (e.g. ``linode/ubuntu16.04``); official images start with ``linode/``. For APIv3,
        this would be an image label (i.e. Ubuntu 16.04). See `listing images <#listing-images>`_
        for more options.

    ``location``
        **(Required)** The location of the VM. This should be a Linode region
        (e.g. ``us-east``). For APIv3, this would be a datacenter location
        (e.g. ``Newark, NJ, USA``). See `listing locations <#listing-locations>`_ for
        more options.

    ``size``
        **(Required)** The size of the VM. This should be a Linode instance type ID
        (e.g. ``g6-standard-2``). For APIv3, this would be a plan ID (e.g. ``Linode 2GB``).
        See `listing sizes <#listing-sizes>`_ for more options.

    ``password`` (overrides provider)
        **(*Required)** The default password for the VM. Must be provided at the profile
        or provider level.

    ``assign_private_ip``
        .. versionadded:: 2016.3.0

        Whether or not to assign a private key to the VM. Defaults to ``False``.

    ``cloneform``
        The name of the Linode to clone from.

    ``disk_size``
        **(Deprecated)** The amount of disk space to allocate for the OS disk. This has no
        effect with APIv4; the size of the boot disk will be the remainder of disk space
        after the swap partition is allocated.

    ``ssh_interface``
        .. versionadded:: 2016.3.0

        The interface with which to connect over SSH. Valid options are ``private_ips`` or
        ``public_ips``. Defaults to ``public_ips``.

        If specifying ``private_ips``, the Linodes must be hosted within the same data center
        and have the Network Helper enabled on your entire account. The instance that is
        running the Salt-Cloud provisioning command must also have a private IP assigned to it.

        Newer accounts created on Linode have the Network Helper setting enabled by default,
        account-wide. Legacy accounts do not have this setting enabled by default. To enable
        the Network Helper on your Linode account, please see `Linode's Network Helper`_
        documentation.

    ``ssh_pubkey``
        The public key to authorize for SSH with the VM.

    ``swap``
        The amount of disk space to allocate for the swap partition. Defaults to ``256``.

.. _Linode's Network Helper: https://www.linode.com/docs/platform/network-helper/#what-is-network-helper

Example Configuration
---------------------

Set up a profile configuration in ``/etc/salt/cloud.profiles.d/``:

.. code-block:: yaml

    my-linode-profile:
        provider: my-linode-provider
        size: g6-standard-1
        image: linode/alpine3.12
        location: us-east

The ``my-linode-profile`` can be realized now with a salt command:

.. code-block:: bash

    salt-cloud -p my-linode-profile my-linode-instance

This will create a salt minion instance named ``my-linode-instance`` in Linode. If the command was
executed on the salt-master, its Salt key will automatically be signed on the master.

Once the instance has been created with a salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt my-linode-instance test.version

A more advanced configuration utlizing all of the configuration options might look like:

.. code-block:: yaml

    my-linode-profile-advanced:
        provider: my-linode-provider
        size: g6-standard-3
        image: linode/alpine3.10
        location: eu-west
        password: bogus123X
        assign_private_ip: true
        ssh_interface: private_ips
        ssh_pubkey: ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB...
        swap_size: 512

A legacy configuration for use with APIv3 might look like:

.. code-block:: yaml

    my-linode-profile-v3:
        provider: my-linode-provider-v3
        size: Nanode 1GB
        image: Alpine 3.12
        location: Fremont, CA, USA

Migrating to APIv4
==================

Linode APIv3 has been deprecated and will be shutdown in the coming months. You can opt-in to using
APIv4 by setting the ``api_version`` provider configuration option to ``v4``.

When switching to APIv4, you will also need to generate a new token. See
`here <https://www.linode.com/docs/platform/api/getting-started-with-the-linode-api/#create-an-api-token>`_
for more information.

Notable Changes
---------------

**Move from label references to ID references.** The profile configuration parameters ``location``,
``size``, and ``image`` have moved from accepting label based references to IDs. See the
`profile configuration <#profile-configuration>`_ section for more details.

**The ``disk_size`` profile configuration parameter has been deprecated.** The parameter will not be taken into
account when creating new VMs while targeting APIv4. See the ``disk_size`` description under the
`profile configuration <#profile-configuration>`_ section for more details.

**The ``boot`` function no longer requires a ``config_id``.** A config can be inferred by the API instead when booting.

**The ``clone`` function has renamed parameters to match convention.** The old version of these parameters will not
be supported when targeting APIv4.
* ``datacenter_id`` has been deprecated in favor of ``location``.
* ``plan_id`` has been deprecated in favor of ``size``.

**The ``get_plan_id`` function has been deprecated and will not be supported by APIv4.** IDs are now the only way
of referring to a "plan" (or type/size).

Query Utilities
===============

Listing Sizes
-------------
Available sizes can be obtained by running one of:

.. code-block:: bash

    salt-cloud --list-sizes my-linode-provider

    salt-cloud -f avail_sizes my-linode-provider

This will list all Linode sizes/types which can be referenced in VM profiles.

.. code-block:: bash

    my-linode-config:
        g6-standard-1:
            ----------
            class:
                standard
            disk:
                51200
            gpus:
                0
            id:
                g6-standard-1
            label:
                Linode 2GB
            memory:
                2048
            network_out:
                2000
            price:
                ----------
                hourly:
                    0.015
                monthly:
                    10.0
            successor:
                None
            transfer:
                2000
            vcpus:
                1
            addons:
                ----------
                backups:
                    ----------
                    price:
                        ----------
                        hourly:
                            0.004
                        monthly:
                            2.5
    ...SNIP...


Listing Images
--------------
Available images can be obtained by running one of:

.. code-block:: bash

    salt-cloud --list-images my-linode-provider

    salt-cloud -f avail_images my-linode-provider

This will list all Linode images which can be referenced in VM profiles.
Official images are available under the ``linode`` namespace.

.. code-block:: bash

    my-linode-config:
        ----------
        linode:
            ----------
            linode/alpine3.10:
                ----------
                created:
                    2019-06-20T17:17:11
                created_by:
                    linode
                deprecated:
                    False
                description:
                    None
                eol:
                    2021-05-01T04:00:00
                expiry:
                    None
                id:
                    linode/alpine3.10
                is_public:
                    True
                label:
                    Alpine 3.10
                size:
                    300
                type:
                    manual
                vendor:
                    Alpine
    ...SNIP...


Listing Locations
-----------------
Available locations can be obtained by running one of:

.. code-block:: bash

    salt-cloud --list-locations my-linode-provider

    salt-cloud -f avail_locations my-linode-provider

This will list all Linode regions which can be referenced in VM profiles.

.. code-block:: bash

    my-linode-config:
        ----------
        linode:
            ----------
            us-east:
                ----------
                capabilities:
                    - Linodes
                    - NodeBalancers
                    - Block Storage
                    - Object Storage
                    - GPU Linodes
                    - Kubernetes
                country:
                    us
                id:
                    us-east
                status:
                    ok
    ...SNIP...


Cloning
=======
To clone a Linode, add a profile with a ``clonefrom`` key, and a ``script_args: -C``.
``clonefrom`` should be the name of the Linode that is the source for the clone.
``script_args: -C`` passes a -C to the salt-bootstrap script, which only configures
the minion and doesn't try to install a new copy of salt-minion. This way the minion
gets new keys and the keys get pre-seeded on the master, and the ``/etc/salt/minion``
file has the right minion 'id:' declaration.

Cloning requires a post 2015-02-01 salt-bootstrap.

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
