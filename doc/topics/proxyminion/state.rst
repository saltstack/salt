.. _proxy-minion-states:

.. versionadded:: 2015.8.2

===================
Proxy Minion States
===================


Salt proxy state can be used to deploy, configure and run
a ``salt-proxy`` instance on your minion. Configure proxy settings
on the master side and the state configures and runs ``salt-proxy``
on the remote end.

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

3. Create the following state in your state tree
   (let's name it salt_proxy.sls)

.. code-block:: yaml

  salt-proxy-configure:
    salt_proxy.configure_proxy:
      - proxyname: p8000
      - start: True # start the process if it isn't running

4. Make sure your salt-master and salt-minion are running.

5. Run the state salt_proxy on the minion where you want to run ``salt-proxy``

Example using ``state.sls`` to configure and run ``salt-proxy``

.. code-block:: bash

  # salt device_minion state.sls salt_proxy

This starts salt-proxy on ``device_minion``

6. Accept your proxy's key on your salt-master

.. code-block:: bash

   salt-key -y -a p8000
   The following keys are going to be accepted:
   Unaccepted Keys:
   p8000
   Key for minion p8000 accepted.

7. Now you should be able to run commands on your proxy.

.. code-block:: bash

    salt p8000 pkg.list_pkgs
