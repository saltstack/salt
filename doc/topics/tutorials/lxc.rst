.. _tutorial-lxc:

========================
LXC Management with Salt
========================

.. note::

    This walkthrough assumes basic knowledge of Salt. To get up to speed, check
    out the :doc:`Salt Walkthrough </topics/tutorials/walkthrough>`.

.. warning::

    Some features are only currently available in the ``develop`` branch, and
    will not be available in an official Salt release until the next feature
    release (codenamed "Lithium"). These new features will be clearly labeled.
    

Dependencies
============

Manipulation of LXC containers in Salt requires the minion to have an LXC
version of at least 1.0 (an alpha or beta release of LXC 1.0 is acceptable).
The following distributions are known to have new enough versions of LXC
packaged:

- RHEL/CentOS 6 and later (via EPEL_)
- Fedora (All non-EOL releases)
- Debian 8.0 (Jessie) (not yet released)
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

There are two types of profiles, one for defining the parameters used in
container creation, and one for defining the container's network interface(s).

.. _tutorial-lxc-profiles-container:

Container Profiles
------------------

In the 2014.7 release cycle and earlier, LXC container profiles were all
defined underneath the ``lxc.profile`` config option:

.. code-block:: yaml

    lxc.profile:
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

However, due to the way that :mod:`config.get <salt.modules.config.get>` works,
this means that if a ``lxc.profile`` key is defined in both the master config
file and in a specific minion's config file, that will cause all profiles to be
overwritten for that minion. For greater flexibility, in the next feature
release each container profile should be configured in its own key, in the
format ``lxc.container_profile.profile_name``. For example:

.. code-block:: yaml

    lxc.container_profile.centos:
      template: centos
      backing: lvm
      vgname: vg1
      lvname: lxclv
      size: 10G
    lxc.container_profile.centos_big:
      template: centos
      backing: lvm
      vgname: vg1
      lvname: lxclv
      size: 20G

This way, the ``centos_big`` profile can be redefined for a single minion
without also removing the ``centos`` profile. The legacy usage will still be
supported for a couple release cycles, to allow for some time to update
configurations.

Additionally, in the next feature release, container profiles have been
expanded to support passing template-specific CLI options. Below is a table
describing the parameters which can be configured in container profiles:

================== ===================================== ====================
Parameter          Develop Branch (Next Feature Release) 2014.7.x and Earlier
================== ===================================== ====================
*template*:sup:`1` Yes                                   Yes
*options*:sup:`1`  Yes                                   No
*image*:sup:`1`    Yes                                   Yes
*backing*          Yes                                   Yes
*snapshot*:sup:`2` Yes                                   Yes
*lvname*:sup:`1`   Yes                                   Yes
*fstype*:sup:`1`   Yes                                   Yes
*size*             Yes                                   Yes
================== ===================================== ====================

1. Parameter is only supported for container creation, and will be ignored if
   the profile is used when cloning a container.
2. Parameter is only supported for container cloning, and will be ignored if
   the profile is used when not cloning a container.

.. _tutorial-lxc-profiles-network:

Network Profiles
----------------

In the 2014.7 release cycle and earlier, LXC network profiles were all
defined underneath the ``lxc.nic`` config option:

.. code-block:: yaml

    lxc.nic:
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

However, due to the way that :mod:`config.get <salt.modules.config.get>` works,
this means that if a ``lxc.nic`` key is defined in both the master config file
and in a specific minion's config file, that will cause all network profiles to
be overwritten for that minion. For greater flexibility, in the next feature
release each container profile should be configured in its own key, in the
format ``lxc.network_profile.profile_name``. For example:

.. code-block:: yaml

    lxc.network_profile.centos:
      eth0:
        link: br0
        type: veth
        flags: up
    lxc.network_profile.ubuntu:
      eth0:
        link: lxcbr0
        type: veth
        flags: up

This way, the ``ubuntu`` profile can be redefined for a single minion
without also removing the ``centos`` profile. The legacy usage will still be
supported for a couple release cycles, to allow for some time to update
configurations.

The following are parameters which can be configured in network profiles. These
will directly correspond to a parameter in an LXC configuration file (see ``man
5 lxc.container.conf``).

- **type** - Corresponds to **lxc.network.type**
- **link** - Corresponds to **lxc.network.link**
- **flags** - Corresponds to **lxc.network.flags**

Interface-specific options (MAC address, IPv4/IPv6, etc.) can be passed on a
container-by-container basis.


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

The :mod:`lxc.images <salt.modules.lxc.images>` function (new in the next
feature release) can be used to list the available images. Alternatively, the
releases can be viewed on http://images.linuxcontainers.org/images/. The images
are organized in such a way that the dist, release, and arch can be determined
using the following URL format:
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

The resulting tarball can then be placed alongside the files in the salt
fileserver and referenced using a ``salt://`` URL. To create a container using
an image, use the ``image`` parameter with :mod:`lxc.create
<salt.modules.lxc.create>`:

.. code-block:: bash

    salt myminion lxc.create new-cent6 image=salt://path/to/cent6.tar.gz


Container Management Using States
=================================

Several states are being renamed for the next feature release. The information
in this tutorial refers to the new states. For 2014.7.x and earlier, please
refer to the :mod:`documentation for the LXC states <salt.states.lxc>`.
