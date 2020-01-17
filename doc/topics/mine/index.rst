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
all the Minions every :ref:`mine_interval`, resulting in
almost fresh data at any given time, with much less overhead.

Mine Functions
==============

To enable the Salt Mine the ``mine_functions`` option needs to be applied to a
Minion. This option can be applied via the Minion's configuration file, or the
Minion's Pillar. The ``mine_functions`` option dictates what functions are
being executed and allows for arguments to be passed in.  The list of
functions are available in the :py:mod:`salt.module`.  If no arguments
are passed, an empty list must be added like in the ``test.ping`` function in
the example below:

.. code-block:: yaml

    mine_functions:
      test.ping: []
      network.ip_addrs:
        interface: eth0
        cidr: 10.0.0.0/8

In the example above :py:mod:`salt.modules.network.ip_addrs` has additional
filters to help narrow down the results.  In the above example IP addresses
are only returned if they are on a eth0 interface and in the 10.0.0.0/8 IP
range.

.. versionchanged:: 3000

The format to define mine_functions has been changed to allow the same format
as used for module.run. The old format (above) will still be supported.

.. code-block:: yaml

    mine_functions:
      test.ping: []
      network.ip_addrs:
        - interface: eth0
        - cidr: 10.0.0.0/8
      test.arg:
        - isn't
        - this
        - fun
        - this: that
        - salt: stack

.. _mine_minion-side-acl:

Minion-side Access Control
--------------------------

.. versionadded:: 3000

Mine functions can be targeted to only be available to specific minions. This
uses the same targeting parameters as :ref:`targeting` but with keywords ``allow_tgt``
and ``allow_tgt_type``. When a minion requests a function from the salt mine that
is not allowed to be requested by that minion (i.e. when looking up the combination
of ``allow_tgt`` and ``allow_tgt_type`` and the requesting minion is not in the list)
it will get no data, just as if the requested function is not present in the salt mine.

.. code-block:: yaml

    mine_functions:
      network.ip_addrs:
        - interface: eth0
        - cidr: 10.0.0.0/8
        - allow_tgt: 'G@role:master'
        - allow_tgt_type: 'compound'


Mine Functions Aliases
----------------------

Function aliases can be used to provide friendly names, usage intentions or to
allow multiple calls of the same function with different arguments. There is a
different syntax for passing positional and key-value arguments. Mixing
positional and key-value arguments is not supported.

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

.. versionchanged:: 3000

With the addition of the module.run-like format for defining mine_functions, the
method of adding aliases remains similar. Just add a ``mine_function`` kwarg with
the name of the real function to call, making the key below ``mine_functions``
the alias:

.. code-block:: yaml

    mine_functions:
      alias_name:
        - mine_function: network.ip_addrs
        - eth0
      internal_ip_addrs:
        - mine_function: network.ip_addrs
        - cidr: 192.168.0.0/16
      ip_list:
        - mine_function: grains.get
        - ip_interfaces

.. _mine_interval:

Mine Interval
=============

The Salt Mine functions are executed when the Minion starts and at a given
interval by the scheduler. The default interval is every 60 minutes and can
be adjusted for the Minion via the ``mine_interval`` option in the minion
config:

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


Minions Targeting with Mine
===========================

The ``mine.get`` function supports various methods of :ref:`Minions targeting
<targeting>` to fetch Mine data from particular hosts, such as glob or regular
expression matching on Minion id (name), grains, pillars and :ref:`compound
matches <targeting-compound>`. See the :py:mod:`salt.modules.mine` module
documentation for the reference.

.. note::

    Pillar data needs to be cached on Master for pillar targeting to work with
    Mine. Read the note in :ref:`relevant section <targeting-pillar>`.

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

Then trigger the minions to refresh their pillar data by running:

.. code-block:: bash

    salt '*' saltutil.refresh_pillar

Verify that the results are showing up in the pillar on the minions by
executing the following and checking for ``network.ip_addrs`` in the output:

.. code-block:: bash

    salt '*' pillar.items

Which should show that the function is present on the minion, but not include
the output:

.. code-block:: shell

    minion1.example.com:
        ----------
        mine_functions:
            ----------
            network.ip_addrs:
                - eth0

Mine data is typically only updated on the master every 60 minutes, this can
be modified by setting:

:file:`/etc/salt/minion.d/mine.conf`:

.. code-block:: yaml

    mine_interval: 5

To force the mine data to update immediately run:

.. code-block:: bash

    salt '*' mine.update

Setup the :py:mod:`salt.states.file.managed` state in
:file:`/srv/salt/haproxy.sls`:

.. code-block:: yaml

    haproxy_config:
      file.managed:
        - name: /etc/haproxy/config
        - source: salt://haproxy_config
        - template: jinja

Create the Jinja template in :file:`/srv/salt/haproxy_config`:

.. code-block:: yaml

    <...file contents snipped...>

    {% for server, addrs in salt['mine.get']('roles:web', 'network.ip_addrs', tgt_type='grain') | dictsort() %}
    server {{ server }} {{ addrs[0] }}:80 check
    {% endfor %}

    <...file contents snipped...>

In the above example, ``server`` will be expanded to the ``minion_id``.

.. note::
    The expr_form argument will be renamed to ``tgt_type`` in the 2017.7.0
    release of Salt.
