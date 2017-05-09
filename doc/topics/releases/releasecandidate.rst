:orphan:

.. _release-candidate:

===========================================
Installing/Testing a Salt Release Candidate
===========================================

It's time for a new feature release of Salt! Follow the instructions below to
install the latest release candidate of Salt, and try :ref:`all the shiny new
features <release-2016-11-0>`! Be sure to report any bugs you find on `Github
<https://github.com/saltstack/salt/issues/new/>`_.

Installing Using Packages
=========================

Builds for a few platforms are available as part of the RC at https://repo.saltstack.com/salt_rc/.

.. note::

    For RHEL and Ubuntu, Follow the instructions on
    https://repo.saltstack.com/, but insert ``salt_rc/`` into the URL between
    the hostname and the remainder of the path.  For example:

    .. code-block:: bash

        baseurl=https://repo.saltstack.com/salt_rc/yum/redhat/$releasever/$basearch/

    .. code-block:: none

        deb http://repo.saltstack.com/salt_rc/apt/ubuntu/14.04/amd64 jessie main

Available builds:

- Amazon Linux
- Debian 8
- macOS
- RHEL 7
- SmartOS (see below)
- Ubuntu 16.04
- Windows

.. FreeBSD

SmartOS
-------
Release candidate builds for SmartOS are available at http://pkg.blackdot.be/extras/salt-2016.11rc/.

On a base64 2015Q4-x86_64 based native zone the package can be installed by the following:

.. code-block:: bash

    pfexec pkg_add -U https://pkg.blackdot.be/extras/salt-2016.11rc/salt-2016.11.0rc2_2015Q4_x86_64.tgz

When using the 2016Q2-tools release on the global zone by the following:

.. code-block:: bash

    pfexec pkg_add -U https://pkg.blackdot.be/extras/salt-2016.11rc/salt-2016.11.0rc2_2016Q2_TOOLS.tgz

Installing Using Bootstrap
==========================

You can install a release candidate of Salt using `Salt Bootstrap
<https://github.com/saltstack/salt-bootstrap/>`_:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P git v2016.11.0rc2

If you want to also install a master using Salt Bootstrap, use the ``-M`` flag:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M git v2016.11.0rc2

If you want to install only a master and not a minion using Salt Bootstrap, use
the ``-M`` and ``-N`` flags:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M -N git v2016.11.0rc2

Installing Using PyPI
=====================

Installing from the `source archive
<https://pypi.python.org/packages/7a/87/3b29ac215208bed9559d6c4df24175ddd1d52e62c5c00ae3afb3b7d9144d/salt-2016.11.0rc2.tar.gz>`_ on
`PyPI <https://pypi.python.org/pypi>`_ is fairly straightforward.

.. note::

    On RHEL derivatives you also need to install the ``epel-release`` package
    first.

    .. code-block:: bash

        sudo yum install epel-release

First install the build dependencies.

- Debian-based systems:

  .. code-block:: bash

      sudo apt-get install python-pip python-dev gcc g++

- RedHat-based systems:

  .. code-block:: bash

      sudo yum install python-pip python-devel gcc gcc-c++

- other systems:

  You will need to install:

  - pip
  - python header libraries
  - C and C++ compilers

Then install salt using the following command:

.. code-block:: bash

    sudo pip install salt==2016.11.0rc2
