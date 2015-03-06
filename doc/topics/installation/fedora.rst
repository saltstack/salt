==================================
Fedora
==================================

Beginning with version 0.9.4, Salt has been available in the primary Fedora
repositories and `EPEL`_. It is installable using yum. Fedora will have more
up to date versions of Salt than other members of the Red Hat family, which
makes it a great place to help improve Salt!

**WARNING**: Fedora 19 comes with systemd 204.  Systemd has known bugs fixed in
later revisions that prevent the salt-master from starting reliably or opening
the network connections that it needs to.  It's not likely that a salt-master
will start or run reliably on any distribution that uses systemd version 204 or
earlier.  Running salt-minions should be OK.

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

Installing from ``updates-testing``
-----------------------------------

When a new Salt release is packaged, it is first admitted into the
``updates-testing`` repository, before being moved to the stable repo.

To install from ``updates-testing``, use the ``enablerepo`` argument for yum:

.. code-block:: bash

    yum --enablerepo=updates-testing install salt-master
    yum --enablerepo=updates-testing install salt-minion

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