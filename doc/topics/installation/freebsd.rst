=======
FreeBSD
=======

Salt was added to the FreeBSD ports tree Dec 26th, 2011 by Christer Edwards
<christer.edwards@gmail.com>. It has been tested on FreeBSD 7.4, 8.2, 9.0, and 9.1
releases.

Salt is dependent on the following additional ports. These will be installed as
dependencies of the ``sysutils/py-salt`` port:

.. code-block:: text

   /devel/py-yaml
   /devel/py-pyzmq
   /devel/py-Jinja2
   /devel/py-msgpack
   /security/py-pycrypto
   /security/py-m2crypto

Installation
============

On FreeBSD 10 and later, to install Salt from the FreeBSD pkgng repo, use the command:

.. code-block:: bash

    pkg install py27-salt

On older versions of FreeBSD, to install Salt from the FreeBSD ports tree, use the command:

.. code-block:: bash

    make -C /usr/ports/sysutils/py-salt install clean

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
   + salt_minion_paths="/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: bash

   service salt_minion start

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
