.. _proxy-minion-beacon:

.. versionadded:: 2015.8.3

===================
Proxy Minion Beacon
===================


The salt proxy beacon is meant to facilitate configuring
multiple proxies on one or many minions. This should simplify
configuring and managing multiple ``salt-proxy`` processes.

1. On your salt-master, ensure that pillar is configured properly.  Select an ID
   for your proxy (in this example we will name the proxy 'p8000').
   In your pillar topfile, place an entry for your proxy:

.. code-block:: yaml

   base:
     'p8000':
       - p8000

This says that Salt's pillar should load some values for the proxy ``p8000``
from the file ``/srv/pillar/p8000.sls`` (if you have not changed your default pillar_roots)

2. In the pillar root for your base environment, create the ``p8000.sls`` file with the
   following contents: 

.. code-block:: yaml

   proxy:
     # set proxytype for your proxymodule
     proxytype: ssh_sample
     host: saltyVM
     username: salt
     password: badpass

This should complete the proxy setup for ``p8000``

3. `Configure`_ the ``salt_proxy`` beacon

.. code-block:: yaml

    beacons:
      salt_proxy:
        - proxies:
            p8000: {}
            p8001: {}


Once this beacon is configured it will automatically start the ``salt-proxy``
process. If the ``salt-proxy`` process is terminated the beacon will
re-start it.

4. Accept your proxy's key on your salt-master

.. code-block:: bash

   salt-key -y -a p8000
   The following keys are going to be accepted:
   Unaccepted Keys:
   p8000
   Key for minion p8000 accepted.

5. Now you should be able to run commands on your proxy.

.. code-block:: bash

    salt p8000 pkg.list_pkgs

.. _Configure: https://docs.saltstack.com/en/latest/topics/beacons/#configuring-beacons
