.. _docker-sls:

=====================================================
Running Salt States and Commands in Docker Containers
=====================================================

The 2016.11.0 release of Salt introduces the ability to execute Salt States
and Salt remote execution commands directly inside of Docker containers.

This addition makes it possible to not only deploy fresh containers using
Salt States. This also allows for running containers to be audited and
modified using Salt, but without running a Salt Minion inside the container.
Some of the applications include security audits of running containers as
well as gathering operating data from containers.

This new feature is simple and straightforward, and can be used via a running
Salt Minion, the Salt Call command, or via Salt SSH. For this tutorial we will
use the `salt-call` command, but like all salt commands these calls are
directly translatable to `salt` and `salt-ssh`.

Step 1 - Install Docker
=======================

Since setting up Docker is well covered in the Docker documentation we will
make no such effort to describe it here. Please see the Docker Installation
Documentation for installing and setting up Docker:
https://docs.docker.com/engine/installation/

The Docker integration also requires that the `docker-py` library is installed.
This can easily be done using pip or via your system package manager:

.. code-block:: bash

    pip install docker-py

Step 2 - Install Salt
=====================

For this tutorial we will be using Salt Call, which is available in the
`salt-minion` package, please follow the
`Salt install guide <https://docs.saltproject.io/salt/install-guide/en/latest/>`_.

Step 3 - Create With Salt States
================================

Next some Salt States are needed, for this example a very basic state which
installs `vim` is used, but anything Salt States can do can be done here,
please see the Salt States Introduction Tutorial to learn more about Salt
States:
https://docs.saltproject.io/en/stage/getstarted/config/

For this tutorial, simply create a small state file in `/srv/salt/vim.sls`:

.. code-block:: yaml

    vim:
      pkg.installed

.. note::

    The base image you choose will need to have python 2.6 or 2.7 installed.
    We are hoping to resolve this constraint in a future release.

    If `base` is omitted the default image used is a minimal openSUSE
    image with Python support, maintained by SUSE

Next run the `docker.sls_build` command:

.. code-block:: bash

    salt-call --local dockerng.sls_build test base=my_base_image mods=vim

Now we have a fresh image called `test` to work with and vim has been
installed.

Step 4 - Running Commands Inside the Container
==============================================

Salt can now run remote execution functions inside the container with another
simple `salt-call` command:

.. code-block:: bash

    salt-call --local dockerng.call test test.version
    salt-call --local dockerng.call test network.interfaces
    salt-call --local dockerng.call test disk.usage
    salt-call --local dockerng.call test pkg.list_pkgs
    salt-call --local dockerng.call test service.running httpd
    salt-call --local dockerng.call test cmd.run 'ls -l /etc'
