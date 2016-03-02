.. _salt-mine:

.. index:: ! Mine, Salt Mine

=============
The Salt Mine
=============

The Salt Mine is used to collect arbitrary data from Minions and store it on
the Master. This data is then made available to all Minions via the
:py:mod:`salt.modules.mine` module.

Mine data is gathered on the Minion and sent back to the Master where only the
most recent data is maintained (if long term data is required use returners or
the external job cache).

Mine vs Grains
==============

Mine data is designed to be much more up-to-date than grain data. Grains are
refreshed on a very limited basis and are largely static data. Mines are
designed to replace slow peer publishing calls when Minions need data from
other Minions. Rather than having a Minion reach out to all the other Minions
for a piece of data, the Salt Mine, running on the Master, can collect it from
all the Minions every :ref:`mine-interval`, resulting in
almost fresh data at any given time, with much less overhead.

Mine Functions
==============

To enable the Salt Mine the ``mine_functions`` option needs to be applied to a
Minion. This option can be applied via the Minion's configuration file, or the
Minion's Pillar. The ``mine_functions`` option dictates what functions are
being executed and allows for arguments to be passed in. If no arguments are
passed, an empty list must be added:

.. code-block:: yaml

    mine_functions:
      test.ping: []
      network.ip_addrs:
        interface: eth0
        cidr: '10.0.0.0/8'

Mine Functions Aliases
----------------------

Function aliases can be used to provide friendly names, usage intentions or to allow
multiple calls of the same function with different arguments.  There is a different
syntax for passing positional and key-value arguments.  Mixing positional and
key-value arguments is not supported.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    mine_functions:
      network.ip_addrs: [eth0]
      networkplus.internal_ip_addrs: []
      internal_ip_addrs:
        mine_function: network.ip_addrs
        cidr: 192.168.0.0/16
      ip_list:
        - mine_function: grains.get
        - ip_interfaces


.. _mine_interval:

Mine Interval
=============

The Salt Mine functions are executed when the Minion starts and at a given
interval by the scheduler. The default interval is every 60 minutes and can
be adjusted for the Minion via the ``mine_interval`` option:

.. code-block:: yaml

    mine_interval: 60

Mine in Salt-SSH
================

As of the 2015.5.0 release of salt, salt-ssh supports ``mine.get``.

Because the Minions cannot provide their own ``mine_functions`` configuration,
we retrieve the args for specified mine functions in one of three places,
searched in the following order:

1. Roster data
2. Pillar
3. Master config

The ``mine_functions`` are formatted exactly the same as in normal salt, just
stored in a different location. Here is an example of a flat roster containing
``mine_functions``:

.. code-block:: yaml

    test:
      host: 104.237.131.248
      user: root
      mine_functions:
        cmd.run: ['echo "hello!"']
        network.ip_addrs:
          interface: eth0

.. note::

    Because of the differences in the architecture of salt-ssh, ``mine.get``
    calls are somewhat inefficient. Salt must make a new salt-ssh call to each
    of the Minions in question to retrieve the requested data, much like a
    publish call. However, unlike publish, it must run the requested function
    as a wrapper function, so we can retrieve the function args from the pillar
    of the Minion in question. This results in a non-trivial delay in
    retrieving the requested data.

Example
=======

One way to use data from Salt Mine is in a State. The values can be retrieved
via Jinja and used in the SLS file. The following example is a partial HAProxy
configuration file and pulls IP addresses from all Minions with the "web" grain
to add them to the pool of load balanced servers.

:file:`/srv/pillar/top.sls`:

.. code-block:: yaml

    base:
      'G@roles:web':
        - web

:file:`/srv/pillar/web.sls`:

.. code-block:: yaml

    mine_functions:
      network.ip_addrs: [eth0]

:file:`/etc/salt/minion.d/mine.conf`:

.. code-block:: yaml

    mine_interval: 5

:file:`/srv/salt/haproxy.sls`:

.. code-block:: yaml

    haproxy_config:
      file.managed:
        - name: /etc/haproxy/config
        - source: salt://haproxy_config
        - template: jinja

:file:`/srv/salt/haproxy_config`:

.. code-block:: yaml

    <...file contents snipped...>

    {% for server, addrs in salt['mine.get']('roles:web', 'network.ip_addrs', expr_form='grain').items() %}
    server {{ server }} {{ addrs[0] }}:80 check
    {% endfor %}

    <...file contents snipped...>
