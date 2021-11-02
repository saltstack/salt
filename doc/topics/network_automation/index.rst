.. meta::
   :description: Network automation is a continuous process of automating the configuration, management and operations of a computer network. Most network devices can be managed via Salt Proxy Minions using Salt SSH. However, some vendors allow for a Salt Minion to be installed directly.
   :keywords: network configuration automation, netops, juniper, configuration management, cisco, junos, napalm

.. _network-automation:

==================
Network Automation
==================

Network automation is a continuous process of automating the configuration,
management and operations of a computer network. Although the abstraction
could be compared with the operations on the server side, there are many particular
challenges, the most important being that a network device is traditionally
closed hardware able to run proprietary software only. In other words,
the user is not able to install the salt-minion package directly on a
traditional network device. For these reasons, most network devices can be
controlled only remotely via :ref:`proxy minions <proxy-minion>` or
using the :ref:`Salt SSH <salt-ssh>`. However, there are also vendors producing
whitebox equipment (e.g. Arista, Cumulus) or others that have moved the
operating system in the container (e.g. Cisco NX-OS, Cisco IOS-XR),
allowing the salt-minion to be installed directly on the platform.

New in Carbon (2016.11)
-----------------------

The methodologies for network automation have been introduced in
:ref:`2016.11.0 <release-2016-11-0-network-automation-napalm>`. Network
automation support is based on proxy minions.

- :mod:`NAPALM proxy <salt.proxy.napalm>`
- :mod:`Junos proxy<salt.proxy.junos>`
- :mod:`Cisco NXOS <salt.proxy.nxos>`
- :mod:`Cisco NSO <salt.proxy.cisconso>`

NAPALM
------

NAPALM (Network Automation and Programmability Abstraction Layer with
Multivendor support) is an opensourced Python library that implements a set of
functions to interact with different router vendor devices using a unified API.
Being vendor-agnostic simplifies operations, as the configuration and
interaction with the network device does not rely on a particular vendor.

.. image:: /_static/napalm_logo.png

Beginning with 2017.7.0, the NAPALM modules have been transformed so they can
run in both proxy and regular minions. That means, if the operating system
allows, the salt-minion package can be installed directly on the network gear.
The interface between the network operating system and Salt in that case would
be the corresponding NAPALM sub-package.

For example, if the user installs the
salt-minion on a Arista switch, the only requirement is
`napalm-eos <https://github.com/napalm-automation/napalm-eos>`_.

The following modules are available in 2017.7.0:

- :mod:`NAPALM grains <salt.grains.napalm>`
- :mod:`NET execution module <salt.modules.napalm_network>` - Networking basic
  features
- :mod:`NTP execution module <salt.modules.napalm_ntp>`
- :mod:`BGP execution module <salt.modules.napalm_bgp>`
- :mod:`Routes execution module <salt.modules.napalm_route>`
- :mod:`SNMP execution module <salt.modules.napalm_snmp>`
- :mod:`Users execution module <salt.modules.napalm_users>`
- :mod:`Probes execution module <salt.modules.napalm_probes>`
- :mod:`NTP peers management state <salt.states.netntp>`
- :mod:`SNMP configuration management state <salt.states.netsnmp>`
- :mod:`Users management state <salt.states.netusers>`
- :mod:`Netconfig state module <salt.states.netconfig>` - Manage the configuration
  of network devices using arbitrary templates and the Salt-specific
  advanced templating methodologies.
- :mod:`Network ACL execution module <salt.modules.napalm_acl>` - Generate and
  load ACL (firewall) configuration on network devices.
- :mod:`Network ACL state <salt.states.netacl>` - Manage the firewall
  configuration. It only requires writing the pillar structure correctly!
- :mod:`NAPALM YANG execution module <salt.modules.napalm_yang_mod>` - Parse,
  generate and load native device configuration in a standard way,
  using the OpenConfig/IETF models. This module contains also helpers for
  the states.
- :mod:`NAPALM YANG state module <salt.states.netyang>` - Manage the
  network device configuration according to the YANG models (OpenConfig or IETF).
- :mod:`NET finder <salt.runners.net>` - Runner to find details easily and
  fast. It's smart enough to know what you are looking for. It will search
  in the details of the network interfaces, IP addresses, MAC address tables,
  ARP tables and LLDP neighbors.
- :mod:`BGP finder <salt.runners.bgp>` - Runner to search BGP neighbors details.
- :mod:`NAPALM syslog <salt.engines.napalm_syslog>` - Engine to import events
  from the napalm-logs library into the Salt event bus. The events are based
  on the syslog messages from the network devices and structured following
  the OpenConfig/IETF YANG models.
- :mod:`NAPALM Helpers <salt.modules.napalm>` - Generic helpers for
  NAPALM-related operations. For example, the
  :mod:`Compliance report <salt.modules.napalm.compliance_report>` function
  can be used inside the state modules to compare the expected and the
  existing configuration.

Getting started
###############

Install NAPALM - follow the notes_ and check the platform-specific dependencies_.

.. _notes: https://napalm.readthedocs.io/en/latest/installation/index.html
.. _dependencies: https://napalm.readthedocs.io/en/latest/installation/index.html#dependencies

Salt's Pillar system is ideally suited for configuring proxy-minions
(though they can be configured in /etc/salt/proxy as well).  Proxies
can either be designated via a pillar file in :conf_master:`pillar_roots`,
or through an external pillar.
External pillars afford the opportunity for interfacing with
a configuration management system, database, or other knowledgeable system
that may already contain all the details of proxy targets. To use static files
in :conf_master:`pillar_roots`, pattern your files after the following examples:

``/etc/salt/pillar/top.sls``

.. code-block:: yaml

    base:
      router1:
        - router1
      router2:
        - router2
      switch1:
        - switch1
      switch2:
        - switch2
      cpe1:
        - cpe1

``/etc/salt/pillar/router1.sls``

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: junos
      host: r1.bbone.as1234.net
      username: my_username
      password: my_password

``/etc/salt/pillar/router2.sls``

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: iosxr
      host: r2.bbone.as1234.net
      username: my_username
      password: my_password
      optional_args:
        port: 22022

``/etc/salt/pillar/switch1.sls``

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: eos
      host: sw1.bbone.as1234.net
      username: my_username
      password: my_password
      optional_args:
        enable_password: my_secret

``/etc/salt/pillar/switch2.sls``

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: nxos
      host: sw2.bbone.as1234.net
      username: my_username
      password: my_password

``/etc/salt/pillar/cpe1.sls``

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: ios
      host: cpe1.edge.as1234.net
      username: ''
      password: ''
      optional_args:
        use_keys: True
        auto_rollback_on_error: True

CLI examples
############

Display the complete running configuration on ``router1``:

.. code-block:: bash

    $ sudo salt 'router1' net.config source='running'

Retrieve the NTP servers configured on all devices:

.. code-block:: yaml

    $ sudo salt '*' ntp.servers
    router1:
      ----------
      comment:
      out:
          - 1.2.3.4
      result:
          True
    cpe1:
      ----------
      comment:
      out:
          - 1.2.3.4
      result:
          True
    switch2:
      ----------
      comment:
      out:
          - 1.2.3.4
      result:
          True
    router2:
      ----------
      comment:
      out:
          - 1.2.3.4
      result:
          True
    switch1:
      ----------
      comment:
      out:
          - 1.2.3.4
      result:
          True

Display the ARP tables on all Cisco devices running IOS-XR 5.3.3:

.. code-block:: bash

    $ sudo salt -G 'os:iosxr and version:5.3.3' net.arp

Return operational details for interfaces from Arista switches:

.. code-block:: bash

    $ sudo salt -C 'sw* and os:eos' net.interfaces

Execute traceroute from the edge of the network:

.. code-block:: bash

    $ sudo salt 'router*' net.traceroute 8.8.8.8 vrf='CUSTOMER1-VRF'

Verbatim display from the CLI of Juniper routers:

.. code-block:: bash

    $ sudo salt -C 'router* and G@os:junos' net.cli 'show version and haiku'

Retrieve the results of the RPM probes configured on Juniper MX960 routers:

.. code-block:: bash

    $ sudo salt -C 'router* and G@os:junos and G@model:MX960' probes.results

Return the list of configured users on the CPEs:

.. code-block:: bash

    $ sudo salt 'cpe*' users.config

Using the :mod:`BGP finder <salt.runners.bgp>`, return the list of BGP neighbors
that are down:

.. code-block:: bash

    $ sudo salt-run bgp.neighbors up=False

Using the :mod:`NET finder <salt.runners.net>`, determine the devices containing
the pattern "PX-1234-LHR" in their interface description:

.. code-block:: bash

    $ sudo salt-run net.find PX-1234-LHR

Cross-platform configuration management example: NTP
####################################################

Assuming that the user adds the following two lines under
:conf_master:`file_roots`:

.. code-block:: yaml

    file_roots:
      base:
        - /etc/salt/pillar/
        - /etc/salt/templates/
        - /etc/salt/states/

Define the list of NTP peers and servers wanted:

``/etc/salt/pillar/ntp.sls``

.. code-block:: yaml

    ntp.servers:
      - 1.2.3.4
      - 5.6.7.8
    ntp.peers:
       - 10.11.12.13
       - 14.15.16.17

Include the new file: for example, if we want to have the same NTP servers on all
network devices, we can add the following line inside the ``top.sls`` file:

.. code-block:: yaml

    '*':
      - ntp

``/etc/salt/pillar/top.sls``

.. code-block:: yaml

    base:
      '*':
        - ntp
      router1:
        - router1
      router2:
        - router2
      switch1:
        - switch1
      switch2:
        - switch2
      cpe1:
        - cpe1

Or include only where needed:

``/etc/salt/pillar/top.sls``

.. code-block:: yaml

    base:
      router1:
        - router1
        - ntp
      router2:
        - router2
        - ntp
      switch1:
        - switch1
      switch2:
        - switch2
      cpe1:
        - cpe1

Define the cross-vendor template:

``/etc/salt/templates/ntp.jinja``

.. code-block:: jinja

    {%- if grains.vendor|lower == 'cisco' %}
      no ntp
      {%- for server in servers %}
      ntp server {{ server }}
      {%- endfor %}
      {%- for peer in peers %}
      ntp peer {{ peer }}
      {%- endfor %}
    {%- elif grains.os|lower == 'junos' %}
      system {
        replace:
        ntp {
          {%- for server in servers %}
          server {{ server }};
          {%- endfor %}
          {%- for peer in peers %}
          peer {{ peer }};
          {%- endfor %}
        }
      }
    {%- endif %}

Define the SLS state file, making use of the
:mod:`Netconfig state module <salt.states.netconfig>`:

``/etc/salt/states/router/ntp.sls``

.. code-block:: yaml

    ntp_config_example:
      netconfig.managed:
        - template_name: salt://ntp.jinja
        - peers: {{ pillar.get('ntp.peers', []) | json }}
        - servers: {{ pillar.get('ntp.servers', []) | json }}

Run the state and assure NTP configuration consistency across your
multi-vendor network:

.. code-block:: bash

    $ sudo salt 'router*' state.sls router.ntp

Besides CLI, the state can be scheduled or executed when triggered by a certain
event.

JUNOS
-----

Juniper has developed a Junos specific proxy infrastructure which allows
remote execution and configuration management of Junos devices without
having to install SaltStack on the device. The infrastructure includes:

- :mod:`Junos proxy <salt.proxy.junos>`
- :mod:`Junos execution module <salt.modules.junos>`
- :mod:`Junos state module <salt.states.junos>`
- :mod:`Junos syslog engine <salt.engines.junos_syslog>`

The execution and state modules are implemented using junos-eznc (PyEZ).
Junos PyEZ is a microframework for Python that enables you to remotely manage
and automate devices running the Junos operating system.


Getting started
###############

Install PyEZ on the system which will run the Junos proxy minion.
It is required to run Junos specific modules.

.. code-block:: shell

    pip install junos-eznc

Next, set the master of the proxy minions.

``/etc/salt/proxy``

.. code-block:: yaml

    master: <master_ip>

Add the details of the Junos device. Device details are usually stored in
salt pillars. If the you do not wish to store credentials in the pillar,
one can setup passwordless ssh.

``/srv/pillar/vmx_details.sls``

.. code-block:: yaml

    proxy:
      proxytype: junos
      host: <hostip>
      username: user
      passwd: secret123

Map the pillar file to the proxy minion. This is done in the top file.

``/srv/pillar/top.sls``

.. code-block:: yaml

    base:
      vmx:
        - vmx_details

.. note::

    Before starting the Junos proxy make sure that netconf is enabled on the
    Junos device. This can be done by adding the following configuration on
    the Junos device.

    .. code-block:: shell

        set system services netconf ssh

Start the salt master.

.. code-block:: bash

    salt-master -l debug


Then start the salt proxy.

.. code-block:: bash

    salt-proxy --proxyid=vmx -l debug

Once the master and junos proxy minion have started, we can run execution
and state modules on the proxy minion. Below are few examples.

CLI examples
############

For detailed documentation of all the junos execution modules refer:
:mod:`Junos execution module <salt.modules.junos>`

Display device facts.

.. code-block:: bash

    $ sudo salt 'vmx' junos.facts


Refresh the Junos facts. This function will also refresh the facts which are
stored in salt grains. (Junos proxy stores Junos facts in the salt grains)

.. code-block:: bash

    $ sudo salt 'vmx' junos.facts_refresh


Call an RPC.

.. code-block:: bash

    $ sudo salt 'vmx' junos.rpc 'get-interface-information' '/var/log/interface-info.txt' terse=True


Install config on the device.

.. code-block:: bash

    $ sudo salt 'vmx' junos.install_config 'salt://my_config.set'


Shutdown the junos device.

.. code-block:: bash

    $ sudo salt 'vmx' junos.shutdown shutdown=True in_min=10


State file examples
###################

For detailed documentation of all the junos state modules refer:
:mod:`Junos state module <salt.states.junos>`

Executing an RPC on Junos device and storing the output in a file.

``/srv/salt/rpc.sls``

.. code-block:: yaml

    get-interface-information:
        junos:
          - rpc
          - dest: /home/user/rpc.log
          - interface_name: lo0


Lock the junos device, load the configuration, commit it and unlock
the device.

``/srv/salt/load.sls``

.. code-block:: yaml

    lock the config:
      junos.lock

    salt://configs/my_config.set:
      junos:
        - install_config
        - timeout: 100
        - diffs_file: 'var/log/diff'

    commit the changes:
      junos:
        - commit

    unlock the config:
      junos.unlock


According to the device personality install appropriate image on the device.

``/srv/salt/image_install.sls``

.. code-block:: jinja

    {% if grains['junos_facts']['personality'] == MX %}
    salt://images/mx_junos_image.tgz:
      junos:
        - install_os
        - timeout: 100
        - reboot: True
    {% elif grains['junos_facts']['personality'] == EX %}
    salt://images/ex_junos_image.tgz:
      junos:
        - install_os
        - timeout: 150
    {% elif grains['junos_facts']['personality'] == SRX %}
    salt://images/srx_junos_image.tgz:
      junos:
        - install_os
        - timeout: 150
    {% endif %}

Junos Syslog Engine
###################

:mod:`Junos Syslog Engine <salt.engines.junos_syslog>` is a Salt engine
which receives data from various Junos devices, extracts event information and
forwards it on the master/minion event bus. To start the engine on the salt
master, add the following configuration in the master config file.
The engine can also run on the salt minion.

``/etc/salt/master``

.. code-block:: yaml

    engines:
      - junos_syslog:
          port: xxx

For junos_syslog engine to receive events, syslog must be set on the Junos device.
This can be done via following configuration:

.. code-block:: shell

    set system syslog host <ip-of-the-salt-device> port xxx any any

.. toctree::
    :maxdepth: 2
    :glob:
