==============================================================
RHEL / CentOS / Scientific Linux / Amazon Linux / Oracle Linux
==============================================================

Installation Using pip
======================

Since Salt is on `PyPI`_, it can be installed using pip, though most users
prefer to install using RPMs (which can be installed from `EPEL`_).
Installation from pip is easy:

.. _`PyPI`: https://pypi.python.org/pypi/salt

.. code-block:: bash

    pip install salt

.. warning::

    If installing from pip (or from source using ``setup.py install``), be
    advised that the ``yum-utils`` package is needed for Salt to manage
    packages. Also, if the Python dependencies are not already installed, then
    you will need additional libraries/tools installed to build some of them.
    More information on this can be found :ref:`here
    <installing-for-development>`.

Installation from EPEL
======================

Beginning with version 0.9.4, Salt has been available in `EPEL`_. It is
installable using yum. Salt should work properly with all mainstream
derivatives of RHEL, including CentOS, Scientific Linux, Oracle Linux and
Amazon Linux. Report any bugs or issues on the `issue tracker`__.

.. __: https://github.com/saltstack/salt/issues

On RHEL6, the proper Jinja package 'python-jinja2' was moved from EPEL to the
"RHEL Server Optional Channel". Verify this repository is enabled before
installing salt on RHEL6.

.. _`EPEL`: http://fedoraproject.org/wiki/EPEL


Enabling EPEL on RHEL
---------------------

If EPEL is not enabled on your system, you can use the following commands to
enable it.

For RHEL 5:

.. code-block:: bash

    rpm -Uvh http://mirror.pnl.gov/epel/5/i386/epel-release-5-4.noarch.rpm

For RHEL 6:

.. code-block:: bash

    rpm -Uvh http://ftp.linux.ncsu.edu/pub/epel/6/i386/epel-release-6-8.noarch.rpm


Installing Stable Release
-------------------------

Salt is packaged separately for the minion and the master. It is necessary only
to install the appropriate package for the role the machine will play.
Typically, there will be one master and multiple minions.

On the salt-master, run this:

.. code-block:: bash

    yum install salt-master

On each salt-minion, run this:

.. code-block:: bash

    yum install salt-minion

Installing from ``epel-testing``
--------------------------------

When a new Salt release is packaged, it is first admitted into the
``epel-testing`` repository, before being moved to the stable repo.

To install from ``epel-testing``, use the ``enablerepo`` argument for yum:

.. code-block:: bash

    yum --enablerepo=epel-testing install salt-minion


ZeroMQ 4
========

We recommend using ZeroMQ 4 where available. SaltStack provides ZeroMQ 4.0.4
and pyzmq 14.3.1 in a COPR_ repository. Instructions for adding this repository
(as well as for upgrading ZeroMQ and pyzmq on existing minions) can be found
here_.

.. _COPR: http://copr.fedoraproject.org/
.. _here: http://copr.fedoraproject.org/coprs/saltstack/zeromq4/

If this repo is added *before* Salt is installed, then installing either
``salt-master`` or ``salt-minion`` will automatically pull in ZeroMQ 4.0.4, and
additional states to upgrade ZeroMQ and pyzmq are unnecessary.

.. warning:: RHEL/CentOS 5 Users
    Using COPR repos on RHEL/CentOS 5 requires that the ``python-hashlib``
    package be installed. Not having it present will result in checksum errors
    because YUM will not be able to process the SHA256 checksums used by COPR.


Package Management
==================

Salt's interface to :mod:`yum <salt.modules.yumpkg>` makes heavy use of the
**repoquery** utility, from the yum-utils_ package. This package will be
installed as a dependency if salt is installed via EPEL. However, if salt has
been installed using pip, or a host is being managed using salt-ssh, then as of
version 2014.7.0 yum-utils_ will be installed automatically to satisfy this
dependency.

.. _yum-utils: http://yum.baseurl.org/wiki/YumUtils

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

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.