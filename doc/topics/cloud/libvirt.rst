============================
Getting Started With Libvirt
============================

Libvirt is a toolkit to interact with the virtualization capabilities of recent versions
of Linux (and other OSes). This driver Salt cloud provider is currently geared towards
libvirt with qemu-kvm.

https://libvirt.org/

Host Dependencies
=================
* libvirt >= 1.2.18 (older might work)

Salt-Cloud Dependencies
=======================
* libvirt-python

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
      # work around flag for XML validation errors while cloning
      validate_xml: no

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
      # grains to add to the minion
      grains:
        clones-are-awesome: true
      # override minion settings
      minion:
        master: 192.168.16.1
        master_port: 5506


The profile can be realized now with a salt command:

.. code-block:: bash

    salt-cloud -p centos7 my-centos7-clone

This will create an instance named ``my-centos7-clone`` on the cloud host. Also
the minion id will be set to ``my-centos7-clone``.

If the command was executed on the salt-master, its Salt key will automatically
be accepted on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt my-centos7-clone test.version


Required Settings
=================
The following settings are always required for libvirt:

.. code-block:: yaml

    centos7:
      provider: local-kvm
      # the domain to clone
      base_domain: base-centos7-64


SSH Key Authentication
======================
Instead of specifying a password, an authorized key can be used for the minion setup. Ensure that
the ssh user of your base image has the public key you want to use in ~/.ssh/authorized_keys.  If
you want to use a non-root user you will likely want to configure salt-cloud to use sudo.

An example using root:

.. code-block:: yaml

    centos7:
      provider: local-kvm
      # the domain to clone
      base_domain: base-centos7-64
      ssh_username: root
      private_key: /path/to/private/key

An example using a non-root user:

.. code-block:: yaml

    centos7:
      provider: local-kvm
      # the domain to clone
      base_domain: base-centos7-64
      ssh_username: centos
      private_key: /path/to/private/key
      sudo: True
      sudo_password: "--redacted--"

Optional Settings
=================

.. code-block:: yaml

    centos7:
      # ssh settings
      # use forwarded agent instead of a local key
      ssh_agent: True
      ssh_port: 4910

      # credentials
      ssh_username: root
      # password will be used for sudo if defined, use sudo_password if using ssh keys
      password: my-secret-password
      private_key: /path/to/private/key
      sudo: True
      sudo_password: "--redacted--"

      # bootstrap options
      deploy_command: sh /tmp/.saltcloud/deploy.sh
      script_args: -F

      # minion config
      grains:
        sushi: more tasty
      # point at the another master at another port
      minion:
        master: 192.168.16.1
        master_port: 5506

      # libvirt settings
      # clone_strategy: [ quick | full ] # default is full
      clone_strategy: quick
      # ip_source: [ ip-learning | qemu-agent ] # default is ip-learning
      ip_source: qemu-agent
      # validate_xml: [ false | true ] # default is true
      validate_xml: false

The ``clone_strategy`` controls how the clone is done. In case of ``full`` the disks
are copied creating a standalone clone. If ``quick`` is used the disks of the base domain
are used as backing disks for the clone. This results in nearly instantaneous clones at
the expense of slower write performance. The quick strategy has a number of requirements:

* The disks must be of type qcow2
* The base domain must be turned off
* The base domain must not change after creating the clone

The ``ip_source`` setting controls how the IP address of the cloned instance is determined.
When using ``ip-learning`` the IP is requested from libvirt. This needs a recent libvirt
version and may only work for NAT/routed networks where libvirt runs the dhcp server.
Another option is to use ``qemu-agent`` this requires that the qemu-agent is installed and
configured to run at startup in the base domain.

The ``validate_xml`` setting is available to disable xml validation by libvirt when cloning.

See also :mod:`salt.cloud.clouds.libvirt`
