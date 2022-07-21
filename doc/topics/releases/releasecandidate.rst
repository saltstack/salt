:orphan:

.. _release-candidate:

=====================================
Install/Test a Salt Release Candidate
=====================================

When it's time for a new feature release of Salt, follow the instructions below to
install the latest release candidate of Salt, and try all the shiny new
features! Be sure to report any bugs you find on `Github
<https://github.com/saltstack/salt/issues/new/>`_.


Install using packages
======================
Builds for a few platforms are available as part of the RC at:
https://repo.saltproject.io/salt_rc/

The builds include the latest version of the operating system that is currently
available. Older versions of operating systems will not get an RC release.

.. note::

   Beginning with the 3005 (Phosphorus) release of Salt, the Salt Project is
   changing its packaging system to Tiamat. Any new operating systems added in 3005
   will only have Tiamat packages. The Salt Project will phase out the old Salt
   package builds for currently supported operating systems by 3007. See
   `What is Tiamat? <https://docs.saltproject.io/salt/install-guide/en/latest/topics/upgrade-to-tiamat.html#what-is-tiamat>`_
   for more information.

To install release candidate packages:

Follow the instructions for your operating system on https://repo.saltproject.io/,
but insert ``salt_rc/`` into the URL between the hostname and the remainder
of the file path.


Tiamat packages
---------------
For RedHat, replace the ``<salt version & release number>`` variable with the
Salt version and release:

.. code-block:: bash

    sudo rpm --import https://repo.saltproject.io/salt/py3/redhat/9/x86_64/minor/<salt version>/SALTSTACK-GPG-KEY2.pub
    baseurl=https://repo.saltproject.io/salt_rc/salt/py3/redhat/$releasever/$basearch/minor/<salt version and release number>

For example, for the 3005 release of RC 1-2:

.. code-block:: bash

    sudo rpm --import https://repo.saltproject.io/salt/py3/redhat/9/x86_64/latest/3005/SALTSTACK-GPG-KEY2.pub
    baseurl=https://repo.saltproject.io/salt_rc/salt/py3/redhat/$releasever/$basearch/minor/3005rc1-2

For Ubuntu, replace:

* The ``<os_version>`` variable with number of the Ubuntu version
* The ``<codename>`` variable for the Ubuntu release codename
* The ``<salt version & release number>`` variable with the Salt version and
  release

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/salt/py3/ubuntu/<os_version>/amd64/minor/<salt version and release number> <codename> main

For example, for the 22.04 release of Ubuntu, codename Jammy Jellyfish and the
3005 release of RC 1-2:

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/salt/py3/ubuntu/22.04/amd64/minor/3005rc1-2 jammy main


For Debian, the syntax is identical to Ubuntu. For example, for the version 10
(Buster) release:

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/salt/py3/debian/10/amd64/minor/3005rc1-2 buster main



Classic packages
----------------
For RedHat:

.. code-block:: bash

    baseurl=https://repo.saltproject.io/salt_rc/py3/redhat/$releasever/$basearch/

For Ubuntu, replace the ``<os_version>`` variable with number of the Ubuntu
version and ``<codename>`` for the release codename.

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/py3/ubuntu/<os_version>/amd64 <codename> main

For example, for the 20.04 release of Ubuntu, codename Focal Fosse:

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/py3/ubuntu/20.04/amd64 focal main


For Debian, the syntax is identical to Ubuntu. For example, for the version 10
(Buster) release:

.. code-block:: none

    deb https://repo.saltproject.io/salt_rc/py3/debian/10/amd64 buster main



.. FreeBSD

Install using bootstrap
=======================
You can install a release candidate of Salt using `Salt Bootstrap
<https://github.com/saltstack/salt-bootstrap/>`_:

For example for the 3003rc1 release:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltproject.io
    sudo sh install_salt.sh -P -x python3 git v3003rc1

If you want to also install a master using Salt Bootstrap, use the ``-M`` flag:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltproject.io
    sudo sh install_salt.sh -P -M -x python3 git v3003rc1

If you want to install only a master and not a minion using Salt Bootstrap, use
the ``-M`` and ``-N`` flags:

.. code-block:: bash

    curl -o install_salt.sh -L https://bootstrap.saltproject.io
    sudo sh install_salt.sh -P -M -N -x python3 git v3003rc1


Install using PyPI
==================
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

For example for the 3005rc1 release:

.. code-block:: bash

    sudo pip install salt==3005rc1
