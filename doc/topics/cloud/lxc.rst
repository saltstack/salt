.. _config_lxc:

========================
Getting Started With LXC
========================

The LXC module is designed to install Salt in an LXC container on a controlled
and possibly remote minion.

In other words, Salt will connect to a minion, then from that minion:

- Provision and configure a container for networking access
- Use saltify to deploy salt and re-attach to master

Limitation
------------
- You can only act on one minion and one provider at a time.
- Listing images must be targeted to a particular driver (nothing will be
  outputted with ``all``)

Operation
---------
This does not use lxc.init to provide a more generic fashion to tie minions
to their master (if any and defined) to allow custom association code.

Order of operation:

- Spin up the LXC template container using :mod:`the LXC execution module
  <salt.modules.lxc>` on the desired minion (clone or template)
- Change LXC config option (if any need to be changed)
- Start container
- Change base passwords if any
- Change base DNS base configuration if neccessary
- Wait for LXC container to be up and ready for ssh
- Test SSH connection and bailout in error
- Via SSH (with the help of saltify, upload deploy script and seeds and
  re-attach minion.


Provider configuration
----------------------

Here is a simple configuration example:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.
    devhost10-lxc:
      target: devhost10
      provider: lxc

Profile configuration
---------------------

Here are the options to configure your containers::

    target
        Host minion id to install the lxc Container into
    profile
        lxc pillar profile
    Container creation/clone options
        Use a container using clone
            from_container
                Name of an original container using clone
            snapshot
                Do we use snapshots on cloned filesystems
        lxc template using total creation
            image
                template to use
            backing
                Backing store type (None, lvm, brtfs)
            lvname
                LVM lvname if any
            fstype
                fstype
    size
        Size of the containera (for brtfs, or lvm)
    vgname
        LVM vgname if any
    users
        sysadmin users [ubuntu] of the container
    ssh_username
        sysadmin ssh_username (ubuntu) of the container
    sudo
        Do we use sudo
    ssh_gateway
        if the minion is not in your 'topmaster' networ, use
        that gateway to connect to the lxc container.
        This may be the public ip of the hosting minion
    ssh_gateway_key
        When using gateway, additionnal parameters as in saltify
    ssh_gateway_port
        When using gateway, additionnal parameters as in saltify
    ssh_gateway_user
        When using gateway, additionnal parameters as in saltify
    password
        password for root and sysadmin (ubuntu)
    mac
        mac address to associate
    ip
        ip to link to
    netmask
        netmask for ip
    bridge
        bridge to use
    dnsservers
        optionnal list of dns servers to use
        Will be restricted to that list if used
    lxc_conf_unset
        Configuration variables to unset in lxc conf
    lxc_conf
        LXC configuration variables to set in lxc_conf
    minion
        minion configuration (as usual with salt cloud)


.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.profile or any file in the
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
