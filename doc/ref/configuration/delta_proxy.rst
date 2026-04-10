.. _delta-proxy-information:

.. _delta-proxy-intro:

===================
Delta proxy minions
===================

Welcome to the delta proxy minion installation guide. This guide explains
the process for installing and using delta proxy minions, which are available
beginning in Salt version 3004.

This guide is intended for system and network administrators with general
knowledge and experience in the field. It is also intended for users who have
already tested and used standard Salt proxy minions in their environment before
moving to a delta proxy minion environment. For more information about standard
proxy minions, see `Salt proxy minions <https://docs.saltproject.io/en/latest/topics/proxyminion/index.html>`_.

.. Note::
    If you have not used standard Salt proxy minions before, consider testing
    and deploying standard Salt proxy minions in your environment first.


Proxy minions vs. delta proxy minions
=====================================
Salt can target network devices through `Salt proxy minions
<https://docs.saltproject.io/en/latest/topics/proxyminion/index.html>`_.
Proxy minions allow you to control network devices that, for whatever reason,
cannot run the standard Salt minion. Examples include:

* Network gear that has an API but runs a proprietary operating system
* Devices with limited CPU or memory
* Devices that could run a minion but will not for security reasons

A proxy minion acts as an intermediary between the Salt master and the
device it represents. The proxy minion process runs on a machine with network
access to the managed device and translates commands from the Salt master
to the device as needed.

By acting as an intermediary, proxy minions eliminate the need to establish
a constant connection from the Salt master to the managed device. Proxy
minions generally only open a connection to the managed device when necessary
to execute commands.

Proxy minions also reduce the computational load on managed devices.
The proxy minion handles communication with the Salt master, while the
managed device only needs to respond to commands when they are executed.

.. Note::
    For more information about Salt proxy minions, see:

    * `Salt proxy minions
      <https://docs.saltproject.io/en/latest/topics/proxyminion/index.html>`_

    * `Salt proxy modules
      <https://docs.saltproject.io/en/latest/ref/proxy/all/index.html#all-salt-proxy>`_


When delta proxy minions are needed
-----------------------------------
Normally, you would create a separate instance of a proxy minion for each device
that needs to be managed. However, this doesn't always scale well if you have
thousands of devices. Running several thousand proxy minions can require significant
amounts of memory and CPU resources.

A delta proxy minion can solve this scaling problem by allowing a single
proxy minion process to manage multiple network devices. In this scenario,
one delta proxy minion process acts as the intermediary between the Salt master
and many network devices. This configuration reduces resource usage and
improves the overall scalability of your network management infrastructure.


Key terms
=========
The following lists some important terminology that is used throughout this
guide:

.. list-table::
  :widths: 25 75
  :header-rows: 1

  * - Term
    - Definition

  * - Salt master
    - The Salt master is a central node running the Salt master server.
      The Salt master issues commands to minions.

  * - minion
    - Minions are nodes running the Salt minion service. Minions listen
      to commands from a Salt master and perform the requested tasks, then return
      data back to the Salt master as needed.

  * - proxy minion
    - A proxy process that acts as an intermediary between the Salt master and
      a network device it represents. The proxy minion runs on a machine with
      network access to the managed device and translates commands from the
      Salt master to the device. A separate proxy minion process is needed for
      each device that is managed.

  * - delta proxy minion
    - A single proxy process that can manage multiple network devices
      simultaneously. The delta proxy minion acts as the intermediary between
      the Salt master and many network devices. Only one instance of the delta
      proxy service is needed to manage multiple devices.

  * - control proxy
    - The control proxy component within a delta proxy minion that manages a
      list of devices and issues commands to the network devices it represents.
      You can have one or more control proxies, each managing a different set
      of devices.

  * - managed device
    - A network device (such as one managed through Netmiko) that is controlled
      by proxy minions or by a delta proxy minion. The proxy only creates
      a connection to the managed device when it needs to execute a command.

  * - pillar file
    - Pillars are structures of data (files) defined on the Salt master and passed
      through to one or more minions when the minion needs access to the
      pillar file. Pillars allow confidential, targeted data to be securely sent
      only to the relevant minion. Because all configurations for
      delta proxy minions are done on the Salt master (not on the minions), you
      use pillar files to configure the delta proxy-minion service.

  * - top file
    - The top file is a pillar file that maps which states should be applied to
      different minions in certain environments.

.. _delta-proxy-preinstall:

Pre-installation
================

Before you start
----------------
Before installing the delta proxy minion, ensure that:

* Your network devices and firmware are supported.
* The machine where you will run the delta proxy minion has network
  access to the devices it will be managing.
* You have installed, configured, and tested standard Salt proxy minions in
  your environment before introducing delta proxy minions.


Install or upgrade Salt
-----------------------
Ensure your Salt masters are running at least Salt version 3004. For instructions
on installing or upgrading Salt, see the
`Salt Install Guide <https://docs.saltproject.io/salt/install-guide/en/latest/>`_.

.. _delta-proxy-install:

Installation
============

Before you begin the delta proxy minion installation process, ensure you
have read and completed the :ref:`delta-proxy-preinstall` steps.


Overview of the installation process
------------------------------------
Similar to proxy minions, all the delta proxy minion configurations are done
on the Salt master rather than on the minions that will be managed. The
installation process has the following phases:

#. `Configure the master to use delta proxy`_ - Create a
   configuration file on the Salt master that defines its proxy settings.
#. `Create a pillar file for each managed device`_ - Create a
   pillar file for each device that will be managed by the delta proxy minion
   and reference these minions in the top file.
#. `Create a control proxy configuration file`_ - Create a control proxy file
   that lists the devices that it will manage. Then, reference this file in the
   top file.
#. `Start the delta proxy minion`_ - Start the delta proxy-minion service and
   validate that it has been set up correctly.


Configure the master to use delta proxy
---------------------------------------
In this step, you'll create a configuration file on the Salt master that defines
its proxy settings. This is a general configuration file that tells the Salt master
how to handle all proxy minions.

To create this configuration:

#. On the Salt master, navigate to the ``/etc/salt`` directory. In this directory,
   create a file named ``proxy`` if one doesn't already exist.

#. Open the file in your preferred editor and add the following configuration
   information:

   .. code-block:: yaml

       # Use delta proxy metaproxy (REQUIRED)
       metaproxy: deltaproxy

       # Disable the FQDNS grain (RECOMMENDED)
       enable_fqdns_grains: False

       # Enable multiprocessing (RECOMMENDED)
       multiprocessing: True

   .. Important::
       The ``metaproxy: deltaproxy`` configuration option is **required** for
       delta proxy minions to function correctly. Without this setting, Salt
       will use the standard proxy service instead of the delta proxy service.

   .. Note::
       See the following section about `delta proxy configuration options`_ for
       a more detailed description of these configuration options.

#. Save the file.

Your Salt master is now configured to use delta proxy. Next, you need to
`Create a pillar file for each managed device`_.


Delta proxy configuration options
---------------------------------
The following table describes the configuration options used in the delta
proxy configuration file:

.. list-table::
  :widths: 25 75
  :header-rows: 1

  * - Field
    - Description

  * - metaproxy
    - Set this configuration option to ``deltaproxy``. If this option is set to
      ``proxy`` or if this line is not included in the file, the Salt master will
      use the standard proxy service instead of the delta proxy service.

  * - enable_fqdns_grains
    - If your router does not have the ability to use Reverse DNS lookup to
      obtain the Fully Qualified Domain Name (fqdn) for an IP address, you'll
      need to change the ``enable_fqdns_grains`` setting in the pillar
      configuration file to ``False`` instead.

  * - multiprocessing
    - Multi-processing is the ability to run more than one task or process at
      the same time. A delta proxy minion has the ability to run with
      multi-processing turned off.

      If you plan to run with multi-processing enabled, you should also enable
      the ``skip_connect_on_init`` setting to ``True``.

  * - skip_connect_on_init
    - This setting tells the control proxy whether or not it should make a
      connection to the managed device when it starts. When set to ``True``, the
      delta proxy minion will only connect when it needs to issue commands to
      the managed devices.


Create a pillar file for each managed device
--------------------------------------------
Each device that needs to be managed by delta proxy needs a separate pillar
file on the Salt master. To create this file:

#. Navigate to the ``/srv/pillar`` directory.

#. In this directory create a new pillar file for a minion. For example,
   ``switch01.sls``.

#. Open the new file in your preferred editor and add the necessary
   configuration information for that minion and your environment. The
   following is an example pillar file for a dummy proxy device (useful for
   testing delta proxy functionality):

   .. code-block:: yaml

       proxy:
         proxytype: dummy
         host: 192.0.2.10
         username: admin
         password: secret123

   For production environments with real network devices, you might use
   a Netmiko device instead:

   .. code-block:: yaml

       proxy:
         proxytype: netmiko
         device_type: arista_eos
         host: 192.0.2.10
         username: myusername
         password: mypassword
         always_alive: True

   .. Note::
      The dummy proxy type is excellent for testing and learning about delta
      proxy functionality without requiring actual network hardware. For
      production deployments, use the appropriate proxy type for your devices.

   .. Note::
      The available configuration options vary depending on the proxy type (in
      other words, the type of device it is). To read a detailed explanation of
      the configuration options, refer to the proxy module documentation for
      the type of device you need to manage. See:

      * `Salt proxy modules
        <https://docs.saltproject.io/en/latest/ref/proxy/all/index.html#all-salt-proxy>`_
      * `Dummy Salt proxy module
        <https://docs.saltproject.io/en/latest/ref/proxy/all/salt.proxy.dummy.html#module-salt.proxy.dummy>`_
      * `Netmiko Salt proxy module
        <https://docs.saltproject.io/en/latest/ref/proxy/all/salt.proxy.netmiko_px.html#module-salt.proxy.netmiko_px>`_

#. Save the file.

#. In an editor, open the top file: ``/srv/pillar/top.sls``.

#. Add a section to the top file that indicates the minion ID of the device
   that will be managed. Then, list the name of the pillar file you created in
   the previous steps. For example:

   .. code-block:: yaml

       switch01:
         - switch01

#. Repeat the previous steps for each minion that needs to be managed.
   For example, create ``switch02.sls`` and ``switch03.sls`` with similar
   configuration but different IP addresses:

   ``switch02.sls``:

   .. code-block:: yaml

       proxy:
         proxytype: dummy
         host: 192.0.2.11
         username: admin
         password: secret123

   ``switch03.sls``:

   .. code-block:: yaml

       proxy:
         proxytype: dummy
         host: 192.0.2.12
         username: admin
         password: secret123

You've now created the pillar files for all the minions that will be managed by the
delta proxy minion and you have referenced these files in the top file.
Proceed to the next section.


Create a control proxy configuration file
-----------------------------------------
On the Salt master, you'll need to create or edit a control proxy file for each
control proxy. The control proxy manages several devices and issues commands to
the network devices it represents. The Salt master needs at least one control
proxy, but it is possible to have more than one control proxy, each managing a
different set of devices.

To configure a control proxy, you'll create a file that lists the minion IDs
of the minions that it will manage. Then you will reference this control proxy
configuration file in the top file.

To create a control proxy configuration file:

#. On the Salt master, navigate to the ``/srv/pillar`` directory. In this
   directory, create a new proxy configuration file. Give this file a
   descriptive name, such as ``deltaproxy_control.sls``.

#. Open the file in your preferred editor and add a list of the minion IDs for
   each device that needs to be managed. For example:

   .. code-block:: yaml

       proxy:
         proxytype: deltaproxy
         ids:
           - switch01
           - switch02
           - switch03

#. Save the file.

#. In an editor, open the top file: ``/srv/pillar/top.sls``.

#. Add a section to the top file that references the delta proxy
   control proxy. For example:

   .. code-block:: yaml

       base:
         switch01:
           - switch01
         switch02:
           - switch02
         switch03:
           - switch03
         deltaproxy_control:
           - deltaproxy_control

#. Repeat the previous steps for each control proxy if needed.

.. Note::
    The ``metaproxy`` setting was already configured in the ``/etc/salt/proxy``
    file during the `Configure the master to use delta proxy`_ step, so no
    additional configuration is needed.

Now that you have created the necessary configurations, proceed to the next
section.


Start the delta proxy minion
----------------------------
After you've successfully configured the delta proxy minion, you need to
start the proxy minion service for each managed device and validate that it is
working correctly.

.. Note::
    This step explains the process for starting a single instance of a
    delta proxy minion. Because starting each minion individually can
    potentially be very time-consuming, most organizations use a script to start
    their delta proxy minions since there are typically many devices being
    managed. Consider implementing a similar script for your environment to save
    time in deployment.

To start a single instance of a delta proxy minion and test that it is
configured correctly:

#. In the terminal for the Salt master, run the following command:

   .. code-block:: bash

       sudo salt-proxy --proxyid=deltaproxy_control


#. To test the delta proxy minion, run the following commands to verify that
   each managed device is accessible through the delta proxy:

   Test connectivity to a single device:

   .. code-block:: bash

       salt switch01 test.ping

   This command returns:

   .. code-block:: bash

       switch01:
           True

   Test all managed devices at once:

   .. code-block:: bash

       salt 'switch*' test.ping

   This command returns:

   .. code-block:: bash

       switch01:
           True
       switch02:
           True
       switch03:
           True

   Check the Salt version on all devices:

   .. code-block:: bash

       salt 'switch*' test.version

   Verify that each device has its own configuration:

   .. code-block:: bash

       salt 'switch*' pillar.get proxy:host

   This command shows that each device has its own unique IP address:

   .. code-block:: bash

       switch01:
           192.0.2.10
       switch02:
           192.0.2.11
       switch03:
           192.0.2.12

   Test the control proxy directly:

   .. code-block:: bash

       salt deltaproxy_control test.ping
       salt deltaproxy_control pillar.get proxy:ids

After you've successfully started the delta proxy minions and verified that
they are working correctly, you can now use these minions the same as standard
proxy minions. The delta proxy system allows you to manage multiple devices
through a single proxy process, making it ideal for large-scale deployments.

.. _delta-proxy-additional-resources:

Additional resources
====================

This reference section includes additional resources for delta proxy minions.

For reference, see:

* `Salt proxy minions
  <https://docs.saltproject.io/en/latest/topics/proxyminion/index.html>`_

* `Salt proxy modules
  <https://docs.saltproject.io/en/latest/ref/proxy/all/index.html#all-salt-proxy>`_

* `Netmiko Salt proxy module
  <https://docs.saltproject.io/en/latest/ref/proxy/all/salt.proxy.netmiko_px.html#module-salt.proxy.netmiko_px>`_
