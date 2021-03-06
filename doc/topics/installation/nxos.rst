============================================================
Cisco Nexus Salt Minion Installation and Configuration Guide
============================================================

This document describes the Salt Minion installation and configuration on Cisco Nexus switches.  These instructions detail the process for managing the Nexus switches using a Proxy Minion or Native Minion on platforms that have GuestShell support.

.. contents:: Table of Contents

Pre-Install Tasks
=================

STEP 1: Verify Platform and Software Version Support
----------------------------------------------------

The following platforms and software versions have been certified to work with this version of Salt.

  .. table:: Platform / Software Minimum Requirements
     :widths: auto
     :align: center

     ===================  =====================  ================  ===================  =================
     Supported Platforms  Minimum NX-OS Version  SSH Proxy Minion  NX-API Proxy Minion  GuestShell Minion
     ===================  =====================  ================  ===================  =================
     Cisco Nexus N3k      7.0(3)I2(5) and later  Supported         Supported            Supported
     Cisco Nexus N9k      7.0(3)I2(5) and later  Supported         Supported            Supported
     Cisco Nexus N6k      7.3(0)N1(1) and later  Supported         Not Supported        Not Supported
     Cisco Nexus N7k      7.3(0)D1(1) and later  Supported         Supported            Not Supported
     ===================  =====================  ================  ===================  =================

  .. table:: Platform Models
     :widths: auto
     :align: center

     ========  ===========
     Platform  Description
     ========  ===========
     N3k       Support includes N30xx, N31xx, N32xx and N35xx models
     N6k       Support includes all N6xxx models
     N7k       Support includes all N7xxx models
     N9k       Support includes all N9xxx models
     ========  ===========

STEP 2: Choose Salt Minion Type
-------------------------------

Using the tables above, select the Salt Minion type.

Choices:
  * ``SSH`` Proxy Minion (See `Salt Proxy Minion Configuration`_ Section)
  * ``NX-API`` Proxy Minion (See `Salt Proxy Minion Configuration`_ Section)
  * ``GuestShell`` Native Minion (See `GuestShell Salt Minion Installation`_ Section)
      * Some platforms support a native minion installed directly on the NX-OS device inside the GuestShell
      * The GuestShell is a secure Linux container environment running CentOS

STEP 3: Network Connectivity
----------------------------

Ensure that IP reachability exists between the NX-OS Salt Minion device and the SaltStack Master.

**Note:** The management interface exists in a separate VRF context and requires additional configuration as shown.

Example: Nexus CLI Configuration for connectivity via management interface

.. code:: bash

  config term
    vrf context management
      ip name-server 10.0.0.202
      ip domain-name mycompany.com
      ip route 0.0.0.0/0 10.0.0.1

    interface mgmt0
      vrf member management
      ip address 10.0.0.99/24

    ntp server 10.0.0.201 use-vrf management
  end

Salt Proxy Minion Configuration
===============================

Here is a sample Proxy Minion directory structure

.. code:: bash

  saltmaster:/srv/pillar$tree
  .
  ├── n3k-proxy.sls
  ├── n7k-proxy.sls
  └── top.sls

This displays a top sls file and two proxy minion sls files for a Nexus 3k and Nexus 7k device.

Sample contents for the ``top.sls`` file.

.. code:: yaml

  saltmaster:/srv/pillar$cat top.sls
  base:
    n3k-proxy:
      - n3k-proxy
    n7k-proxy:
      - n7k-proxy

Proxy Minion Pillar Data
------------------------

Here is a sample Proxy Minion pillar data file.

All of the data for both ssh and nxapi proxy minion types can be stored in the same pillar data file.  To choose ``ssh`` or ``nxapi``, simply set the ``connection:`` parameter accordingly.

.. code:: yaml

  saltmaster:/srv/pillar$cat n7k-proxy.sls
  proxy:
    proxytype: nxos

    # Specify ssh or nxapi connection type (default is ssh)
    #connection: ssh
    connection: nxapi

    # Parameters Common to both SSH and NX-API
    host: n7k.example.com
    username: admin
    password: password

    # SSH Parameters
    prompt_name: n7k
    ssh_args: '-o PubkeyAuthentication=no'
    key_accept: True

    # NX-API Parameters
    transport: https
    port: 443
    verify: False

    # Option to prevent auto-save after each configuration command.
    # Setting this to True will improve performance when using
    # nxos execution module functions to configure the device.
    no_save_config: True


* For the most current nxos proxy minion configuration options, See :mod:`salt.proxy.nxos <salt.proxy.nxos>`
* For the most current list of nxos execution module functions, See :mod:`salt.modules.nxos<salt.modules.nxos>`



GuestShell Salt Minion Installation
===================================

This section is only required when running the SaltStack Minion from the ``guestshell``.

STEP 1a: Enable the Guestshell on low footprint N3ks
----------------------------------------------------

**NOTE:** Skip down to **STEP 1b** if the target system is not a low footprint N3k.

Nexus 3xxx switches with 4 GB RAM and 1.6 GB bootflash are advised to use compacted images to reduce the storage resources consumed by the image. As part of the compaction process, the ``guestshell.ova`` is removed from the system image.  To make use of the guestshell on these systems, the guestshell.ova may be downloaded and used to install the guestshell.

Guestshell OVA Download Link_

.. _Link: https://software.cisco.com/download/home/283970187/type/282088129/release/9.2%25281%2529?catid=268438038

Starting in release ``9.2(1)`` and onward, the .ova file can be copied to the ``volatile:`` directory which frees up more space on ``bootflash:``.

Copy the ``guestshell.ova`` file to ``volatile:`` if supported, otherwise copy it to ``bootflash:``

.. code-block:: console

  n3xxx# copy scp://admin@1.2.3.4/guestshell.ova volatile: vrf management
  guestshell.ova 100% 55MB 10.9MB/s 00:05
  Copy complete, now saving to disk (please wait)...
  Copy complete.

Use the ``guestshell enable`` command to install and enable guestshell.

.. code-block:: console

  n3xxx# guestshell enable package volatile:guestshell.ova


STEP 1b: Enable the Guestshell
------------------------------

The ``guestshell`` container environment is enabled by default on most platforms; however, the default disk and memory resources allotted to guestshell are typically too small to support SaltStack Minion requirements. The resource limits may be increased with the NX-OS CLI ``guestshell resize`` commands as shown below.

  .. table:: Resource Requirements
     :widths: auto
     :align: center

     ===================  =====================
     Resource             Recommended
     ===================  =====================
     Disk                 **500 MB**
     Memory               **350 MB**
     ===================  =====================


``show guestshell detail`` displays the current resource limits:

.. code:: bash

  n3k# show guestshell detail
  Virtual service guestshell+ detail
    State                 : Activated
  ...
    Resource reservation
    Disk                : 150 MB
    Memory              : 128 MB

``guestshell resize rootfs`` sets disk size limits while ``guestshell resize memory`` sets memory limits. The resize commands do not take effect until after the guestshell container is (re)started by ``guestshell reboot`` or ``guestshell enable``.


**Example.** Allocate resources for guestshell by setting new limits to 500MB disk and 350MB memory.

.. code:: console

  n3k# guestshell resize rootfs 500
  n3k# guestshell resize memory 350

  n3k# guestshell reboot
  Are you sure you want to reboot the guest shell? (y/n) [n] y

STEP 2: Set Up Guestshell Network
---------------------------------

The ``guestshell`` is an independent CentOS container that does not inherit settings from NX-OS.

* Use ``guestshell`` to enter the guestshell environment, then become root.
* *Optional:* Use ``chvrf`` to specify a vrf namespace; e.g. ``sudo chvrf management``

.. code:: bash

  n3k#  guestshell

  [guestshell@guestshell ~]$ sudo su -          # Optional: sudo chvrf management
  [root@guestshell guestshell]#

**OPTIONAL: Add DNS Configuration**

.. code:: console

  [root@guestshell guestshell]#  cat >> /etc/resolv.conf << EOF
  nameserver 10.0.0.202
  domain mycompany.com
  EOF


**OPTIONAL: Define proxy server variables if needed to allow network access to SaltStack package repositories**

.. code:: console

  export http_proxy=http://proxy.yourdomain.com:<port>
  export https_proxy=https://proxy.yourdomain.com:<port>


STEP 3: Install SaltStack Minion
---------------------------------

**OPTIONAL: Upgrade the pip installer**

  ``[root@guestshell guestshell]# pip install --upgrade pip``


Install the ``certifi`` python package.

  ``[root@guestshell guestshell]# pip install certifi``

The most current information on installing the SaltStack Minion in a Centos7 environment can be found here_

.. _here: https://repo.saltstack.com/#rhel

Information from the install guide is provided here for convenience.

Run the following commands to install the SaltStack repository and key:

  ``[root@guestshell guestshell]# yum install https://repo.saltstack.com/yum/redhat/salt-repo-latest-2.el7.noarch.rpm``

Run the following command to force yum to revalidate the cache for each repository.

  ``[root@guestshell guestshell]# yum clean expire-cache``

Install the Salt Minion.

  ``[root@guestshell guestshell]# yum install salt-minion``

STEP 4: Configure SaltStack Minion
----------------------------------

Make the following changes to the ``/etc/salt/minion`` configuration file in the NX-OS GuestShell.

Change the ``master:`` directive to point to the SaltStack Master.

.. code:: diff

  - #master: salt
  + master: saltmaster.example.com

Change the ``id:`` directive to easily identify the minion running in the GuestShell.

Example:

.. code:: diff

  - #id: salt
  + id: n3k-guestshell-minion

Start the Minion in the Guestshell and accept the key on the SaltStack Master.

  ``[root@guestshell ~]# systemctl start salt-minion``

.. code:: bash

  saltmaster: salt-key -L
  Accepted Keys:
  Denied Keys:
  Unaccepted Keys:
  n3k-guestshell-minion
  Rejected Keys:

.. code:: bash

  saltmaster: salt-key -A
  The following keys are going to be accepted:
  Unaccepted Keys:
  n3k-guestshell-minion
  Proceed? [n/Y] Y
  Key for minion n3k-guestshell-minion accepted.

Ping the SaltStack Minion running in the Guestshell.

.. code:: bash

  saltmaster: salt n3k-guestshell-minion nxos.ping
  n3k-guestshell-minion:
    True


GuestShell Salt Minion Persistence
===================================

This section documents SaltStack Minion persistence in the ``guestshell`` after system restarts and high availability switchovers.

The ``guestshell`` container does not automatically sync filesystem changes from the active processor to the standby processor. This means that SaltStack Minion installation files and related file changes will not be present on the standby until they are manually synced with the following NX-OS exec command:

``guestshell sync``

The ``guestshell`` environment uses **systemd** for service management. The SaltStack Minion provides a generic systemd script when installed, but a slight modification as shown below is needed for nodes that run Salt in the management (or other vrf) namespace:

.. code:: diff

  --- /usr/lib/systemd/system/salt-minion.service.old
  +++ /usr/lib/systemd/system/salt-minion.service
  [Unit]
  Description=The Salt Minion
  Documentation=man:salt-minion(1) file:///usr/share/doc/salt/html/contents.html
  https://docs.saltstack.com/en/latest/contents.html
  After=network.target salt-master.service

  [Service]
  KillMode=process
  Type=notify
  NotifyAccess=all
  LimitNOFILE=8192

  - ExecStart=/usr/bin/salt-minion
  + ExecStart=/bin/nsenter --net=/var/run/netns/management -- /usr/bin/salt-minion

  [Install]
  WantedBy=multi-user.target


Change the ``pidfile:`` directive to point to the ``/run`` ``tmpfs`` location in the GuestShell.

.. code:: diff

  - #pidfile: /var/run/salt-minion.pid
  + pidfile: /run/salt-minion.pid

Next, enable the SaltStack Minion systemd service (the ``enable`` command adds it to systemd for autostarting on the next boot) and optionally start it now:

.. code:: diff

  systemctl enable salt-minion
  systemctl start salt-minion


References
==========

  .. table:: Nexus Document References
     :widths: auto
     :align: center

     ===================  =====================
     References           Description
     ===================  =====================
     GuestShell_N9k_      N9k Guestshell Programmability Guide
     GuestShell_N3k_      N3k Guestshell Programmability Guide
     ===================  =====================

.. _Guestshell_N9k: https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/9-x/programmability/guide/b_Cisco_Nexus_9000_Series_NX-OS_Programmability_Guide_9x/b_Cisco_Nexus_9000_Series_NX-OS_Programmability_Guide_9x_chapter_0100.html

.. _GuestShell_N3k: https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/programmability/9_x/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide_9x/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide_9x_chapter_0101.html

