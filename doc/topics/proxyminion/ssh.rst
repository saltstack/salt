.. _proxy-minion-ssh-end-to-end-example:

========================================
Salt Proxy Minion SSH End-to-End Example
========================================

The following is walkthrough that documents how to run a sample SSH service
and configure one or more proxy minions to talk to and control it.

1. This walkthrough uses a custom SSH shell to provide an end to end example.
   Any other shells can be used too.

2. Setup the proxy command shell as shown https://github.com/saltstack/salt-contrib/tree/master/proxyminion_ssh_example


Now, configure your salt-proxy.

1. Edit ``/etc/salt/proxy`` and add an entry for your master's location

.. code-block:: yaml

   master: localhost
   multiprocessing: False

2. On your salt-master, ensure that pillar is configured properly.  Select an ID
   for your proxy (in this example we will name the proxy with the letter 'p'
   followed by the port the proxy is answering on).  In your pillar topfile,
   place an entry for your proxy:

.. code-block:: yaml

   base:
     'p8000':
       - p8000


This says that Salt's pillar should load some values for the proxy ``p8000``
from the file ``/srv/pillar/p8000.sls`` (if you have not changed your default pillar_roots)

3. In the pillar root for your base environment, create the ``p8000.sls`` file with the
   following contents:


.. code-block:: yaml

   proxy:
     proxytype: ssh_sample
     host: saltyVM
     username: salt
     password: badpass


4. Make sure your salt-master is running.

5. Start the salt-proxy in debug mode

.. code-block:: bash

   salt-proxy --proxyid=p8000 -l debug

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

8. The SSH shell implements a degenerately simple pkg.
   To "install" a package, use a standard
   ``pkg.install``.  If you pass '==' and a version number after the package
   name then the service will parse that and accept that as the package's
   version.
