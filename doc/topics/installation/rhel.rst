==========================================================================
RHEL / CentOS / Scientific Linux / Amazon Linux / Oracle Linux
==========================================================================

Beginning with version 0.9.4, Salt has been available in `EPEL`_. It is installable using yum. Salt should work properly with all mainstream derivatives
of RHEL, including CentOS, Scientific Linux, Oracle Linux and Amazon Linux. Report any bugs or issues to the salt GitHub project.

Installation
============

Salt and all dependencies have been accepted into the yum repositories for
EPEL5 and EPEL6. The latest salt version can be found in epel-testing, while an
older but more tested version can be found in regular epel.

Example showing how to install salt from epel-testing:

.. code-block:: bash

    yum --enablerepo=epel-testing install salt-minion

On RHEL6, the proper Jinja package 'python-jinja2' was moved from EPEL to the
"RHEL Server Optional Channel". Verify this repository is enabled before
installing salt on RHEL6.

.. _`EPEL`: http://fedoraproject.org/wiki/EPEL


Salt can be installed using ``yum`` and is available in the standard Fedora
repositories.

Enabling EPEL on RHEL
=====================

If EPEL is not enabled on your system, you can use the following commands to
enable it.

For RHEL 5:

.. code-block:: bash

    rpm -Uvh http://mirror.pnl.gov/epel/5/i386/epel-release-5-4.noarch.rpm

For RHEL 6:

.. code-block:: bash

    rpm -Uvh http://ftp.linux.ncsu.edu/pub/epel/6/i386/epel-release-6-8.noarch.rpm


Stable Release
--------------

Salt is packaged separately for the minion and the master. It is necessary only to install the appropriate package for the role the machine will play. Typically, there will be one master and multiple minions.

On the salt-master, run this:

.. code-block:: bash

    yum install salt-master

On each salt-minion, run this:

.. code-block:: bash

    yum install salt-minion

Post-installation tasks
=======================

**Master**

To have the Master start automatically at boot time:

.. code-block:: bash

    chkconfig salt-master on


To start the Master:

.. code-block:: bash

    service salt-master start

**Minion**

To have the Minion start automatically at boot time:

.. code-block:: bash

    chkconfig salt-minion on


To start the Minion:

.. code-block:: bash

    service salt-minion start

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
