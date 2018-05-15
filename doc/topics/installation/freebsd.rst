=======
FreeBSD
=======

Installation
============

Salt is available in the FreeBSD ports at `sysutils/py-salt. <https://www.freshports.org/sysutils/py-salt/>`__


FreeBSD binary repo
===================

.. code-block:: shell

    pkg install py27-salt

FreeBSD ports
=============

By default salt is packaged using python 2.7, but if you build your own packages from FreeBSD ports either by hand or with poudriere you can instead package it with your choice of python. Add a line to /etc/make.conf to choose your python flavour:

.. code-block:: shell

    echo "DEFAULT_VERSIONS+= python=3.6" >> /etc/make.conf

Then build the port and install:

.. code-block:: shell

    cd /usr/ports/sysutils/py-salt
    make install

Post-installation tasks
=======================

**Master**

Copy the sample configuration file:

.. code-block:: shell

   cp /usr/local/etc/salt/master.sample /usr/local/etc/salt/master

**rc.conf**

Activate the Salt Master in ``/etc/rc.conf``:

.. code-block:: shell

   sysrc salt_master_enable="YES"

**Start the Master**

Start the Salt Master as follows:

.. code-block:: shell

   service salt_master start

**Minion**

Copy the sample configuration file:

.. code-block:: shell

   cp /usr/local/etc/salt/minion.sample /usr/local/etc/salt/minion

**rc.conf**

Activate the Salt Minion in ``/etc/rc.conf``:

.. code-block:: shell

   sysrc salt_minion_enable="YES"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: shell

   service salt_minion start

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
