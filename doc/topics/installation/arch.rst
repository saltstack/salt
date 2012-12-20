==========
Arch Linux
==========

Installation
============

Salt is currently available via the Arch User Repository (AUR). There are
currently stable and -git packages available.

Stable Release
--------------

Install Salt stable releases from the Arch Linux AUR as follows:

.. code-block:: bash

    wget https://aur.archlinux.org/packages/sa/salt/salt.tar.gz
    tar xf salt.tar.gz
    cd salt/
    makepkg -is

A few of Salt's dependencies are currently only found within the AUR, so it is
necessary to download and run ``makepkg -is`` on these as well. As a reference, Salt
currently relies on the following packages which are only available via the AUR:

* https://aur.archlinux.org/packages/py/python2-msgpack/python2-msgpack.tar.gz
* https://aur.archlinux.org/packages/py/python2-psutil/python2-psutil.tar.gz

.. note:: yaourt

    If a tool such as Yaourt_ is used, the dependencies will be
    gathered and built automatically.

    The command to install salt using the yaourt tool is:

    .. code-block:: bash

        yaourt salt

.. _Yaourt: https://aur.archlinux.org/packages.php?ID=5863

Tracking develop
----------------

To install the bleeding edge version of Salt (**may include bugs!**),
use the -git package. Installing the -git package as follows:

.. code-block:: bash

    wget https://aur.archlinux.org/packages/sa/salt-git/salt-git.tar.gz
    tar xf salt-git.tar.gz
    cd salt-git/
    makepkg -is

See the note above about Salt's dependencies.

Post-installation tasks
=======================

**Configuration files**

The Salt package installs two template configuration files,
``/etc/salt/master.template`` and ``/etc/salt/minion.template``. These
files need to be copied as follows:

.. code-block:: bash

   cp /etc/salt/master.template /etc/salt/master
   cp /etc/salt/minion.template /etc/salt/minion

Note: only the configuration files for the services to be run need be
copied.

**rc.conf**

Activate the Salt Master and/or Minion in ``/etc/rc.conf`` as follows:

.. code-block:: diff

    -DAEMONS=(syslog-ng network crond)
    +DAEMONS=(syslog-ng network crond @salt-master @salt-minion)

**Start the Master**

Once you've completed all of these steps you're ready to start your Salt
Master. You should be able to start your Salt Master now using the command
seen here:

.. code-block:: bash

    rc.d start salt-master

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

