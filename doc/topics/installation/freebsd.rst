=======
FreeBSD
=======

Installation
============

Salt is available in binary package form from both the FreeBSD pkgng repository
or directly from SaltStack. The instructions below outline installation via
both methods:

FreeBSD repo
============

The FreeBSD pkgng repository is preconfigured on systems 10.x and above. No
configuration is needed to pull from these repositories.

.. code-block:: bash

    pkg install py27-salt

These packages are usually available within a few days of upstream release.

Post-installation tasks
=======================

**Master**

Copy the sample configuration file:

.. code-block:: bash

   cp /usr/local/etc/salt/master.sample /usr/local/etc/salt/master

**rc.conf**

Activate the Salt Master in ``/etc/rc.conf``:

.. code-block:: bash

   sysrc salt_master_enable="YES"

**Start the Master**

Start the Salt Master as follows:

.. code-block:: bash

   service salt_master start

**Minion**

Copy the sample configuration file:

.. code-block:: bash

   cp /usr/local/etc/salt/minion.sample /usr/local/etc/salt/minion

**rc.conf**

Activate the Salt Minion in ``/etc/rc.conf``:

.. code-block:: bash

   sysrc salt_minion_enable="YES"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: bash

   service salt_minion start

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
