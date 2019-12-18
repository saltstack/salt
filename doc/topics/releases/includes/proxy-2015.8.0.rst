:orphan:

.. _proxy-2015.8.0:

=========================
Proxy Minion Enhancements
=========================

Proxy Minions have undergone a significant overhaul in 2015.8.

- Proxies are now more of a first-class citizen in the Salt universe
- Proxies are no longer started by a "parent minion", they are started on the
  command line with the new ``salt-proxy`` command
- The default configuration file for proxies is now ``/etc/salt/proxy``.
- The default logfile for proxies is now ``/var/log/salt/proxy``.
- ``salt-proxy`` takes a ``--proxyid`` switch.  This becomes the id of the proxy
  minion, and thus the pillar key under which the configuration for the proxy is
  looked up.
- Proxies have been lightly tested with the new TCP transport.  They still do
  not work with the RAET transport.
- The pillar structure is therefore different than in previous releases.  In
  earlier releases you might have something that looked like this:

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      minioncontroller:
        - dumbdevice1
        - dumbdevice2

``/srv/pillar/dumbdevice1.sls``:

.. code-block:: yaml

    dumbdevice1:
      proxy:
        proxytype: networkswitch
        host: 172.23.23.5
        username: root
        passwd: letmein

``/srv/pillar/dumbdevice2.sls``:

.. code-block:: yaml

    dumbdevice2:
      proxy:
        proxytype: networkswitch
        host: 172.23.23.6
        username: root
        passwd: letmein


This would cause the minion with id ``minioncontroller`` to fork off two
processes and rename their minion id's to ``dumbdevice1`` and ``dumbdevice2``.
These processes would initiate a new connection to the master.

For proxy minion controllers this made it quite difficult to tell which process
was doing what.  Also, if the controlling minion died for any reason, it would
take all the proxies with it.  The new pillar structure does away with the
id's in the lower level pillar files and brings proxy configuration to the same
level with all other minions.

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      dumbdevice1:
        - dumbdevice1
      dumbdevice2:
        - dumbdevice2

``/srv/pillar/dumbdevice1.sls``:

.. code-block:: yaml

proxy:
  proxytype: networkswitch
  host: 172.23.23.5
  username: root
  passwd: letmein

``/srv/pillar/dumbdevice2.sls``:

.. code-block:: yaml

proxy:
  proxytype: networkswitch
  host: 172.23.23.6
  username: root
  passwd: letmein

Proxies can be better tracked via system process utilities:

..code-block:: bash

    root@raring64:/var/log/salt# ps guax | grep p8
    root     15215  pts/3    S+   10:57   0:00 python salt-proxy -l debug --proxyid=p8000
    root     15275  pts/5    S+   10:57   0:00 python salt-proxy -l debug --proxyid=p8002

Proxies still gather a significant number of grains from the host.  This is
useful for targeting, but does not obviate the need for custom grains to better
support your controlled devices.  See the proxy documentation for writing
grains modules for your proxy.

Future enhancements of proxy minions could include execution modules and states
for easier proxy process management.

See :ref:`Proxy Minion Documentation <proxy-minion>`.
