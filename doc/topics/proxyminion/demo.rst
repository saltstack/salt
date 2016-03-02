====================================
Salt Proxy Minion End-to-End Example
====================================

The following is walkthrough that documents how to run a sample REST service
and configure one or more proxy minions to talk to and control it.

1. Ideally, create a Python virtualenv in which to run the REST service.  This
   is not strictly required, but without a virtualenv you will need to install
   ``bottle`` via pip globally on your system

2. Clone https://github.com/saltstack/salt-contrib
   and copy the contents of the directory ``proxyminion_rest_example``
   somewhere on a machine that is reachable from the machine on which you want to
   run the salt-proxy.  This machine needs Python 2.7 or later.

3. Install bottle version 0.12.8 via pip or easy_install

.. code-block:: bash

   pip install bottle==0.12.8

4. Run ``python rest.py --help`` for usage

5. Start the REST API on an appropriate port and IP.

6. Load the REST service's status page in your browser by going to the IP/port
   combination (e.g. http://127.0.0.1:8000)

7. You should see a page entitled "Salt Proxy Minion" with two sections,
   one for "services" and one for "packages" and you should see a log entry in
   the terminal where you started the REST process indicating that the index
   page was retrieved.


.. image:: /_static/rest_status_screen.png

Now, configure your salt-proxy.

1. Edit ``/etc/salt/proxy`` and add an entry for your master's location

.. code-block:: yaml

   master: localhost

2. On your salt-master, ensure that pillar is configured properly.  Select an ID
   for your proxy (in this example we will name the proxy with the letter 'p'
   followed by the port the proxy is answering on).  In your pillar topfile,
   place an entry for your proxy:

.. code-block:: yaml

   base:
     'p8000':
       - p8000


This says that Salt's pillar should load some values for the proxy ``p8000``
from the file /srv/pillar/p8000.sls (if you have not changed your default pillar_roots)

3. In the pillar root for your base environment, create this file:


.. code-block:: yaml

   p8000.sls
   ---------

   proxy:
     proxytype: rest_sample
     url: http://<IP your REST listens on>:port

In other words, if your REST service is listening on port 8000 on 127.0.0.1
the 'url' key above should say ``url: http://127.0.0.1:8000``

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

7. Now you should be able to ping your proxy.  When you ping, you should see
   a log entry in the terminal where the REST service is running.

.. code-block:: bash

    salt p8000 test.ping

8. The REST service implements a degenerately simple pkg and service provider as
   well as a small set of grains.  To "install" a package, use a standard
   ``pkg.install``.  If you pass '==' and a verrsion number after the package
   name then the service will parse that and accept that as the package's
   version.

9. Try running ``salt p8000 grains.items`` to see what grains are available.  You
   can target proxies via grains if you like.

10. You can also start and stop the available services (apache, redbull, and
    postgresql with ``service.start``, etc.

11. States can be written to target the proxy.  Feel free to experiment with
    them.

