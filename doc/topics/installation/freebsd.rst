=======
FreeBSD
=======

Installation
============

Salt is available in the FreeBSD ports tree at `sysutils/py-salt
<https://www.freshports.org/sysutils/py-salt/>`_.


FreeBSD binary repo
===================


For Python 2.7 use:

Install Salt via the official package repository. Salt is packaged both as a Python 2.7 or 3.6 version.


.. code-block:: bash

    pkg install py27-salt


For Python 3.6 use:


.. code-block:: bash

    pkg install py36-salt


FreeBSD ports
=============

Installation from ports:

.. code-block:: bash

    cd /usr/ports/sysutils/py-salt
    make install

Python 3.6 can be used by setting default Python version to 3.6:  
    
.. code-block:: text

    echo "DEFAULT_VERSIONS+= python=3.6" >> /etc/make.conf


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
