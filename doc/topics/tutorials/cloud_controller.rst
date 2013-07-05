==========================
Salt as a Cloud Controller
==========================

In Salt 0.14.0 advanced cloud control systems were introduced, allowing for
private cloud vms to be managed directly with Salt. This system is generally
referred to as "Salt Virt".

The Salt Virt system already exists and is installed within Salt itself, this
means that beyond setting up Salt no additional salt code needs to be deployed.

Setting up Hypervisors
======================

The first step to set up the hypervisors involves getting the correct software
installed and setting up the hypervisor network interfaces.

Installing Hypervisor Software
------------------------------

Salt Virt is made to be hypervisor agnostic, but currently the only
implemented hypervisor is KVM via libvirt.

The required software for a hypervisor is libvirt and kvm. For advanced 
features install libguestfs or qemu-nbd.

.. note::

    Libguestfs and qemu-nbd allow for virtual machine images to be mounted
    before startup and get pre-seeded with configurations and a salt minion

A simple sls formula to deploy the required software and service:

.. note::

    Package names used are Red Hat specific, different package names will be
    required for different platforms

.. code-block:: yaml

    libguestfs:
      pkg.installed

    qemu-kvm:
      pkg.installed

    libvirt:
      pkg.installed

    libvirtd:
      service.running:
        - enable: True
        - watch:
          - pkg: libvirt

Network Setup
-------------

Salt virt comes with a system to model the network interfaces used by the
deployed virtual machines, by default a single interface is created for the
deployed virtual machine and is bridged to `br0`. To get going with the default
networking setup ensure that the bridge interface named `br0` exists on the
hypervisor and is bridged to an active network device.

.. note::

    To use more advanced networking in Salt Virt read the `Salt Virt
    Networking` document:

    :doc:`Salt Virt Networking <topics/virt/nic>`

Libvirt State
-------------

One of the challanges of deploying a libvirt based cloud is the distribution
of libvirt certificates. These certificates allow for virtual machine
migration. Salt comes with a system used to auto deploy these certificates.
Salt manages the signing authority key and generates keys for libvirt clients
on the master, signs them with the certificate authority and uses pillar to
distrbute them. This is managed via the ``libvirt`` state. Simply execute this
formula on the minion to ensure that the certificate is in place and up to
date:

.. code-block:: yaml

    libvirt_keys:
      libvirt.keys

Getting Virtual Machine Images Ready
====================================

Salt Virt, requires that virtual machine images be provided as these are not
generated on the fly. Generating these virtual machine images differs greatly
based on the underlying platform.

Virtual machine images can be manually created using KVM and running through
the installer, but this process is not recommended since it is very manual and
prone to errors.

Virtual Machine generation applications are avilable for many platforms:

vm-builder:
  http://wiki.debian.org/VMBuilder

Using Salt Virt
===============

With hypervisors set up and virtual machine images ready, Salt can start
issuing cloud commands.

Start by deploying 
