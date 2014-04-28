.. _config_lxc:

========================
Getting Started With LXC
========================

The LXC module is designed to install Salt in an LXC container on a controlled
and possibly remote minion.

In other words, Salt will connect to a minion, then from that minion:

- Provision and configure a container for networking access
- Use :ref:`saltify <config_saltify>` to deploy salt and re-attach to master

Limitations
------------
- You can only act on one minion and one provider at a time.
- Listing images must be targeted to a particular LXC provider (nothing will be
  outputted with ``all``)

Operation
---------
Salt's LXC support does not use lxc.init.  This enables it to tie minions
to a master in a more generic fashion (if any masters are defined)
and allows other custom association code.

Order of operation:

- Create the LXC container using :mod:`the LXC execution module
  <salt.modules.lxc>` on the desired minion (clone or template)
- Change LXC config options (if any need to be changed)
- Start container
- Change base passwords if any
- Change base DNS configuration if necessary
- Wait for LXC container to be up and ready for ssh
- Test SSH connection and bailout in error
- Via SSH (with the help of saltify), upload deploy script and seeds,
  then re-attach the minion.


Provider configuration
----------------------

Here is a simple provider configuration:

.. code-block:: yaml

    # Note: This example goes in /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.
    devhost10-lxc:
      target: devhost10
      provider: lxc

Profile configuration
---------------------

Here are the options to configure your containers::

    ``target``
        Host minion id to install the lxc Container into
    ``profile``
        Name of the profile containing the LXC configuration

    Container creation/clone options:
        Create a container by cloning:
            ``from_container``
                Name of an original container using clone
            ``snapshot``
                Do we use snapshots on cloned filesystems
        Create a container from scratch using an LXC template:
            image
                template to use
            backing
                Backing store type (None, lvm, brtfs)
            lvname
                LVM logical volume name, if any
            fstype
                Type of filesystem
    size
        Size of the containera (for brtfs, or lvm)
    vgname
        LVM Volume Group name, if any
    users
        Names of the users to be pre-created inside the container
    ssh_username
        Username of the SSH systems administrator inside the container
    sudo
        Do we use sudo
    ssh_gateway
        if the minion is not in your 'topmaster' network, use
        that gateway to connect to the lxc container.
        This may be the public ip of the hosting minion
    ssh_gateway_key
        When using gateway, the ssh key of the gateway user (passed to saltify)
    ssh_gateway_port
        When using gateway, the ssh port of the gateway (passed to saltify)
    ssh_gateway_user
        When using gateway, user to login as via SSH (passed to saltify)
    password
        password for root and sysadmin (see "users" parameter above)
    mac
        mac address to assign to the container's network interface
    ip
        IP address to assign to the container's network interface
    netmask
        netmask for the network interface's IP
    bridge
        bridge under which the container's network interface will be enslaved
    dnsservers
        List of DNS servers to use--this is optional.  If present, DNS
        servers will be restricted to that list if used
    lxc_conf_unset
        Configuration variables to unset in this container's LXC configuration
    lxc_conf
        LXC configuration variables to add in this container's LXC configuration
    minion
        minion configuration (see :doc:`Minion Configuration in Salt Cloud </topics/cloud/config>`)


.. code-block:: yaml

    # Note: This example would go in /etc/salt/cloud.profile or any file in the
    # /etc/salt/cloud.profile.d/ directory.
    devhost10-lxc:
      provider: devhost10-lxc
      from_container: ubuntu
      backing: lvm
      sudo: True
      size: 3g
      ip: 10.0.3.9
      minion:
        master: 10.5.0.1
        master_port: 4506
      lxc_conf:
        - lxc.utsname: superlxc

Driver Support
--------------

- Container creation
- Image listing (LXC templates)
- Running container informations (IP addresses, etc.)
