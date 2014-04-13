==================================
Fedora
==================================

Beginning with version 0.9.4, Salt has been available in the primary Fedora
repositories and `EPEL`_. It is installable using yum. Fedora will have more
up to date versions of Salt than other members of the Red Hat family, which
makes it a great place to help improve Salt!

Installation
============

Salt can be installed using ``yum`` and is available in the standard Fedora
repositories.

Stable Release
--------------

Salt is packaged separately for the minion and the master. It is necessary only to
install the appropriate package for the role the machine will play. Typically, there
will be one master and multiple minions.

.. code-block:: bash

    yum install salt-master
    yum install salt-minion

.. _`EPEL`: http://fedoraproject.org/wiki/EPEL

Post-installation tasks
=======================

**Master**

To have the Master start automatically at boot time:

.. code-block:: bash

    systemctl enable salt-master.service

To start the Master:

.. code-block:: bash

    systemctl start salt-master.service

**Minion**

To have the Minion start automatically at boot time:

.. code-block:: bash

    systemctl enable salt-minion.service

To start the Minion:

.. code-block:: bash

    systemctl start salt-minion.service

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
