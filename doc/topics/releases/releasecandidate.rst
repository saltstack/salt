:orphan:

===========================================
Installing/Testing a Salt Release Candidate
===========================================

It's time for a new feature release of Salt! Follow the instructions below to
install the latest release candidate of Salt, and try :doc:`all the shiny new
features </topics/releases/2016.3.0>`! Be sure to report any bugs you find on `Github
<https://github.com/saltstack/salt/issues/new/>`_.

Installing Using Packages
=========================

Builds for a few platforms are available as part of the RC here:
https://repo.saltstack.com/salt_rc/. For RHEL and Ubuntu, Follow the
instructions on https://repo.saltstack.com/, but prepend the URL paths with
``salt_rc/``.

Available builds:

- Windows
- Mac OS X
- RHEL 6
- RHEL 7
- Ubuntu 14.04

Installing Using Bootstrap
==========================

You can install a release candidate of Salt using `Salt Bootstrap
<https://github.com/saltstack/salt-bootstrap/>`_:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P git v2016.3.0rc2

If you want to also install a master using Salt Bootstrap, use the ``-M`` flag:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M git v2016.3.0rc2

If you want to install only a master and not a minion using Salt Bootstrap, use
the ``-M`` and ``-N`` flags:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M -N git v2016.3.0rc2

Installing Using PyPI
=====================

Installing from the `source archive
<https://pypi.python.org/packages/source/s/salt/salt-2016.3.0rc2.tar.gz>`_ on
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

    sudo pip install salt==2016.3.0rc2
