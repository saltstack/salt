============================
Getting Started With Proxmox
============================

.. warning::
    This cloud provider will be removed from Salt in version 3009.0 in favor of
    the `saltext.proxmox Salt Extension
    <https://github.com/salt-extensions/saltext-proxmox>`_

Proxmox Virtual Environment is a complete server virtualization management solution,
based on OpenVZ(in Proxmox up to 3.4)/LXC(from Proxmox 4.0 and up) and full virtualization with KVM.
Further information can be found at:

https://www.proxmox.com

Dependencies
============
* IPy >= 0.81
* requests >= 2.2.1

Please note:
This module allows you to create OpenVZ/LXC containers and KVM VMs, but installing Salt on it will only be
done on containers rather than a KVM virtual machine.

* Set up the cloud configuration at
  ``/etc/salt/cloud.providers`` or
  ``/etc/salt/cloud.providers.d/proxmox.conf``:

.. code-block:: yaml

    my-proxmox-config:
      # Set up the location of the salt master
      #
      minion:
        master: saltmaster.example.com

      # Set the PROXMOX access credentials (see below)
      #
      user: myuser@pve
      password: badpass

      # Set the access URL for your PROXMOX host
      #
      url: your.proxmox.host
      driver: proxmox

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Access Credentials
==================
The ``user``, ``password``, and ``url`` will be provided to you by your cloud
host. These are all required in order for the PROXMOX driver to work.


Cloud Profiles
==============
Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/proxmox.conf``:

* Configure a profile to be used:

.. code-block:: yaml

    proxmox-ubuntu:
        provider: my-proxmox-config
        image: local:vztmpl/ubuntu-12.04-standard_12.04-1_amd64.tar.gz
        technology: lxc

        # host needs to be set to the configured name of the proxmox host
        # and not the ip address or FQDN of the server
        host: myvmhost
        ip_address: 192.168.100.155
        password: topsecret


The profile can be realized now with a salt command:

.. code-block:: bash

    # salt-cloud -p proxmox-ubuntu myubuntu

This will create an instance named ``myubuntu`` on the cloud host. The
minion that is installed on this instance will have a ``hostname`` of ``myubuntu``.
If the command was executed on the salt-master, its Salt key will automatically
be signed on the master.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    # salt myubuntu test.version


Required Settings
=================
The following settings are always required for PROXMOX:

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

    # Whether or not to verify the SSL cert on the Proxmox host
    verify_ssl: False

    # Network interfaces, netX
    net0: name=eth0,bridge=vmbr0,ip=dhcp

    # Public key to add to /root/.ssh/authorized_keys.
    pubkey: 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABA...'


QEMU
====

Some functionnalities works differently if you use 'qemu' as technology. In order to create a new VM with qemu, you need to specificy some more information.
You can also clone a qemu template which already is on your Proxmox server.

QEMU profile file (for a new VM):

.. code-block:: yaml

  proxmox-win7:
    # Image of the new VM
    image: image.iso # You can get all your available images using 'salt-cloud --list-images provider_name' (Ex: 'salt-cloud --list-images my-proxmox-config')

    # Technology used to create the VM ('qemu', 'openvz'(on Proxmox <4.x) or 'lxc'(on Proxmox 4.x+))
    technology: qemu

    # Proxmox node name
    host: node_name

    # Proxmox password
    password: your_password

    # Workaround https://github.com/saltstack/salt/issues/27821
    size: ''

    # RAM size (MB)
    memory: 2048

    # OS Type enum (other / wxp / w2k / w2k3 / w2k8 / wvista / win7 / win8 / l24 / l26 / solaris)
    ostype: win7

    # Hard disk location
    sata0: <location>:<size>, format=<qcow2/vmdk/raw>, size=<size>GB #Example: local:120,format=qcow2,size=120GB

    #CD/DVD Drive
    ide2: <content_location>,media=cdrom #Example: local:iso/name.iso,media=cdrom

    # Network Device
    net0:<model>,bridge=<bridge> #Example: e1000,bridge=vmbr0

    # Enable QEMU Guest Agent (0 / 1)
    agent: 1

    # VM name
    name: Test

More information about these parameters can be found on Proxmox API (http://pve.proxmox.com/pve2-api-doc/) under the 'POST' method of nodes/{node}/qemu


QEMU profile file (for a clone):

.. code-block:: yaml

  proxmox-win7:
    # Enable Clone
    clone: True

    # New VM description
    clone_description: 'description'

    # New VM name
    clone_name: 'name'

    # New VM format (qcow2 / raw / vmdk)
    clone_format: qcow2

    # Full clone (1) or Link clone (0)
    clone_full: 0

    # VMID of Template to clone
    clone_from: ID

    # Technology used to create the VM ('qemu' or 'lxc')
    technology: qemu

    # Proxmox node name
    host: node_name

    # Proxmox password
    password: your_password

    # Workaround https://github.com/saltstack/salt/issues/27821
    size: ''

    # Enable the use of a Qemu agent on VM to retrieve the IP-address from.
    agent_get_ip: True

More information can be found on Proxmox API under the 'POST' method of /nodes/{node}/qemu/{vmid}/clone

.. note::
    The Proxmox API offers a lot more options and parameters, which are not yet
    supported by this salt-cloud 'overlay'. Feel free to add your contribution
    by forking the github repository and modifying  the following file:
    ``salt/cloud/clouds/proxmox.py``

    An easy way to support more parameters for VM creation would be to add the
    names of the optional parameters in the 'create_nodes(vm\_)' function, under
    the 'qemu' technology. But it requires you to dig into the code ...
