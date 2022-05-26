.. _installation-ubuntu:

======
Ubuntu
======

.. _installation-ubuntu-repo:

Installation from the Official SaltStack Repository
===================================================

Packages for Ubuntu 20.04 (Focal) and 18.04 (Bionic)
are available in the SaltStack repository.

Instructions are at https://repo.saltproject.io/#ubuntu.

.. note::
    Archived builds from unsupported branches:
    
    - `Archive 1 <https://archive.repo.saltproject.io/py3/ubuntu/>`__
    - `Archive 2 <https://archive.repo.saltproject.io/apt/ubuntu/>`__

    If looking to use archives, the same directions from the `Ubuntu install
    directions <https://repo.saltproject.io/#ubuntu>`__ can be used by replacing
    the URL paths with the appropriate archive location. The
    repository configuration endpoint also needs to be adjusted to point to the
    archives. Here is an example ``sed`` command:

    .. code-block:: bash

        # Salt repo configurations are found in the /etc/apt/sources.list.d/salt.list directory
        sed -i 's/repo.saltproject.io/archive.repo.saltproject.io/g' /etc/apt/sources.list.d/salt.list


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

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
