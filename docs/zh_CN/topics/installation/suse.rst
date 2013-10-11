=================
SUSE Installation
=================

With openSUSE 13.1, Salt 0.16.4 has been available in the primary repositories.
The devel:language:python repo will have more up to date versions of salt, 
all package development will be done there.

Installation
============

Salt can be installed using ``zypper`` and is available in the standard openSUSE 13.1
repositories.

Stable Release
--------------

Salt is packaged separately for the minion and the master. It is necessary only to
install the appropriate package for the role the machine will play. Typically, there
will be one master and multiple minions.

.. code-block:: bash

    zypper install salt-master
    zypper install salt-minion

Post-installation tasks openSUSE
================================

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

Post-installation tasks SLES
============================

**Master**

To have the Master start automatically at boot time:

.. code-block:: bash

    chkconfig salt-master on

To start the Master:

.. code-block:: bash

    rcsalt-master start

**Minion**

To have the Minion start automatically at boot time:

.. code-block:: bash

    chkconfig salt-minion on

To start the Minion:

.. code-block:: bash

    rcsalt-minion start


Unstable Release
----------------

openSUSE
--------

For openSUSE Factory run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_Factory/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

For openSUSE 13.1 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_13.1/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master    

For openSUSE 12.3 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_12.3/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

For openSUSE 12.2 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_12.2/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

For openSUSE 12.1 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_12.1/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

For bleeding edge python Factory run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/bleeding_edge_python_Factory/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

Suse Linux Enterprise
---------------------

For SLE 11 SP3 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/SLE_11_SP3/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master
    
For SLE 11 SP2 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/SLE_11_SP2/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
