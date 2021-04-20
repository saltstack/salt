.. _installation-rhel:

==============================================================
RHEL / CentOS / Scientific Linux / Amazon Linux / Oracle Linux
==============================================================

.. _installation-rhel-repo:

Salt should work properly with all mainstream derivatives of Red Hat Enterprise
Linux, including CentOS, Scientific Linux, Oracle Linux, and Amazon Linux.
Report any bugs or issues on the `issue tracker 
<https://github.com/saltstack/salt/issues>`__.

Installation from the Official Salt Project Repository
======================================================

Packages for Redhat, CentOS, and Amazon Linux are available in
the Salt Project Repository.

- `Red Hat / CentOS <https://repo.saltproject.io/#rhel>`_
- `Amazon Linux <https://repo.saltproject.io/#amzn>`_

.. note::
    Archived builds from unsupported branches: 
    
    **Red Hat / CentOS**
    
    - `Archive 1 <https://archive.repo.saltproject.io/py3/redhat/>`__
    - `Archive 2 <https://archive.repo.saltproject.io/yum/redhat/>`__

    If looking to use archives, the same directions from the `RHEL/CentOS
    install directions <https://repo.saltproject.io/#rhel>`__ can be used by
    replacing the URL paths with the appropriate archive location. The
    repository configuration endpoint also needs to be adjusted to point to the
    archives. Here is an example ``sed`` command:

    .. code-block:: bash

        # Salt repo configurations are found in the /etc/yum.repos.d/ directory
        sed -i 's/repo.saltproject.io/archive.repo.saltproject.io/g' /etc/yum.repos.d/salt*.repo


    **Amazon Linux**

    - `Archive 1 <https://archive.repo.saltproject.io/py3/amazon/>`__
    - `Archive 2 <https://archive.repo.saltproject.io/yum/amazon/>`__

    If looking to use archives, the same directions from the `Amazon
    install directions <https://repo.saltproject.io/#amzn>`__ can be used by
    replacing the URL paths with the appropriate archive location. The
    repository configuration endpoint also needs to be adjusted to point to the
    archives. Here is an example ``sed`` command:

    .. code-block:: bash

        # Salt repo configurations are found in the /etc/yum.repos.d/ directory
        sed -i 's/repo.saltproject.io/archive.repo.saltproject.io/g' /etc/yum.repos.d/salt*.repo

.. note::
    As of 2015.8.0, EPEL repository is no longer required for installing on
    RHEL systems. Salt Project repository provides all needed dependencies.

.. warning::
    If installing on Red Hat Enterprise Linux 7 with disabled (not subscribed on)
    'RHEL Server Releases' or 'RHEL Server Optional Channel' repositories,
    append CentOS 7 GPG key URL to Salt Project yum repository configuration to
    install required base packages:

    .. code-block:: cfg

       [saltstack-repo]
       name=Salt repo for Red Hat Enterprise Linux $releasever
       baseurl=https://repo.saltproject.io/py3/redhat/$releasever/$basearch/latest
       enabled=1
       gpgcheck=1
       gpgkey=https://repo.saltproject.io/py3/redhat/$releasever/$basearch/latest/SALTSTACK-GPG-KEY.pub
              https://repo.saltproject.io/py3/redhat/$releasever/$basearch/latest/base/RPM-GPG-KEY-CentOS-7

.. note::
    ``systemd`` and ``systemd-python`` are required by Salt, but are not
    installed by the Red Hat 7 ``@base`` installation or by the Salt
    installation. These dependencies might need to be installed before Salt.

Installation Using pip
======================

Since Salt is on `PyPI`_, it can be installed using pip, though most users
prefer to install using RPM packages (which can be installed by following
the directions in the :ref:`Salt Repository <installation-rhel-repo>`).

Installing from pip has a few additional requirements:

* Install the group 'Development Tools', ``yum groupinstall 'Development Tools'``
* Install the 'zeromq-devel' package if it fails on linking against that
  afterwards as well.

A pip install does not make the init scripts or the /etc/salt directory, and you
will need to provide your own systemd service unit.

Installation from pip:

.. _`PyPI`: https://pypi.org/project/salt/

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

We recommend using ZeroMQ 4 where available. Salt Project provides ZeroMQ 4.3.1
and ``pyzmq`` 17.0.0 in the :ref:`Salt Repository
<installation-rhel-repo>`.

If this repository is added *before* Salt is installed, then installing either
``salt-master`` or ``salt-minion`` will automatically pull in ZeroMQ 4.3.1, and
additional steps to upgrade ZeroMQ and pyzmq are unnecessary.

Package Management
==================

Salt's interface to :mod:`yum <salt.modules.yumpkg>` makes heavy use of the
**repoquery** utility, from the yum-utils_ package. If salt has
been installed using pip, or a host is being managed using salt-ssh, then as of
version 2014.7.0 yum-utils_ will be installed automatically to satisfy this
dependency.

.. _yum-utils: http://yum.baseurl.org/wiki/YumUtils

Post-installation tasks
=======================

Master
------

To have the Master start automatically at boot time:

**RHEL/CentOS 7 and 8**

.. code-block:: bash

    systemctl enable salt-master.service

To start the Master:

**RHEL/CentOS 7 and 8**

.. code-block:: bash

    systemctl start salt-master.service

Minion
------

To have the Minion start automatically at boot time:

**RHEL/CentOS 7 and 8**

.. code-block:: bash

    systemctl enable salt-minion.service

To start the Minion:

**RHEL/CentOS 7 and 8**

.. code-block:: bash

    systemctl start salt-minion.service

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
