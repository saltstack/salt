.. _salt-mine:

.. index:: ! Mine, Salt Mine

=============
The Salt Mine
=============

The Salt Mine is used to collect arbitrary data from minions and store it on
the master. This data is then made available to all minions via the
:py:mod:`salt.modules.mine` module.

The data is gathered on the minion and sent back to the master where only
the most recent data is maintained (if long term data is required use
returners or the external job cache).

Mine Functions
==============

To enable the Salt Mine the `mine_functions` option needs to be applied to a
minion. This option can be applied via the minion's configuration file, or the
minion's Pillar. The `mine_functions` option dictates what functions are being
executed and allows for arguments to be passed in. If no arguments are passed,
an empty list must be added:

.. code-block:: yaml

    mine_functions:
      test.ping: []
      network.ip_addrs:
        interface: eth0
        cidr: '10.0.0.0/8'

Mine Interval
=============

The Salt Mine functions are executed when the minion starts and at a given
interval by the scheduler. The default interval is every 60 minutes and can
be adjusted for the minion via the `mine_interval` option:

.. code-block:: yaml

    mine_interval: 60

Example
=======

One way to use data from Salt Mine is in a State. The values can be retrieved
via Jinja and used in the SLS file. The following example is a partial HAProxy
configuration file and pulls IP addresses from all minions with the "web" grain
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
      file:
        - managed
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
