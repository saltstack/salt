.. _tutorial-lxc:

========================
LXC Management with Salt
========================

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :ref:`Salt Walkthrough <tutorial-salt-walk-through>`.

Dependencies
============

Manipulation of LXC containers in Salt requires the minion to have an LXC
version of at least 1.0 (an alpha or beta release of LXC 1.0 is acceptable).
The following distributions are known to have new enough versions of LXC
packaged:

- RHEL/CentOS 6 and later (via EPEL_)
- Fedora (All non-EOL releases)
- Debian 8.0 (Jessie)
- Ubuntu 14.04 LTS and later (LXC templates are packaged separately as
  **lxc-templates**, it is recommended to also install this package)
- openSUSE 13.2 and later

.. _EPEL: https://fedoraproject.org/wiki/EPEL


.. _tutorial-lxc-profiles:

Profiles
========

Profiles allow for a sort of shorthand for commonly-used
configurations to be defined in the minion config file, :ref:`grains
<targeting-grains>`, :ref:`pillar <pillar>`, or the master config file. The
profile is retrieved by Salt using the :mod:`config.get
<salt.modules.config.get>` function, which looks in those locations, in that
order. This allows for profiles to be defined centrally in the master config
file, with several options for overriding them (if necessary) on groups of
minions or individual minions.

There are two types of profiles:

    - One for defining the parameters used in container creation/clone.
    - One for defining the container's network interface(s) settings.

.. _tutorial-lxc-profiles-container:

Container Profiles
------------------

LXC container profiles are defined defined underneath the
``lxc.container_profile`` config option:

.. code-block:: yaml

    lxc.container_profile:
      centos:
        template: centos
        backing: lvm
        vgname: vg1
        lvname: lxclv
        size: 10G
      centos_big:
        template: centos
        backing: lvm
        vgname: vg1
        lvname: lxclv
        size: 20G

Profiles are retrieved using the :mod:`config.get <salt.modules.config.get>`
function, with the **recurse** merge strategy. This means that a profile can be
defined at a lower level (for example, the master config file) and then parts
of it can be overridden at a higher level (for example, in pillar data).
Consider the following container profile data:

**In the Master config file:**

.. code-block:: yaml

    lxc.container_profile:
      centos:
        template: centos
        backing: lvm
        vgname: vg1
        lvname: lxclv
        size: 10G

**In the Pillar data**

.. code-block:: yaml

    lxc.container_profile:
      centos:
        size: 20G

Any minion with the above Pillar data would have the **size** parameter in the
**centos** profile overridden to 20G, while those minions without the above
Pillar data would have the 10G **size** value. This is another way of achieving
the same result as the **centos_big** profile above, without having to define
another whole profile that differs in just one value.

.. note::

    In the 2014.7.x release cycle and earlier, container profiles are defined
    under ``lxc.profile``. This parameter will still work in version 2015.5.0,
    but is deprecated and will be removed in a future release. Please note
    however that the profile merging feature described above will only work
    with profiles defined under ``lxc.container_profile``, and only in versions
    2015.5.0 and later.

Additionally, in version 2015.5.0 container profiles have been expanded to
support passing template-specific CLI options to :mod:`lxc.create
<salt.modules.lxc.create>`. Below is a table describing the parameters which
can be configured in container profiles:

================== ================== ====================
Parameter          2015.5.0 and Newer 2014.7.x and Earlier
================== ================== ====================
*template*:sup:`1` Yes                Yes
*options*:sup:`1`  Yes                No
*image*:sup:`1`    Yes                Yes
*backing*          Yes                Yes
*snapshot*:sup:`2` Yes                Yes
*lvname*:sup:`1`   Yes                Yes
*fstype*:sup:`1`   Yes                Yes
*size*             Yes                Yes
================== ================== ====================

1. Parameter is only supported for container creation, and will be ignored if
   the profile is used when cloning a container.
2. Parameter is only supported for container cloning, and will be ignored if
   the profile is used when not cloning a container.

.. _tutorial-lxc-profiles-network:

Network Profiles
----------------
LXC network profiles are defined defined underneath the ``lxc.network_profile``
config option.
By default, the module uses a DHCP based configuration and try to guess a bridge to
get connectivity.


.. warning::

   on pre **2015.5.2**, you need to specify explicitly the network bridge

.. code-block:: yaml

    lxc.network_profile:
      centos:
        eth0:
          link: br0
          type: veth
          flags: up
      ubuntu:
        eth0:
          link: lxcbr0
          type: veth
          flags: up

As with container profiles, network profiles are retrieved using the
:mod:`config.get <salt.modules.config.get>` function, with the **recurse**
merge strategy. Consider the following network profile data:

**In the Master config file:**

.. code-block:: yaml

    lxc.network_profile:
      centos:
        eth0:
          link: br0
          type: veth
          flags: up

**In the Pillar data**

.. code-block:: yaml

    lxc.network_profile:
      centos:
        eth0:
          link: lxcbr0

Any minion with the above Pillar data would use the **lxcbr0** interface as the
bridge interface for any container configured using the **centos** network
profile, while those minions without the above Pillar data would use the
**br0** interface for the same.

.. note::

    In the 2014.7.x release cycle and earlier, network profiles are defined
    under ``lxc.nic``. This parameter will still work in version 2015.5.0, but
    is deprecated and will be removed in a future release. Please note however
    that the profile merging feature described above will only work with
    profiles defined under ``lxc.network_profile``, and only in versions
    2015.5.0 and later.

The following are parameters which can be configured in network profiles. These
will directly correspond to a parameter in an LXC configuration file (see ``man
5 lxc.container.conf``).

- **type** - Corresponds to **lxc.network.type**
- **link** - Corresponds to **lxc.network.link**
- **flags** - Corresponds to **lxc.network.flags**

Interface-specific options (MAC address, IPv4/IPv6, etc.) must be passed on a
container-by-container basis, for instance using the ``nic_opts`` argument to
:mod:`lxc.create <salt.modules.lxc.create>`:

.. code-block:: bash

    salt myminion lxc.create container1 profile=centos network_profile=centos nic_opts='{eth0: {ipv4: 10.0.0.20/24, gateway: 10.0.0.1}}'

.. warning::

    The ``ipv4``, ``ipv6``, ``gateway``, and ``link`` (bridge) settings in
    network profiles / nic_opts will only work if the container doesn't redefine
    the network configuration (for example in
    ``/etc/sysconfig/network-scripts/ifcfg-<interface_name>`` on RHEL/CentOS,
    or ``/etc/network/interfaces`` on Debian/Ubuntu/etc.). Use these with
    caution. The container images installed using the ``download`` template,
    for instance, typically are configured for eth0 to use DHCP, which will
    conflict with static IP addresses set at the container level.

.. note::

    For LXC < 1.0.7 and DHCP support, set ``ipv4.gateway: 'auto'`` is your
    network profile, ie.::

        lxc.network_profile.nic:
          debian:
            eth0:
              link: lxcbr0
              ipv4.gateway: 'auto'


Old lxc support (<1.0.7)
------------------------

With saltstack **2015.5.2** and above, normally the setting is autoselected, but
before, you'll need to teach your network profile to set
**lxc.network.ipv4.gateway** to **auto** when using a classic ipv4 configuration.

Thus you'll need

.. code-block:: yaml

      lxc.network_profile.foo:
        etho:
          link: lxcbr0
          ipv4.gateway: auto

Tricky network setups Examples
------------------------------
This example covers how to make a container with both an internal ip and a
public routable ip, wired on two veth pairs.

The another interface which receives directly a public routable ip can't be on
the first interface that we reserve for private inter LXC networking.

.. code-block:: yaml

    lxc.network_profile.foo:
      eth0: {gateway: null, bridge: lxcbr0}
      eth1:
        # replace that by your main interface
        'link': 'br0'
        'mac': '00:16:5b:01:24:e1'
        'gateway': '2.20.9.14'
        'ipv4': '2.20.9.1'

Creating a Container on the CLI
===============================

From a Template
---------------

LXC is commonly distributed with several template scripts in
/usr/share/lxc/templates. Some distros may package these separately in an
**lxc-templates** package, so make sure to check if this is the case.

There are LXC template scripts for several different operating systems, but
some of them are designed to use tools specific to a given distribution. For
instance, the ``ubuntu`` template uses deb_bootstrap, the ``centos`` template
uses yum, etc., making these templates impractical when a container from a
different OS is desired.

The :mod:`lxc.create <salt.modules.lxc.create>` function is used to create
containers using a template script. To create a CentOS container named
``container1`` on a CentOS minion named ``mycentosminion``, using the
``centos`` LXC template, one can simply run the following command:

.. code-block:: bash

    salt mycentosminion lxc.create container1 template=centos


For these instances, there is a ``download`` template which retrieves minimal
container images for several different operating systems. To use this template,
it is necessary to provide an ``options`` parameter when creating the
container, with three values:

1. **dist** - the Linux distribution (i.e. ``ubuntu`` or ``centos``)
2. **release** - the release name/version (i.e. ``trusty`` or ``6``)
3. **arch** - CPU architecture (i.e. ``amd64`` or ``i386``)

The :mod:`lxc.images <salt.modules.lxc.images>` function (new in version
2015.5.0) can be used to list the available images. Alternatively, the releases
can be viewed on http://images.linuxcontainers.org/images/. The images are
organized in such a way that the **dist**, **release**, and **arch** can be
determined using the following URL format:
``http://images.linuxcontainers.org/images/dist/release/arch``. For example,
``http://images.linuxcontainers.org/images/centos/6/amd64`` would correspond to
a **dist** of ``centos``, a **release** of ``6``, and an **arch** of ``amd64``.

Therefore, to use the ``download`` template to create a new 64-bit CentOS 6
container, the following command can be used:

.. code-block:: bash

    salt myminion lxc.create container1 template=download options='{dist: centos, release: 6, arch: amd64}'

.. note::

    These command-line options can be placed into a :ref:`container profile
    <tutorial-lxc-profiles-container>`, like so:

    .. code-block:: yaml

        lxc.container_profile.cent6:
          template: download
          options:
            dist: centos
            release: 6
            arch: amd64

    The ``options`` parameter is not supported in profiles for the 2014.7.x
    release cycle and earlier, so it would still need to be provided on the
    command-line.


Cloning an Existing Container
-----------------------------

To clone a container, use the :mod:`lxc.clone <salt.modules.lxc.clone>`
function:

.. code-block:: bash

    salt myminion lxc.clone container2 orig=container1


Using a Container Image
-----------------------

While cloning is a good way to create new containers from a common base
container, the source container that is being cloned needs to already exist on
the minion. This makes deploying a common container across minions difficult.
For this reason, Salt's :mod:`lxc.create <salt.modules.lxc.create>` is capable
of installing a container from a tar archive of another container's rootfs. To
create an image of a container named ``cent6``, run the following command as
root:

.. code-block:: bash

    tar czf cent6.tar.gz -C /var/lib/lxc/cent6 rootfs

.. note::

    Before doing this, it is recommended that the container is stopped.

The resulting tarball can then be placed alongside the files in the salt
fileserver and referenced using a ``salt://`` URL. To create a container using
an image, use the ``image`` parameter with :mod:`lxc.create
<salt.modules.lxc.create>`:

.. code-block:: bash

    salt myminion lxc.create new-cent6 image=salt://path/to/cent6.tar.gz

.. note:: Making images of containers with LVM backing

    For containers with LVM backing, the rootfs is not mounted, so it is
    necessary to mount it first before creating the tar archive. When a
    container is created using LVM backing, an empty ``rootfs`` dir is handily
    created within ``/var/lib/lxc/container_name``, so this can be used as the
    mountpoint. The location of the logical volume for the container will be
    ``/dev/vgname/lvname``, where ``vgname`` is the name of the volume group,
    and ``lvname`` is the name of the logical volume. Therefore, assuming a
    volume group of ``vg1``, a logical volume of ``lxc-cent6``, and a container
    name of ``cent6``, the following commands can be used to create a tar
    archive of the rootfs:

    .. code-block:: bash

        mount /dev/vg1/lxc-cent6 /var/lib/lxc/cent6/rootfs
        tar czf cent6.tar.gz -C /var/lib/lxc/cent6 rootfs
        umount /var/lib/lxc/cent6/rootfs

.. warning::

    One caveat of using this method of container creation is that
    ``/etc/hosts`` is left unmodified.  This could cause confusion for some
    distros if salt-minion is later installed on the container, as the
    functions that determine the hostname take ``/etc/hosts`` into account.

    Additionally, when creating an rootfs image, be sure to remove
    ``/etc/salt/minion_id`` and make sure that ``id`` is not defined in
    ``/etc/salt/minion``, as this will cause similar issues.


Initializing a New Container as a Salt Minion
=============================================

The above examples illustrate a few ways to create containers on the CLI, but
often it is desirable to also have the new container run as a Minion. To do
this, the :mod:`lxc.init <salt.modules.lxc.init>` function can be used. This
function will do the following:

1. Create a new container
2. Optionally set password and/or DNS
3. Bootstrap the minion (using either salt-bootstrap_ or a custom command)

.. _salt-bootstrap: https://github.com/saltstack/salt-bootstrap

By default, the new container will be pointed at the same Salt Master as the
host machine on which the container was created. It will then request to
authenticate with the Master like any other bootstrapped Minion, at which point
it can be accepted.

.. code-block:: bash

    salt myminion lxc.init test1 profile=centos
    salt-key -a test1

For even greater convenience, the :mod:`LXC runner <salt.runners.lxc>` contains
a runner function of the same name (:mod:`lxc.init <salt.runners.lxc.init>`),
which creates a keypair, seeds the new minion with it, and pre-accepts the key,
allowing for the new Minion to be created and authorized in a single step:

.. code-block:: bash

    salt-run lxc.init test1 host=myminion profile=centos


Running Commands Within a Container
===================================

For containers which are not running their own Minion, commands can be run
within the container in a manner similar to using (:mod:`cmd.run
<salt.modules.cmdmod.run`). The means of doing this have been changed
significantly in version 2015.5.0 (though the deprecated behavior will still be
supported for a few releases). Both the old and new usage are documented
below.

2015.5.0 and Newer
------------------

New functions have been added to mimic the behavior of the functions in the
:mod:`cmd <salt.modules.cmdmod>` module. Below is a table with the :mod:`cmd
<salt.modules.cmdmod>` functions and their :mod:`lxc <salt.modules.lxc>` module
equivalents:


======================================= ====================================================== ===================================================
Description                             :mod:`cmd <salt.modules.cmdmod>` module                :mod:`lxc <salt.modules.lxc>` module
======================================= ====================================================== ===================================================
Run a command and get all output        :mod:`cmd.run <salt.modules.cmdmod.run>`               :mod:`lxc.run <salt.modules.lxc.run>`
Run a command and get just stdout       :mod:`cmd.run_stdout <salt.modules.cmdmod.run_stdout>` :mod:`lxc.run_stdout <salt.modules.lxc.run_stdout>`
Run a command and get just stderr       :mod:`cmd.run_stderr <salt.modules.cmdmod.run_stderr>` :mod:`lxc.run_stderr <salt.modules.lxc.run_stderr>`
Run a command and get just the retcode  :mod:`cmd.retcode <salt.modules.cmdmod.retcode>`       :mod:`lxc.retcode <salt.modules.lxc.retcode>`
Run a command and get all information   :mod:`cmd.run_all <salt.modules.cmdmod.run_all>`       :mod:`lxc.run_all <salt.modules.lxc.run_all>`
======================================= ====================================================== ===================================================


2014.7.x and Earlier
--------------------

Earlier Salt releases use a single function (:mod:`lxc.run_cmd
<salt.modules.lxc.run_cmd>`) to run commands within containers. Whether stdout,
stderr, etc. are returned depends on how the function is invoked.


To run a command and return the stdout:

.. code-block:: bash

    salt myminion lxc.run_cmd web1 'tail /var/log/messages'

To run a command and return the stderr:

.. code-block:: bash

    salt myminion lxc.run_cmd web1 'tail /var/log/messages' stdout=False stderr=True

To run a command and return the retcode:

.. code-block:: bash

    salt myminion lxc.run_cmd web1 'tail /var/log/messages' stdout=False stderr=False

To run a command and return all information:

.. code-block:: bash

    salt myminion lxc.run_cmd web1 'tail /var/log/messages' stdout=True stderr=True


Container Management Using salt-cloud
=====================================

Salt cloud uses under the hood the salt runner and module to manage containers,
Please look at :ref:`this chapter <config_lxc>`


Container Management Using States
=================================

Several states are being renamed or otherwise modified in version 2015.5.0. The
information in this tutorial refers to the new states. For
2014.7.x and earlier, please refer to the :mod:`documentation for the LXC
states <salt.states.lxc>`.


Ensuring a Container Is Present
-------------------------------

To ensure the existence of a named container, use the :mod:`lxc.present
<salt.states.lxc.present>` state. Here are some examples:

.. code-block:: yaml

    # Using a template
    web1:
      lxc.present:
        - template: download
        - options:
            dist: centos
            release: 6
            arch: amd64

    # Cloning
    web2:
      lxc.present:
        - clone_from: web-base

    # Using a rootfs image
    web3:
      lxc.present:
        - image: salt://path/to/cent6.tar.gz

    # Using profiles
    web4:
      lxc.present:
        - profile: centos_web
        - network_profile: centos

.. warning::

    The :mod:`lxc.present <salt.states.lxc.present>` state will not modify an
    existing container (in other words, it will not re-create the container).
    If an :mod:`lxc.present <salt.states.lxc.present>` state is run on an
    existing container, there will be no change and the state will return a
    ``True`` result.

The :mod:`lxc.present <salt.states.lxc.present>` state also includes an
optional ``running`` parameter which can be used to ensure that a container is
running/stopped. Note that there are standalone :mod:`lxc.running
<salt.states.lxc.running>` and :mod:`lxc.stopped <salt.states.lxc.stopped>`
states which can be used for this purpose.


Ensuring a Container Does Not Exist
-----------------------------------

To ensure that a named container is not present, use the :mod:`lxc.absent
<salt.states.lxc.absent>` state. For example:

.. code-block:: yaml

    web1:
      lxc.absent


Ensuring a Container is Running/Stopped/Frozen
----------------------------------------------

Containers can be in one of three states:

- **running** - Container is running and active
- **frozen** - Container is running, but all process are blocked and the
  container is essentially non-active until the container is "unfrozen"
- **stopped** - Container is not running

Salt has three states (:mod:`lxc.running <salt.states.lxc.running>`,
:mod:`lxc.frozen <salt.states.lxc.frozen>`, and :mod:`lxc.stopped
<salt.states.lxc.stopped>`) which can be used to ensure a container is in one
of these states:

.. code-block:: yaml

    web1:
      lxc.running

    # Restart the container if it was already running
    web2:
      lxc.running:
        - restart: True

    web3:
      lxc.stopped

    # Explicitly kill all tasks in container instead of gracefully stopping
    web4:
      lxc.stopped:
        - kill: True

    web5:
      lxc.frozen

    # If container is stopped, do not start it (in which case the state will fail)
    web6:
      lxc.frozen:
        - start: False
