============================================================
Cisco Nexus Salt Minion Installation and Configuration Guide
============================================================

This document describes the Salt Minion installation and configuration on Cisco Nexus switches.  These instructions detail the process for managing the Nexus switches using a Proxy Minion or Native Minion on platforms that have GuestShell support.

.. contents:: Table of Contents

Pre-Install Tasks
=================

**STEP 1: Verify Platform and Software Version Support**

The following platforms and software versions have been certified to work with this version of Salt.

  .. table:: Platform / Software Mininum Requirements
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
     N3k       Support includes N30xx, N31xx and N35xx models
     N6k       Support includes all N6xxx models
     N7k       Support includes all N7xxx models
     N9k       Support includes all N9xxx models
     ========  ===========

**STEP 2: Choose Salt Minion Type**

Using the tables above, select the Salt Minion type.

Choices:
  * ``SSH`` Proxy Minion
  * ``NX-API`` Proxy Minon
  * ``GuestShell`` Native Minion
      * Some platforms support a native minon installed directly on the NX-OS device inside the GuestShell
      * The GuestShell is a secure Linux container environment running CentOS

**STEP 3: Network Connectivity**

Ensure that IP reachability exists between the NX-OS Salt Minon device and the SaltStack Master. Note that connectivity via the management interface is in a separate VRF context which requires some additional configuration.

Note: The management interface exists in a separate VRF context and requires additional configuration as shown.

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

This displays a top sls file and two proxy minon sls files for a Nexus 3k and Nexus 7k device.

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

Here is a sample Proxy Minon pillar data file.

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

GuestShell Salt Minion Persistence
===================================
