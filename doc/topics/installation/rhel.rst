.. _installation-rhel:

==============================================================
RHEL / CentOS / Scientific Linux / Amazon Linux / Oracle Linux
==============================================================

.. _installation-rhel-repo:

Salt should work properly with all mainstream derivatives of Red Hat Enterprise
Linux, including CentOS, Scientific Linux, Oracle Linux, and Amazon Linux.
Report any bugs or issues on the `issue tracker`__.

.. __: https://github.com/saltstack/salt/issues

Installation from the SaltStack Repository
==========================================

2015.5 and later packages for RHEL 5, 6, and 7 are available in the
SaltStack repository.

.. important::
  The repository folder structure changed in the 2015.8.3 release, though the
  previous repository structure that was documented in 2015.8.1 can continue to
  be used.

To install using the SaltStack repository:

#. Run one of the following commands based on your version to import the SaltStack repository key:

   Version 7:

   .. code-block:: bash

       rpm --import https://repo.saltstack.com/yum/redhat/7/x86_64/latest/SALTSTACK-GPG-KEY.pub

   Version 6:

   .. code-block:: bash

       rpm --import https://repo.saltstack.com/yum/redhat/6/x86_64/latest/SALTSTACK-GPG-KEY.pub

   Version 5:

   .. code-block:: bash

       wget https://repo.saltstack.com/yum/redhat/5/x86_64/latest/SALTSTACK-EL5-GPG-KEY.pub
       rpm --import SALTSTACK-EL5-GPG-KEY.pub
       rm -f SALTSTACK-EL5-GPG-KEY.pub

#. Save the following file to ``/etc/yum.repos.d/saltstack.repo``:

   Version 7 and 6:

   .. code-block:: cfg

       [saltstack-repo]
       name=SaltStack repo for RHEL/CentOS $releasever
       baseurl=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest
       enabled=1
       gpgcheck=1
       gpgkey=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest/SALTSTACK-GPG-KEY.pub

   Version 5:

   .. code-block:: cfg

       [saltstack-repo]
       name=SaltStack repo for RHEL/CentOS $releasever
       baseurl=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest
       enabled=1
       gpgcheck=1
       gpgkey=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest/SALTSTACK-EL5-GPG-KEY.pub

#. Run ``sudo yum clean expire-cache``.

#. Run ``sudo yum update``.

#. Install the salt-minion, salt-master, or other Salt components:

   - ``yum install salt-master``
   - ``yum install salt-minion``
   - ``yum install salt-ssh``
   - ``yum install salt-syndic``
   - ``yum install salt-cloud``

.. note::
    As of 2015.8.0, EPEL repository is no longer required for installing on
    RHEL systems. SaltStack repository provides all needed dependencies.

.. warning::
    If installing on Red Hat Enterprise Linux 7 with disabled (not subscribed on)
    'RHEL Server Releases' or 'RHEL Server Optional Channel' repositories,
    append CentOS 7 GPG key URL to SaltStack yum repository configuration to
    install required base packages:

    .. code-block:: cfg

       [saltstack-repo]
       name=SaltStack repo for Red Hat Enterprise Linux $releasever
       baseurl=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest
       enabled=1
       gpgcheck=1
       gpgkey=https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest/SALTSTACK-GPG-KEY.pub
              https://repo.saltstack.com/yum/redhat/$releasever/$basearch/latest/base/RPM-GPG-KEY-CentOS-7

.. note::
    ``systemd`` and ``python-systemd`` are required by Salt, but are not
    installed by the Red Hat 7 ``@base`` installation or by the Salt
    installation. These dependencies might need to be installed before Salt.

Installation from the Community Repository
==========================================

Beginning with version 0.9.4, Salt has been available in `EPEL`_. For
RHEL/CentOS 5, `Fedora COPR`_ is a single community repository that provides
Salt packages due to the removal from EPEL5.

.. note::
   Packages in these repositories are built by community, and it can
   take a little while until the latest stable SaltStack release become
   available.

.. _`EPEL`: http://fedoraproject.org/wiki/EPEL
.. _`Fedora COPR`: https://copr.fedorainfracloud.org/coprs/saltstack/salt-el5/

RHEL/CentOS 6 and 7, Scientific Linux, etc.
-------------------------------------------

.. warning::
    Salt 2015.8 is currently not available in EPEL due to unsatisfied
    dependencies: ``python-crypto`` 2.6.1 or higher, and ``python-tornado``
    version 4.2.1 or higher. These packages are not currently available in EPEL
    for Red Hat Enterprise Linux 6 and 7.

Enabling EPEL
*************

If the EPEL repository is not installed on your system, you can download the
RPM for `RHEL/CentOS 6`_ or for `RHEL/CentOS 7`_ and install it
using the following command:

.. code-block:: bash

    rpm -Uvh epel-release-X-Y.rpm

Replace ``epel-release-X-Y.rpm`` with the appropriate filename.

.. _RHEL/CentOS 6: http://download.fedoraproject.org/pub/epel/6/i386/repoview/epel-release.html
.. _RHEL/CentOS 7: http://download.fedoraproject.org/pub/epel/7/x86_64/repoview/epel-release.html

Installing Stable Release
*************************

Salt is packaged separately for the minion and the master. It is necessary
to install only the appropriate package for the role the machine will play.
Typically, there will be one master and multiple minions.

   - ``yum install salt-master``
   - ``yum install salt-minion``
   - ``yum install salt-ssh``
   - ``yum install salt-syndic``
   - ``yum install salt-cloud``

Installing from ``epel-testing``
********************************

When a new Salt release is packaged, it is first admitted into the
``epel-testing`` repository, before being moved to the stable EPEL repository.

To install from ``epel-testing``, use the ``enablerepo`` argument for ``yum``:

.. code-block:: bash

    yum --enablerepo=epel-testing install salt-minion

Installation Using pip
======================

Since Salt is on `PyPI`_, it can be installed using pip, though most users
prefer to install using RPM packages (which can be installed from `EPEL`_).

Installing from pip has a few additional requirements:

* Install the group 'Development Tools', ``yum groupinstall 'Development Tools'``
* Install the 'zeromq-devel' package if it fails on linking against that
  afterwards as well.

A pip install does not make the init scripts or the /etc/salt directory, and you
will need to provide your own systemd service unit.

Installation from pip:

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

ZeroMQ 4
========

We recommend using ZeroMQ 4 where available. SaltStack provides ZeroMQ 4.0.5
and pyzmq 14.5.0 in the :ref:`SaltStack Repository <installation-rhel-repo>`
as well as a separate `zeromq4 COPR`_ repository.

.. _`zeromq4 COPR`: http://copr.fedorainfracloud.org/coprs/saltstack/zeromq4/

If this repository is added *before* Salt is installed, then installing either
``salt-master`` or ``salt-minion`` will automatically pull in ZeroMQ 4.0.5, and
additional steps to upgrade ZeroMQ and pyzmq are unnecessary.

.. warning:: RHEL/CentOS 5 Users
    Using COPR repos on RHEL/CentOS 5 requires that the ``python-hashlib``
    package be installed. Not having it present will result in checksum errors
    because YUM will not be able to process the SHA256 checksums used by COPR.

.. note::
    For RHEL/CentOS 5 installations, if using the SaltStack repo or Fedora COPR
    to install Salt (as described :ref:`above <installation-rhel-repo>`),
    then it is not necessary to enable the `zeromq4 COPR`_, because those
    repositories already include ZeroMQ 4.

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

Master
------

To have the Master start automatically at boot time:

**RHEL/CentOS 5 and 6**

.. code-block:: bash

    chkconfig salt-master on

**RHEL/CentOS 7**

.. code-block:: bash

    systemctl enable salt-master.service

To start the Master:

**RHEL/CentOS 5 and 6**

.. code-block:: bash

    service salt-master start

**RHEL/CentOS 7**

.. code-block:: bash

    systemctl start salt-master.service

Minion
------

To have the Minion start automatically at boot time:

**RHEL/CentOS 5 and 6**

.. code-block:: bash

    chkconfig salt-minion on

**RHEL/CentOS 7**

.. code-block:: bash

    systemctl enable salt-minion.service

To start the Minion:

**RHEL/CentOS 5 and 6**

.. code-block:: bash

    service salt-minion start

**RHEL/CentOS 7**

.. code-block:: bash

    systemctl start salt-minion.service

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
