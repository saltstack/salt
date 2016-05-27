===========================
Getting Started With Linode
===========================

Linode is a public cloud host with a focus on Linux instances.

Starting with the 2015.8.0 release of Salt, the Linode driver uses Linode's
native REST API. There are no external dependencies required to use the
Linode driver, other than a Linode account.


Provider Configuration
======================
Linode requires a single API key, but the default root password for new
instances also needs to be set. The password needs to be eight characters
and contain lowercase, uppercase, and numbers.

Set up the provider cloud configuration file at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.

.. code-block:: yaml

    my-linode-config:
      apikey: 'asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf'
      password: 'F00barbaz'
      driver: linode

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.


Profile Configuration
=====================
Linode profiles require a ``provider``, ``size``, ``image``, and ``location``. Set up an initial profile
at ``/etc/salt/cloud.profiles`` or in the ``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    linode_1024:
      provider: my-linode-config
      size: Linode 2048
      image: CentOS 7
      location: London, England, UK

The profile can be realized now with a salt command:

.. code-block:: bash

    salt-cloud -p linode_1024 linode-instance

This will create an salt minion instance named ``linode-instance`` in Linode. If the command was
executed on the salt-master, its Salt key will automatically be signed on the master.

Once the instance has been created with a salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt linode-instance test.ping


Listing Sizes
-------------
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
                AVAIL:
                    ----------
                    10:
                        500
                    2:
                        500
                    3:
                        500
                    4:
                        500
                    6:
                        500
                    7:
                        500
                    8:
                        500
                    9:
                        500
                CORES:
                    1
                DISK:
                    24
                HOURLY:
                    0.015
                LABEL:
                    Linode 1024
    ...SNIP...


Listing Images
--------------
Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-linode-config
    my-linode-config:
        ----------
        linode:
            ----------
            Arch Linux 2015.02:
                ----------
                CREATE_DT:
                    2015-02-20 14:17:16.0
                DISTRIBUTIONID:
                    138
                IS64BIT:
                    1
                LABEL:
                    Arch Linux 2015.02
                MINIMAGESIZE:
                    800
                REQUIRESPVOPSKERNEL:
                    1
    ...SNIP...


Listing Locations
-----------------
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
                ABBR:
                    atlanta
                DATACENTERID:
                    4
                LOCATION:
                    Atlanta, GA, USA
    ...SNIP...


Linode Specific Settings
========================
There are several options outlined below that can be added to either the Linode
provider of profile configuration files. Some options are mandatory and are
properly labeled below but typically also include a hard-coded default.

image
-----
Image is used to define what Operating System image should be used for the
instance. Examples are ``Ubuntu 14.04 LTS`` and ``CentOS 7``. This option should
be specified in the profile config. Required.

location
--------
Location is used to define which Linode data center the instance will reside in.
Required.

size
----
Size is used to define the instance's "plan type" which includes memory, storage,
and price. Required.

assign_private_ip
-----------------
.. versionadded:: 2016.3.0

Assigns a private IP address to a Linode when set to True. Default is False.

private_ip
----------
Deprecated in favor of `assign_private_ip`_ in Salt 2016.3.0.

ssh_interface
-------------
.. versionadded:: 2016.3.0

Specify whether to use a public or private IP for the deploy script. Valid options
are:

* public_ips: The salt-master is hosted outside of Linode. Default.
* private_ips: The salt-master is also hosted within Linode.

If specifying ``private_ips``, the Linodes must be hosted within the same data
center and have the Network Helper enabled on your entire account. The instance
that is running the Salt-Cloud provisioning command must also have a private IP
assigned to it.

Newer accounts created on Linode have the Network Helper setting enabled by default,
account-wide. Legacy accounts do not have this setting enabled by default. To enable
the Network Helper on your Linode account, please see `Linode's Network Helper`_
documentation.

If you're running into problems, be sure to restart the instance that is running
Salt Cloud after adding its own private IP address or enabling the Network
Helper.

.. _Linode's Network Helper: https://www.linode.com/docs/platform/network-helper

clonefrom
---------
Setting the clonefrom option to a specified instance enables the new instance to be
cloned from the named instance instead of being created from scratch. If using the
clonefrom option, it is likely a good idea to also specify ``script_args: -C`` if a
minion is already installed on the to-be-cloned instance. See the `Cloning`_ section
below for more information.


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
