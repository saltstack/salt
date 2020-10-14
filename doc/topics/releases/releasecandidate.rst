:orphan:

.. _release-candidate:

===========================================
Installing/Testing a Salt Release Candidate
===========================================

When it's time for a new feature release of Salt, follow the instructions below to
install the latest release candidate of Salt, and try all the shiny new
features! Be sure to report any bugs you find on `Github
<https://github.com/saltstack/salt/issues/new/>`_.

Installing Using Packages
=========================

Builds for a few platforms are available as part of the RC at https://repo.saltstack.com/salt_rc/.
The builds should include the latest version of the OS that is currently available.

.. note::

    Follow the instructions on https://repo.saltstack.com/,
    but insert ``salt_rc/`` into the URL between the hostname
    and the remainder of the path.

    For Redhat Python 3

    .. code-block:: bash

        baseurl=https://repo.saltstack.com/salt_rc/py3/redhat/$releasever/$basearch/

    For Ubuntu Python 3 (replace os_version, with ubuntu version. For example 20.04)

    .. code-block:: none

        deb http://repo.saltstack.com/salt_rc/py3/ubuntu/<os_version>/amd64 focal main

    For Debian Python 3 (replace os_version, with debian version. For example 10)

    .. code-block:: none

        deb http://repo.saltstack.com/salt_rc/py3/debian/<os_version>/amd64 buster main

The OSs that will be built for each RC release are the latest version of each OS on https://repo.saltstack.com


.. FreeBSD

Installing Using Bootstrap
==========================

You can install a release candidate of Salt using `Salt Bootstrap
<https://github.com/saltstack/salt-bootstrap/>`_:

For example for the 3002rc1 release:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -x python3 git v3002rc1

If you want to also install a master using Salt Bootstrap, use the ``-M`` flag:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M -x python3 git v3002rc1

If you want to install only a master and not a minion using Salt Bootstrap, use
the ``-M`` and ``-N`` flags:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltstack.com
    sudo sh install_salt.sh -P -M -N -x python3 git v3002rc1

Installing Using PyPI
=====================

Installing from the source archive on `PyPI <https://pypi.org/>`_
is fairly straightforward.

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

    sudo pip install salt==$rc_tag_version

For example for the 3002rc1 release:

.. code-block:: bash

    sudo pip install salt==3002rc1
