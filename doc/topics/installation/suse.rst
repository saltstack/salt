=================
SUSE Installation
=================

openSUSE
--------

For openSUSE Factory run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/openSUSE_Factory/devel:languages:python.repo
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

SLES 11 SP2
-----------

For SLE 11 SP2 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/devel:languages:python/SLE_11_SP2/devel:languages:python.repo
    zypper refresh
    zypper install salt salt-minion salt-master

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

