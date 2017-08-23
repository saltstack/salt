.. _getting-started-with-vagrant:

============================
Getting Started With Vagrant
============================

The Vagrant driver is a new, experimental driver for spinning up a VagrantBox
virtual machine, and installing Salt on it.

Dependencies
============
The Vagrant driver itself has no external dependencies.

The machine which will host the VagrantBox must be an existing Salt minion
and have Vagrant_ installed, and a Vagrant-compatible virtual machine engine.

.. _Vagrant: https://www.vagrantup.com/

Salt-api must be installed and configured on the salt master.


Configuration
=============

Configuration of the client virtual machine (using virtualbox, VMware, etc)
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

Each profile requires a ``vagrantfile``parameter. If the Vagrantfile has
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

This will create the machine specified by the cloud profile,
``vagrant-machine``, and will give the machine the minion id of
``my-machine``. If the command was executed on the salt-master, its Salt
key will automatically be signed on the master.

Once a salt-minion has been successfully installed on the instance, connectivity
to it can be verified with Salt:

.. code-block:: bash

    salt my-machine test.ping


Provisioning salt-api
=====================

In order to query or control minions it created, the driver needs to send commands
to the salt master.  It does that using the network interface to salt-api.

The salt-api is not enabled by default. The following example will provide a
simple installation.

.. code-block:: yaml

    # file /etc/salt/cloud.profiles.d/my_vagrant_profiles.conf
    prof1:
      host: vbox_host  # the Salt id of your virtual machine host
      machine: mach1   # a machine name in the Vagrantfile (if not primary)
      cwd: '/projects/my_project' # the path (on vbox_host) of the Vagrantfile
      ssh_username: vagrant  # a user name which has passwordless sudo
      password: vagrant      # on the target machine you are creating.
      runas: my_linux_name  # owner of Vagrant box files on your workstation
      provider: my_vagrant_provider  # name of entry in provider.conf file

.. code-block:: yaml

    # file /etc/salt/cloud.providers.d/vagrant_provider.conf
    my_vagrant_provider:
      driver: vagrant
      api_eauth: pam
      api_username: vagrant  # supply some sudo-group-member's name
      api_password: vagrant  # and password on the salt master
      minion:
        master: 10.100.9.5  # the hard address of the master

.. code-block:: yaml

    # file /etc/salt/master.d/auth.conf
    #  using salt-api ... members of the 'sudo' group can do anything ...
    external_auth:
      pam:
        sudo%:
          - .*
          - '@wheel'
          - '@runner'
          - '@jobs'

.. code-block:: yaml

    # file /etc/salt/master.d/api.conf
    # see https://docs.saltstack.com/en/latest/ref/netapi/all/salt.netapi.rest_cherrypy.html
    rest_cherrypy:
      host: localhost
      port: 8000
      ssl_crt: /etc/pki/tls/certs/localhost.crt
      ssl_key: /etc/pki/tls/certs/localhost.key
      thread_pool: 30
      socket_queue_size: 10

.. code-block:: yaml

    # file /srv/salt/salt_api.sls
    salt-api:
      pkg.installed:
        - unless:
          - salt-api --version
    #
    cherrypy:
      pip.installed:
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


Create your target machine as a Salt minion named "v1" by:

.. code-block:: bash

    $ sudo salt-call --local state.apply salt_api
    $ sudo salt-cloud -p prof1 v1
