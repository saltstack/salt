.. _installation-suse:

====
SUSE
====

Installation from the Official SaltStack Repository
===================================================

Packages for SUSE 12 SP1, SUSE 12, SUSE 11, openSUSE 13 and openSUSE Leap 42.1
are available in the SaltStack Repository.

Instructions are at https://repo.saltstack.com/#suse.

Installation from the SUSE Repository
=====================================

Since openSUSE 13.2, Salt 2014.1.11 is available in the primary repositories.
With the release of SUSE manager 3 a new repository setup has been created.
The new repo will by systemsmanagement:saltstack, which is the source
for newer stable packages. For backward compatibility a linkpackage will be
created to the old devel:language:python repo.
All development of suse packages will be done in systemsmanagement:saltstack:testing.
This will ensure that salt will be in mainline suse repo's, a stable release
repo and a testing repo for further enhancements.

Installation
============

Salt can be installed using ``zypper`` and is available in the standard openSUSE/SLES
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

For openSUSE Tumbleweed run the following as root:

.. code-block:: bash

    zypper install salt salt-minion salt-master


For openSUSE 15.0 Leap run the following as root:

.. code-block:: bash

    zypper install salt salt-minion salt-master


For openSUSE 15.1 run the following as root:

.. code-block:: bash

    zypper install salt salt-minion salt-master

SUSE Linux Enterprise
---------------------

For SLE 12 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/systemsmanagement:/saltstack/SLE_12/systemsmanagement:saltstack.repo
    zypper refresh
    zypper install salt salt-minion salt-master

For SLE 11 SP4 run the following as root:

.. code-block:: bash

    zypper addrepo http://download.opensuse.org/repositories/systemsmanagement:/saltstack/SLE_11_SP4/systemsmanagement:saltstack.repo
    zypper refresh
    zypper install salt salt-minion salt-master

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
