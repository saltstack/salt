============================================================
Cisco NX-OS Salt Minion Installation and Configuration Guide
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
  * SSH Proxy Minion
  * NX-API Proxy Minon
  * GuestShell Native Minion
      * Some platforms support a native minon installed directly on the NX-OS device
      * This is a secure Linux container environment running CentOS

**STEP 3: Network Connectivity**

When Using Proxy Minion:

* Ensure that IP reachability exists between the Proxy Minion Device and the SaltStack Master.
   * (NOTE) Not needed if Proxy Minions are started on the SaltStack Master.

When Using GuestShell Minion:

* Ensure that IP reachability exists between the NX-OS Salt Minon device and the SaltStack Master. Note that connectivity via the management interface is in a separate VRF context which requires some additional configuration.

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

Salt Proxy Minion Installation
==============================

SSH Proxy Minion
----------------

NX-API Proxy Minion
-------------------

GuestShell Salt Minion Installation
===================================

GuestShell Salt Minion Persistence
===================================
