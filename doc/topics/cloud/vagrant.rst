.. _getting-started-with-vagrant:

============================
Getting Started With Vagrant
============================

The Vagrant driver is a new, experimental driver for spinning up a VagrantBox
virtual machine, and installing Salt on it.

Dependencies
============
The Vagrant driver itself has no external dependencies.

The machine which will host the VagrantBox must be an already existing minion
of the cloud server's Salt master.
It must have Vagrant_ installed, and a Vagrant-compatible virtual machine engine,
such as VirtualBox_.
(Note: The Vagrant driver does not depend on the salt-cloud VirtualBox driver in any way.)

.. _Vagrant: https://www.vagrantup.com/
.. _VirtualBox: https://www.virtualbox.org/

\[Caution: The version of Vagrant packaged for ``apt install`` in Ubuntu 16.04 will not connect a bridged
network adapter correctly. Use a version downloaded directly from the web site.\]

Include the Vagrant guest editions plugin:
``vagrant plugin install vagrant-vbguest``.

Configuration
=============

Configuration of the client virtual machine (using VirtualBox, VMware, etc)
will be done by Vagrant as specified in the Vagrantfile on the host machine.

Salt-cloud will push the commands to install and provision a salt minion on
the virtual machine, so you need not (perhaps **should** not) provision salt
in your Vagrantfile, in most cases.

If, however, your cloud master cannot open an SSH connection to the child VM,
you may **need** to let Vagrant provision the VM with Salt, and use some other
method (such as passing a pillar dictionary to the VM) to pass the master's
IP address to the VM. The VM can then attempt to reach the salt master in the
usual way for non-cloud minions. Specify the profile configuration argument
as ``deploy: False`` to prevent the cloud master from trying.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers file or any file in
    # the /etc/salt/cloud.providers.d/ directory.

    my-vagrant-config:
      minion:
        master: 111.222.333.444
      provider: vagrant


Because the Vagrant driver needs a place to store the mapping between the
node name you use for Salt commands and the Vagrantfile which controls the VM,
you must configure your salt minion as a Salt smb server.
(See `host provisioning example`_ below.)

Profiles
========

Vagrant requires a profile to be configured for each machine that needs Salt
installed. The initial profile can be set up at ``/etc/salt/cloud.profiles``
or in the ``/etc/salt/cloud.profiles.d/`` directory.

Each profile requires a ``vagrantfile`` parameter. If the Vagrantfile has
definitions for `multiple machines`_ then you need a ``machine`` parameter,

.. _`multiple machines`: https://www.vagrantup.com/docs/multi-machine/

Salt-cloud uses SSH to provision the minion. There must be a routable path
from the cloud master to the VM. Usually, you will want to use
a bridged network adapter for SSH. The address may not be known until
DHCP assigns it. If ``ssh_host`` is not defined, and ``target_network``
is defined, the driver will attempt to read the address from the output
of an ``ifconfig`` command. Lacking either setting,
the driver will try to use the value Vagrant returns as its ``ssh_host``,
which will work only if the cloud master is running somewhere on the same host.

The ``target_network`` setting should be used
to identify the IP network your bridged adapter is expected to appear on.
Use CIDR notation, like ``target_network: '2001:DB8::/32'``
or ``target_network: '192.0.2.0/24'``.

Profile configuration example:

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/vagrant.conf

    vagrant-machine:
      host: my-vhost  # the Salt id of the virtual machine's host computer.
      provider: my-vagrant-config
      cwd: /srv/machines  # the path to your Vagrantfile.
      vagrant_runas: my-username  # the username who defined the Vagrantbox on the host
      # vagrant_up_timeout: 300 # (seconds) timeout for cmd.run of the "vagrant up" command
      # vagrant_provider: '' # option for "vagrant up" like: "--provider vmware_fusion"
      # ssh_host: None  # "None" means try to find the routable IP address from "ifconfig"
      # ssh_username: '' # also required when ssh_host is used.
      # target_network: None  # Expected CIDR address range of your bridged network
      # force_minion_config: false  # Set "true" to re-purpose an existing VM

The machine can now be created and configured with the following command:

.. code-block:: bash

    salt-cloud -p vagrant-machine my-id

This will create the machine specified by the cloud profile
``vagrant-machine``, and will give the machine the minion id of
``my-id``. If the cloud master is also the salt-master, its Salt
key will automatically be accepted on the master.

Once a salt-minion has been successfully installed on the instance, connectivity
to it can be verified with Salt:

.. code-block:: bash

    salt my-id test.version

.. _host provisioning example:

Provisioning a Vagrant cloud host (example)
===========================================

In order to query or control minions it created, each host
minion needs to track the Salt node names associated with
any guest virtual machines on it.
It does that using a Salt sdb database.

The Salt sdb is not configured by default. The following example shows a
simple installation.

This example assumes:

- you are on a large network using the 10.x.x.x IP address space
- your Salt master's Salt id is "bevymaster"
- it will also be your salt-cloud controller
- it is at hardware address 10.124.30.7
- it is running a recent Debian family Linux (raspbian)
- your workstation is a Salt minion of bevymaster
- your workstation's minion id is "my_laptop"
- VirtualBox has been installed on "my_laptop" (apt install is okay)
- Vagrant was installed from vagrantup.com. (not the 16.04 Ubuntu apt)
- "my_laptop" has done "vagrant plugin install vagrant-vbguest"
- the VM you want to start is on "my_laptop" at "/home/my_username/Vagrantfile"

.. code-block:: yaml

    # file /etc/salt/minion.d/vagrant_sdb.conf on host computer "my_laptop"
    #  -- this sdb database is required by the Vagrant module --
    vagrant_sdb_data:  # The sdb database must have this name.
      driver: sqlite3  # Let's use SQLite to store the data ...
      database: /var/cache/salt/vagrant.sqlite  # ... in this file ...
      table: sdb  # ... using this table name.
      create_table: True  # if not present

Remember to re-start your minion after changing its configuration files...

    ``sudo systemctl restart salt-minion``

.. code-block:: ruby

    # -*- mode: ruby -*-
    # file /home/my_username/Vagrantfile on host computer "my_laptop"
    BEVY = "bevy1"
    DOMAIN = BEVY + ".test"  # .test is an ICANN reserved non-public TLD

    # must supply a list of names to avoid Vagrant asking for interactive input
    def get_good_ifc()   # try to find a working Ubuntu network adapter name
      addr_infos = Socket.getifaddrs
      addr_infos.each do |info|
        a = info.addr
        if a and a.ip? and not a.ip_address.start_with?("127.")
         return info.name
         end
      end
      return "eth0"  # fall back to an old reliable name
    end

    Vagrant.configure(2) do |config|
      config.ssh.forward_agent = true  # so you can use git ssh://...

      # add a bridged network interface. (try to detect name, then guess MacOS names, too)
      interface_guesses = [get_good_ifc(), 'en0: Ethernet', 'en1: Wi-Fi (AirPort)']
      config.vm.network "public_network", bridge: interface_guesses
      if ARGV[0] == "up"
        puts "Trying bridge network using interfaces: #{interface_guesses}"
      end
      config.vm.provision "shell", inline: "ip address", run: "always"  # make user feel good

      # . . . . . . . . . . . . Define machine QUAIL1 . . . . . . . . . . . . . .
      config.vm.define "quail1", primary: true do |quail_config|
        quail_config.vm.box = "boxesio/xenial64-standard"  # a public VMware & Virtualbox box
        quail_config.vm.hostname = "quail1." + DOMAIN  # supply a name in our bevy
        quail_config.vm.provider "virtualbox" do |v|
            v.memory = 1024       # limit memory for the virtual box
            v.cpus = 1
            v.linked_clone = true # make a soft copy of the base Vagrant box
            v.customize ["modifyvm", :id, "--natnet1", "192.168.128.0/24"]  # do not use 10.x network for NAT
        end
      end
    end

.. code-block:: yaml

    # file /etc/salt/cloud.profiles.d/my_vagrant_profiles.conf on bevymaster
    q1:
      host: my_laptop  # the Salt id of your virtual machine host
      machine: quail1   # a machine name in the Vagrantfile (if not primary)
      vagrant_runas: my_username  # owner of Vagrant box files on "my_laptop"
      cwd: '/home/my_username' # the path (on "my_laptop") of the Vagrantfile
      provider: my_vagrant_provider  # name of entry in provider.conf file
      target_network: '10.0.0.0/8'  # VM external address will be somewhere here

.. code-block:: yaml

    # file /etc/salt/cloud.providers.d/vagrant_provider.conf on bevymaster
    my_vagrant_provider:
      driver: vagrant
      minion:
        master: 10.124.30.7  # the hard address of the master


Create and use your new Salt minion
-----------------------------------

- Typing on the Salt master computer ``bevymaster``, tell it to create a new minion named ``v1`` using profile ``q1``...

.. code-block:: bash

    sudo salt-cloud -p q1 v1
    sudo salt v1 network.ip_addrs
      [ you get a list of IP addresses, including the bridged one ]

- logged in to your laptop (or some other computer known to GitHub)...

    \[NOTE:\] if you are using MacOS, you need to type ``ssh-add -K`` after each boot,
    unless you use one of the methods in `this gist`_.

.. _this gist: https://github.com/jirsbek/SSH-keys-in-macOS-Sierra-keychain

.. code-block:: console

    ssh -A vagrant@< the bridged network address >
      # [ or, if you are at /home/my_username/ on my_laptop ]
    vagrant ssh quail1

- then typing on your new node "v1" (a.k.a. quail1.bevy1.test)...

.. code-block:: console

    password: vagrant
      # [ stuff types out ... ]

    ls -al /vagrant
      # [ should be shared /home/my_username from my_laptop ]

    # you can access other network facilities using the ssh authorization
    # as recorded in your ~.ssh/ directory on my_laptop ...

    sudo apt update
    sudo apt install git
    git clone ssh://git@github.com/yourID/your_project
    # etc...

