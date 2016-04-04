.. _installation-ubuntu:

======
Ubuntu
======

.. _installation-ubuntu-repo:

Installation from the SaltStack Repository
==========================================

2015.5 and later packages for Ubuntu 14 (Trusty) and Ubuntu 12 (Precise) are
available in the SaltStack repository.

.. note::
    While Salt packages are built for all Ubuntu supported CPU architectures
    (``i386`` and ``amd64``), some of the dependencies avaivable from SaltStack
    corporate repository are only suitable for ``amd64`` systems.

.. important::
    The repository folder structure changed in the 2015.8.3 release, though the
    previous repository structure that was documented in 2015.8.1 can continue to
    be used.

To install using the SaltStack repository:

#. Run the following command to import the SaltStack repository key:

   Ubuntu 14:

   .. code-block:: bash

       wget -O - https://repo.saltstack.com/apt/ubuntu/14.04/amd64/latest/SALTSTACK-GPG-KEY.pub | sudo apt-key add -

   Ubuntu 12:

   .. code-block:: bash

       wget -O - https://repo.saltstack.com/apt/ubuntu/12.04/amd64/latest/SALTSTACK-GPG-KEY.pub | sudo apt-key add -

#. Add the following line to ``/etc/apt/sources.list``:

   Ubuntu 14:

   .. code-block:: bash

       deb http://repo.saltstack.com/apt/ubuntu/14.04/amd64/latest trusty main

   Ubuntu 12:

   .. code-block:: bash

       deb http://repo.saltstack.com/apt/ubuntu/12.04/amd64/latest precise main

#. Run ``sudo apt-get update``.

#. Now go to the :ref:`packages installation <ubuntu-install-pkgs>` section.

Installation from the Community Repository
==========================================

Packages for Ubuntu are also published in the saltstack PPA. If you have
the ``add-apt-repository`` utility, you can add the repository and import the
key in one step:

.. code-block:: bash

    sudo add-apt-repository ppa:saltstack/salt

In addition to the main repository, there are secondary repositories for each
individual major release. These repositories receive security and point
releases but will not upgrade to any subsequent major release.  There are
currently several available repos: salt16, salt17, salt2014-1, salt2014-7,
salt2015-5. For example to follow 2015.5.x releases:

.. code-block:: bash

    sudo add-apt-repository ppa:saltstack/salt2015-5

.. admonition:: add-apt-repository: command not found?

    The ``add-apt-repository`` command is not always present on Ubuntu systems.
    This can be fixed by installing `python-software-properties`:

    .. code-block:: bash

        sudo apt-get install python-software-properties

    The following may be required as well:

    .. code-block:: bash

        sudo apt-get install software-properties-common

    Note that since Ubuntu 12.10 (Raring Ringtail), ``add-apt-repository`` is
    found in the `software-properties-common` package, and is part of the base
    install. Thus, ``add-apt-repository`` should be able to be used
    out-of-the-box to add the PPA.

Alternately, manually add the repository and import the PPA key with these
commands:

.. code-block:: bash

    echo deb http://ppa.launchpad.net/saltstack/salt/ubuntu `lsb_release -sc` main | sudo tee /etc/apt/sources.list.d/saltstack.list
    wget -q -O- "http://keyserver.ubuntu.com:11371/pks/lookup?op=get&search=0x4759FA960E27C0A6" | sudo apt-key add -

After adding the repository, update the package management database:

.. code-block:: bash

    sudo apt-get update

.. _ubuntu-install-pkgs:

Install Packages
================

Install the Salt master, minion or other packages from the repository with
the `apt-get` command. These examples each install one of Salt components, but
more than one package name may be given at a time:

- ``apt-get install salt-api``
- ``apt-get install salt-cloud``
- ``apt-get install salt-master``
- ``apt-get install salt-minion``
- ``apt-get install salt-ssh``
- ``apt-get install salt-syndic``

.. _ubuntu-config:

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
