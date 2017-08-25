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

Salt-api must be installed and configured on the salt master.


Configuration
=============

Configuration of the client virtual machine (using VirtualBox, VMware, etc)
will be done by Vagrant as specified in the Vagrantfile on the host machine.

Salt-cloud will push the commands to install and provision a salt minion on
the virtual machine, so you need not (perhaps **should** not) provision salt
in your Vagrantfile.

Because the Vagrant driver does not use an actual cloud provider host, the salt master
must fill the role usually performed by a vendor's cloud management system.
In order to do that, you must configure your salt master as a salt-api server,
and supply credentials to use it. (See `Provisioning salt-api`_ below.)

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers file or any file in
    # the /etc/salt/cloud.providers.d/ directory.

    my-vagrant-config:
      minion:
        master: 111.222.333.444
      provider: vagrant
      # following is the authorization for the salt-api engine on the salt master
      api_eauth: pam
      api_username: genericadminuser
      api_password: insecurepassword1


Profiles
========

Vagrant requires a profile to be configured for each machine that needs Salt
installed. The initial profile can be set up at ``/etc/salt/cloud.profiles``
or in the ``/etc/salt/cloud.profiles.d/`` directory.

Each profile requires a ``vagrantfile`` parameter. If the Vagrantfile has
definitions for `multiple machines`_ then you need a ``machine`` parameter,

.. _`multiple machines`: https://www.vagrantup.com/docs/multi-machine/
as well as either
an ``key_filename`` or a ``password``.

Profile configuration example:

.. code-block:: yaml

    # /etc/salt/cloud.profiles.d/vagrant.conf

    vagrant-machine:
      host: my-vhost  # the Salt id of the virtual machine's host computer.
      provider: my-vagrant-config
      cwd: /srv/machines  # the path to your Virtualbox file.
      runas: my-username  # the username who defined the Vagrantbox on the host
      vagrant_up_timeout: 180 # timeout for cmd.run of the "vagrant up" command (seconds)


The machine can now be created and configured with the following command:

.. code-block:: bash

    salt-cloud -p vagrant-machine my-machine

This will create the machine specified by the cloud profile
``vagrant-machine``, and will give the machine the minion id of
``my-machine``. If the command was executed on the salt-master, its Salt
key will automatically be accepted on the master.

Once a salt-minion has been successfully installed on the instance, connectivity
to it can be verified with Salt:

.. code-block:: bash

    salt my-machine test.ping


Provisioning using salt-api (example)
=====================================

In order to query or control minions it created, the driver needs to send commands
to the VM host computer via the salt master.
It does that using the network interface of salt-api.

The salt-api is not enabled by default. The following example shows a
simple installation.

This example assumes:

- your Salt master's Salt id is "bevymaster"
- it will also be your salt-cloud controller
- it is at hardware address 10.124.29.190
- it has an administrative user named "vagrant"
- the password for user "vagrant" is "vagrant"
- it is running a recent Debian family OS (like Ubuntu server)
- your workstation is a Salt minion of bevymaster
- your workstation's minion id is "my_laptop"
- the VM you want to start is on "my_laptop" at "/projects/bevy_master/Vagrantfile"
- a user named "my_username" owns the Vagrant box files

.. code-block:: ruby

    # -*- mode: ruby -*-
    # file /projects/bevy_master/Vagrantfile on host computer "my_laptop"
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

      # add a bridged network interface, guess MacOS names first
      interface_guesses = ['en0: Ethernet', 'en1: Wi-Fi (AirPort)', get_good_ifc()]
      config.vm.network "public_network", bridge: interface_guesses

      # . . . . . . . . . . . . Define machine QUAIL1 . . . . . . . . . . . . . .
      config.vm.define "quail1", primary: true do |quail_config|
        quail_config.vm.box = "boxesio/xenial64-standard"  # a public VMware & Virtualbox box
        quail_config.vm.hostname = "quail1." + DOMAIN
      end
    end

.. code-block:: yaml

    # file /etc/salt/cloud.profiles.d/my_vagrant_profiles.conf on bevy_master
    q1:
      host: my_laptop  # the Salt id of your virtual machine host
      machine: quail1   # a machine name in the Vagrantfile (if not primary)
      runas: my_username  # owner of Vagrant box files on "my_laptop"
      cwd: '/projects/bevy_master' # the path (on "my_laptop") of the Vagrantfile
      provider: my_vagrant_provider  # name of entry in provider.conf file

.. code-block:: yaml

    # file /etc/salt/cloud.providers.d/vagrant_provider.conf on bevy_master
    my_vagrant_provider:
      driver: vagrant
      api_eauth: pam
      api_username: vagrant  # supply some sudo-group member's name
      api_password: vagrant  # and password on the salt master
      minion:
        master: 10.124.29.190  # the hard address of the master

.. code-block:: yaml

    # file /etc/salt/master.d/auth.conf on bevy_master
    #  using salt-api ... members of the 'sudo' group can do anything ...
    external_auth:
      pam:
        sudo%:
          - .*
          - '@wheel'
          - '@runner'
          - '@jobs'

.. code-block:: yaml

    # file /etc/salt/master.d/api.conf on bevy_master
    # see https://docs.saltstack.com/en/latest/ref/netapi/all/salt.netapi.rest_cherrypy.html
    rest_cherrypy:
      host: 0.0.0.0
      port: 4507  # why not use one near Salt master?
      ssl_crt: /etc/pki/tls/certs/localhost.crt
      ssl_key: /etc/pki/tls/certs/localhost.key
      thread_pool: 30
      socket_queue_size: 10

.. code-block:: yaml

    # file /srv/salt/salt_api.sls on your Salt master
    # . . . install the salt_api server . . .
    salt-api:
      pkg.installed:
        - unless:
          - salt-api --version
    #
    python-pip:
      pkg.installed
    cherrypy:
      pip.installed:
        - require:
          - pkg: python-pip
    #
    create-cert:
      module.run:
        - name: tls.create_self_signed_cert
        - kwargs:
          - O: 'The Round Table'
          - L: 'Camelot'
          - emailAddress: arthur@roundtable.org
    #
    salt-api-service:
      service.running:
        - name: salt-api
        - enable: True
        - watch:
          - pkg: salt-api


Create and use your new Salt minion
-----------------------------------

- Typing on the Salt master computer...

.. code-block:: bash

    sudo salt-call state.apply salt_api
    sudo salt-cloud -p q1 v1
    sudo salt v1 network.ip_addrs
      [ you get a list of ip addresses, including the bridged one ]

- logged in to your laptop (or some computer known to github)...

.. code-block:: bash

    ssh -A vagrant@< the bridged network address >
      [ or perhaps ]
    vagrant ssh quail1

- then typing on your new node "v1" (a.k.a. quail1.bevy1.test)...

.. code-block:: bash

    password: vagrant
      [ stuff types out ... ]
    ls -al /vagrant
      [ should be shared /home/my_username from my_laptop ]
    sudo apt update
    sudo apt install git
    git clone ssh://git@github.com/yourID/your_project
    # etc...

