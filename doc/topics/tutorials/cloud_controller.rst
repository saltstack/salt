.. _cloud-controller:

==========================
Salt as a Cloud Controller
==========================

In Salt 0.14.0, an advanced cloud control system were introduced, allow
private cloud vms to be managed directly with Salt. This system is generally
referred to as :strong:`Salt Virt`.

The Salt Virt system already exists and is installed within Salt itself, this
means that besides setting up Salt, no additional salt code needs to be
deployed.

.. note::

    The ``libvirt`` python module and the ``certtool`` binary are required.

The main goal of Salt Virt is to facilitate a very fast and simple cloud. The
cloud that can scale and is fully featured. Salt Virt comes with the
ability to set up and manage complex virtual machine networking, powerful
image and disk management, as well as virtual machine migration with and without
shared storage.

This means that Salt Virt can be used to create a cloud from a blade center
and a SAN, but can also create a cloud out of a swarm of Linux Desktops
without a single shared storage system. Salt Virt can make clouds from
truly commodity hardware, but can also stand up the power of specialized
hardware as well.

Setting up Hypervisors
======================

The first step to set up the hypervisors involves getting the correct software
installed and setting up the hypervisor network interfaces.

Installing Hypervisor Software
------------------------------

Salt Virt is made to be hypervisor agnostic but currently the only fully
implemented hypervisor is KVM via libvirt.

The required software for a hypervisor is libvirt and kvm. For advanced
features install libguestfs or qemu-nbd.

.. note::

    Libguestfs and qemu-nbd allow for virtual machine images to be mounted
    before startup and get pre-seeded with configurations and a salt minion

This sls will set up the needed software for a hypervisor, and run the routines
to set up the libvirt pki keys.

.. note::

    Package names and setup used is Red Hat specific, different package names
    will be required for different platforms

.. code-block:: yaml

    libvirt:
      pkg.installed: []
      file.managed:
        - name: /etc/sysconfig/libvirtd
        - contents: 'LIBVIRTD_ARGS="--listen"'
        - require:
          - pkg: libvirt
      virt.keys:
        - require:
          - pkg: libvirt
      service.running:
        - name: libvirtd
        - require:
          - pkg: libvirt
          - network: br0
          - libvirt: libvirt
        - watch:
          - file: libvirt

    libvirt-python:
      pkg.installed: []

    libguestfs:
      pkg.installed:
        - pkgs:
          - libguestfs
          - libguestfs-tools

Hypervisor Network Setup
------------------------

The hypervisors will need to be running a network bridge to serve up network
devices for virtual machines, this formula will set up a standard bridge on
a hypervisor connecting the bridge to eth0:

.. code-block:: yaml

    eth0:
      network.managed:
        - enabled: True
        - type: eth
        - bridge: br0

    br0:
      network.managed:
        - enabled: True
        - type: bridge
        - proto: dhcp
        - require:
          - network: eth0


Virtual Machine Network Setup
-----------------------------

Salt Virt comes with a system to model the network interfaces used by the
deployed virtual machines; by default a single interface is created for the
deployed virtual machine and is bridged to ``br0``. To get going with the
default networking setup, ensure that the bridge interface named ``br0`` exists
on the hypervisor and is bridged to an active network device.

.. note::

    To use more advanced networking in Salt Virt, read the `Salt Virt
    Networking` document:

    :ref:`Salt Virt Networking <vm-nic-profiles>`

Libvirt State
-------------

One of the challenges of deploying a libvirt based cloud is the distribution
of libvirt certificates. These certificates allow for virtual machine
migration. Salt comes with a system used to auto deploy these certificates.
Salt manages the signing authority key and generates keys for libvirt clients
on the master, signs them with the certificate authority and uses pillar to
distribute them. This is managed via the ``libvirt`` state. Simply execute this
formula on the minion to ensure that the certificate is in place and up to
date:

.. note::

    The above formula includes the calls needed to set up libvirt keys.

.. code-block:: yaml

    libvirt_keys:
      virt.keys

Getting Virtual Machine Images Ready
====================================

Salt Virt, requires that virtual machine images be provided as these are not
generated on the fly. Generating these virtual machine images differs greatly
based on the underlying platform.

Virtual machine images can be manually created using KVM and running through
the installer, but this process is not recommended since it is very manual and
prone to errors.

Virtual Machine generation applications are available for many platforms:

kiwi: (openSUSE, SLES, RHEL, CentOS)
  https://suse.github.io/kiwi/

vm-builder:
  https://wiki.debian.org/VMBuilder

  .. seealso:: :formula_url:`vmbuilder-formula`

Once virtual machine images are available, the easiest way to make them
available to Salt Virt is to place them in the Salt file server. Just copy an
image into ``/srv/salt`` and it can now be used by Salt Virt.

For purposes of this demo, the file name ``centos.img`` will be used.

Existing Virtual Machine Images
-------------------------------

Many existing Linux distributions distribute virtual machine images which
can be used with Salt Virt. Please be advised that NONE OF THESE IMAGES ARE
SUPPORTED BY SALTSTACK.

CentOS
~~~~~~

These images have been prepared for OpenNebula but should work without issue with
Salt Virt, only the raw qcow image file is needed:
http://wiki.centos.org/Cloud/OpenNebula

Fedora Linux
~~~~~~~~~~~~

Images for Fedora Linux can be found here:
http://fedoraproject.org/en/get-fedora#clouds

openSUSE
~~~~~~~~

http://download.opensuse.org/repositories/openSUSE:/Leap:/42.1:/Images/images

(look for JeOS-for-kvm-and-xen variant)

SUSE
~~~~

https://www.suse.com/products/server/jeos

Ubuntu Linux
~~~~~~~~~~~~

Images for Ubuntu Linux can be found here:
http://cloud-images.ubuntu.com/

Using Salt Virt
===============

With hypervisors set up and virtual machine images ready, Salt can start
issuing cloud commands.

Start by running a Salt Virt hypervisor info command:

.. code-block:: bash

    salt-run virt.hyper_info

This will query what the running hypervisor stats are and display information
for all configured hypervisors. This command will also validate that the
hypervisors are properly configured.

Now that hypervisors are available a virtual machine can be provisioned. The
``virt.init`` routine will create a new virtual machine:

.. code-block:: bash

    salt-run virt.init centos1 2 512 salt://centos.img

This command assumes that the CentOS virtual machine image is sitting in the
root of the Salt fileserver. Salt Virt will now select a hypervisor to deploy
the new virtual machine on and copy the virtual machine image down to the
hypervisor.

Once the VM image has been copied down the new virtual machine will be seeded.
Seeding the VMs involves setting pre-authenticated Salt keys on the new VM and
if needed, will install the Salt Minion on the new VM before it is started.

.. note::

    The biggest bottleneck in starting VMs is when the Salt Minion needs to be
    installed. Making sure that the source VM images already have Salt
    installed will GREATLY speed up virtual machine deployment.

Now that the new VM has been prepared, it can be seen via the ``virt.query``
command:

.. code-block:: bash

    salt-run virt.query

This command will return data about all of the hypervisors and respective
virtual machines.

Now that the new VM is booted it should have contacted the Salt Master, a
``test.ping`` will reveal if the new VM is running.

Migrating Virtual Machines
==========================

Salt Virt comes with full support for virtual machine migration, and using
the libvirt state in the above formula makes migration possible.

A few things need to be available to support migration. Many operating systems
turn on firewalls when originally set up, the firewall needs to be opened up
to allow for libvirt and kvm to cross communicate and execution migration
routines. On Red Hat based hypervisors in particular port 16514 needs to be
opened on hypervisors:

.. code-block:: bash

    iptables -A INPUT -m state --state NEW -m tcp -p tcp --dport 16514 -j ACCEPT

.. note::

    More in-depth information regarding distribution specific firewall settings can read in:

    :ref:`Opening the Firewall up for Salt <firewall>`

Salt also needs an additional flag to be turned on as well. The ``virt.tunnel``
option needs to be turned on. This flag tells Salt to run migrations securely
via the libvirt TLS tunnel and to use port 16514. Without ``virt.tunnel`` libvirt
tries to bind to random ports when running migrations. To turn on ``virt.tunnel``
simple apply it to the master config file:

.. code-block:: yaml

    virt.tunnel: True

Once the master config has been updated, restart the master and send out a call
to the minions to refresh the pillar to pick up on the change:

.. code-block:: bash

    salt \* saltutil.refresh_modules

Now, migration routines can be run! To migrate a VM, simply run the Salt Virt
migrate routine:

.. code-block:: bash

    salt-run virt.migrate centos <new hypervisor>

VNC Consoles
============

Although not enabled by default, Salt Virt can also set up VNC consoles allowing for remote visual
consoles to be opened up. When creating a new VM using ``virt.init`` pass the ``enable_vnc=True``
parameter to have a console configured for the new VM.

The information from a ``virt.query`` routine will display the vnc console port for the specific vms:

.. code-block:: yaml

  centos
    CPU: 2
    Memory: 524288
    State: running
    Graphics: vnc - hyper6:5900
    Disk - vda:
      Size: 2.0G
      File: /srv/salt-images/ubuntu2/system.qcow2
      File Format: qcow2
    Nic - ac:de:48:98:08:77:
      Source: br0
      Type: bridge

The line `Graphics: vnc - hyper6:5900` holds the key. First the port named,
in this case 5900, will need to be available in the hypervisor's firewall.
Once the port is open, then the console can be easily opened via vncviewer:

.. code-block:: bash

    vncviewer hyper6:5900

By default there is no VNC security set up on these ports, which suggests that
keeping them firewalled and mandating that SSH tunnels be used to access these
VNC interfaces. Keep in mind that activity on a VNC interface that is accessed
can be viewed by any other user that accesses that same VNC interface, and any other
user logging in can also operate with the logged in user on the virtual
machine.

Conclusion
==========

Now with Salt Virt running, new hypervisors can be seamlessly added just by
running the above states on new bare metal machines, and these machines will be
instantly available to Salt Virt.
