============================
Getting Started With Libvirt
============================

Libvirt is a toolkit to interact with the virtualization capabilities of recent versions
of Linux (and other OSes). This driver Salt cloud provider is currently geared towards
libvirt with qemu-kvm.

http://www.proxmox.org/

Dependencies
============
* libvirt >= 1.2.18 (older might work)

Provider Configuration
======================

For every KVM host a provider needs to be set up. The provider currently maps to one libvirt daemon (e.g. one KVM host).

Set up the provider cloud configuration file at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.


.. code-block:: yaml

    # Set up a provider with qemu+ssh protocol
    kvm-via-ssh:
      driver: libvirt
      url: qemu+ssh://user@kvm.company.com/system?socket=/var/run/libvirt/libvirt-sock

    # Or connect to a local libvirt instance
    local-kvm:
      driver: libvirt
      url: qemu:///system

TODO: there's probably more that can be configured.

Cloud Profiles
==============
Virtual machines get cloned from so called Cloud Profiles. Profiles can be set up at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/*.conf``:

* Configure a profile to be used:

.. code-block:: yaml

    centos7:
      # points back at provider configuration
      provider: local-kvm
      base_domain: base-centos7-64
      ip_source: ip-learning
      ssh_username: root
      password: my-very-secret-password
      # /tmp is mounted noexec.. do workaround
      deploy_command: sh /tmp/.saltcloud/deploy.sh
      script_args: -F
      grains:
        clones-are-awesome: true
      minion:
        master: 192.168.16.1
        master_port: 5506


The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p centos7 my-centos7-clone

This will create an instance named ``my-centos7-clone`` on the cloud host.

TODO: this true? The
minion that is installed on this instance will have a ``hostname`` of ``myubuntu``.

If the command was executed on the salt-master, its Salt key will automatically
be signed on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    # salt my-centos7-clone test.ping


Required Settings
=================
The following settings are always required for libvirt:

* Using the new cloud configuration format:

.. code-block:: yaml

    my-proxmox-config:
      driver: proxmox
      user: saltcloud@pve
      password: xyzzy
      url: your.proxmox.host

Optional Settings
=================
Unlike other cloud providers in Salt Cloud, Proxmox does not utilize a
``size`` setting. This is because Proxmox allows the end-user to specify a
more detailed configuration for their instances, than is allowed by many other
cloud providers. The following options are available to be used in a profile,
with their default settings listed.

.. code-block:: yaml

    # Description of the instance.
    desc: <instance_name>

    # How many CPU cores, and how fast they are (in MHz)
    cpus: 1
    cpuunits: 1000

    # How many megabytes of RAM
    memory: 256

    # How much swap space in MB
    swap: 256

    # Whether to auto boot the vm after the host reboots
    onboot: 1

    # Size of the instance disk (in GiB)
    disk: 10

    # Host to create this vm on
    host: myvmhost

    # Nameservers. Defaults to host
    nameserver: 8.8.8.8 8.8.4.4

    # Username and password
    ssh_username: root
    password: <value from PROXMOX.password>

    # The name of the image, from ``salt-cloud --list-images proxmox``
    image: local:vztmpl/ubuntu-12.04-standard_12.04-1_amd64.tar.gz
