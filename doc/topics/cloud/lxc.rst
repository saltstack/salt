.. _config_lxc:

========================
Getting Started With LXC
========================

The LXC module is designed to install Salt in an LXC container on a controlled
and possibly remote minion.

In other words, Salt will connect to a minion, then from that minion:

- Provision and configure a container for networking access
- Use those modules to deploy salt and re-attach to master.

    - :mod:`lxc runner <salt.runners.lxc>`
    - :mod:`lxc module <salt.modules.lxc>`
    - :mod:`seed <salt.modules.config>`

Limitations
-----------

- You can only act on one minion and one provider at a time.
- Listing images must be targeted to a particular LXC provider (nothing will be
  outputted with ``all``)

Operation
---------

Salt's LXC support does use :mod:`lxc.init <salt.modules.lxc.init>`
via the :mod:`lxc.cloud_init_interface <salt.modules.lxc.cloud_init_interface>`
and seeds the minion via :mod:`seed.mkconfig <salt.modules.seed.mkconfig>`.

You can provide to those lxc VMs a profile and a network profile like if
you were directly using the minion module.

Order of operation:

- Create the LXC container on the desired minion (clone or template)
- Change LXC config options (if any need to be changed)
- Start container
- Change base passwords if any
- Change base DNS configuration if necessary
- Wait for LXC container to be up and ready for ssh
- Test SSH connection and bailout in error
- Upload deploy script and seeds, then re-attach the minion.


Provider configuration
----------------------

Here is a simple provider configuration:

.. code-block:: yaml

    # Note: This example goes in /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.
    devhost10-lxc:
      target: devhost10
      driver: lxc

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Profile configuration
---------------------

Please read :ref:`tutorial-lxc` before anything else.
And specially :ref:`tutorial-lxc-profiles`.

Here are the options to configure your containers:


    target
        Host minion id to install the lxc Container into
    lxc_profile
        Name of the profile or inline options for the LXC vm creation/cloning,
        please see :ref:`tutorial-lxc-profiles-container`.
    network_profile
        Name of the profile or inline options for the LXC vm network settings,
        please see :ref:`tutorial-lxc-profiles-network`.
    nic_opts
        Totally optional.
        Per interface new-style configuration options mappings which will
        override any profile default option::

              eth0: {'mac': '00:16:3e:01:29:40',
                            'gateway': None, (default)
                            'link': 'br0', (default)
                            'gateway': None, (default)
                            'netmask': '', (default)
                            'ip': '22.1.4.25'}}

    password
        password for root and sysadmin users
    dnsservers
        List of DNS servers to use. This is optional.
    minion
        minion configuration (see :ref:`Minion Configuration in Salt Cloud <salt-cloud-config>`)
    bootstrap_delay
        specify the time to wait (in seconds) between container creation
        and salt bootstrap execution. It is useful to ensure that all essential services
        have started before the bootstrap script is executed. By default there's no
        wait time between container creation and bootstrap unless you are on systemd
        where we wait that the system is no more in starting state.
    bootstrap_shell
        shell for bootstraping script (default: /bin/sh)
    script
        defaults to salt-boostrap
    script_args
        arguments which are given to the bootstrap script.
        the {0} placeholder will be replaced by the path which contains the
        minion config and key files, eg::

            script_args="-c {0}"


Using profiles:

.. code-block:: yaml

    # Note: This example would go in /etc/salt/cloud.profiles or any file in the
    # /etc/salt/cloud.profiles.d/ directory.
    devhost10-lxc:
      provider: devhost10-lxc
      lxc_profile: foo
      network_profile: bar
      minion:
        master: 10.5.0.1
        master_port: 4506

Using inline profiles (eg to override the network bridge):

.. code-block:: yaml

    devhost11-lxc:
      provider: devhost10-lxc
      lxc_profile:
        clone_from: foo
      network_profile:
        etho:
          link: lxcbr0
      minion:
        master: 10.5.0.1
        master_port: 4506

Using a lxc template instead of a clone:

.. code-block:: yaml

    devhost11-lxc:
      provider: devhost10-lxc
      lxc_profile:
        template: ubuntu
        # options:
        #   release: trusty
      network_profile:
        etho:
          link: lxcbr0
      minion:
        master: 10.5.0.1
        master_port: 4506

Static ip:

.. code-block:: yaml

    # Note: This example would go in /etc/salt/cloud.profiles or any file in the
    # /etc/salt/cloud.profiles.d/ directory.
    devhost10-lxc:
      provider: devhost10-lxc
      nic_opts:
        eth0:
          ipv4: 10.0.3.9
      minion:
        master: 10.5.0.1
        master_port: 4506

DHCP:

.. code-block:: yaml

    # Note: This example would go in /etc/salt/cloud.profiles or any file in the
    # /etc/salt/cloud.profiles.d/ directory.
    devhost10-lxc:
      provider: devhost10-lxc
      minion:
        master: 10.5.0.1
        master_port: 4506

Driver Support
--------------

- Container creation
- Image listing (LXC templates)
- Running container information (IP addresses, etc.)

