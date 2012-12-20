=======
FreeBSD
=======

Salt was added to the FreeBSD ports tree Dec 26th, 2011 by Christer Edwards
<christer.edwards@gmail.com>. It has been tested on FreeBSD 7.4, 8.2 and 9.0
releases.

Salt is dependent on the following additional ports. These will be installed as
dependencies of the ``sysutils/salt`` port. ::

   /devel/py-yaml
   /devel/py-pyzmq
   /devel/py-Jinja2
   /devel/py-msgpack
   /security/py-pycrypto
   /security/py-m2crypto

Installation
============

To install Salt from the FreeBSD ports tree, use the command:

.. code-block:: bash

   cd /usr/ports/sysutils/salt && make install clean

Once the port is installed, it is necessary to make a few configuration changes.
These include defining the IP to bind to (optional), and some configuration
path changes to make salt fit more natively into the FreeBSD filesystem tree.

Post-installation tasks
=======================

**Master**

Copy the sample configuration file:

.. code-block:: bash

   cp /usr/local/etc/salt/master.sample /usr/local/etc/salt/master

**rc.conf**

Activate the Salt Master in ``/etc/rc.conf`` or ``/etc/rc.conf.local`` and add:

.. code-block:: diff

   + salt_master_enable="YES"

**Start the Master**

Start the Salt Master as follows:

.. code-block:: bash

   service salt_master start

**Minion**

Copy the sample configuration file:

.. code-block:: bash

   cp /usr/local/etc/salt/minion.sample /usr/local/etc/salt/minion

**rc.conf**

Activate the Salt Minion in ``/etc/rc.conf`` or ``/etc/rc.conf.local`` and add:

.. code-block:: diff

   + salt_minion_enable="YES"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: bash

   service salt_minion start

Now go to the :doc:`Configuring Salt</topics/configuration>` page.


