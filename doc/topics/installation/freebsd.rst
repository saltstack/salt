.. meta::
   :description: How do you install Salt on FreeBSD?
   :keywords: freebsd

=======
FreeBSD
=======

Installation
============

Salt is available in the FreeBSD ports tree at `sysutils/py-salt
<https://www.freshports.org/sysutils/py-salt/>`_.


FreeBSD binary repo
===================


Install Salt on FreeBSD via the official package repository. Salt is packaged
with whichever Python version is currently the `default on FreeBSD <https://cgit.freebsd.org/ports/tree/Mk/bsd.default-versions.mk>`_.

Python 3.8 is currently default, install from packages like this:

.. code-block:: bash

    pkg install py38-salt


FreeBSD ports
=============

Installation from ports:

.. code-block:: bash

    cd /usr/ports/sysutils/py-salt
    make install

Python 3.7 can be used by setting default Python version to 3.7:  
    
.. code-block:: text

    echo "DEFAULT_VERSIONS+= python=3.7" >> /etc/make.conf


Post-installation tasks
=======================


**rc.conf**

Activate the Salt Master in ``/etc/rc.conf``:

.. code-block:: bash

   sysrc salt_master_enable="YES"

**Start the Master**

Start the Salt Master as follows:

.. code-block:: bash

   service salt_master start

**rc.conf**

Activate the Salt Minion in ``/etc/rc.conf``:

.. code-block:: bash

   sysrc salt_minion_enable="YES"

**Start the Minion**

Start the Salt Minion as follows:

.. code-block:: bash

   service salt_minion start

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
