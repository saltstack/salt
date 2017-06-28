==========
Arch Linux
==========

Installation
============

Salt (stable) is currently available via the Arch Linux Official repositories.
There are currently -git packages available in the Arch User repositories (AUR)
as well.

Stable Release
--------------

Install Salt stable releases from the Arch Linux Official repositories as follows:

.. code-block:: bash

    pacman -S salt

Tracking develop
----------------

To install the bleeding edge version of Salt (**may include bugs!**),
use the -git package. Installing the -git package as follows:

.. code-block:: bash

    wget https://aur.archlinux.org/packages/sa/salt-git/salt-git.tar.gz
    tar xf salt-git.tar.gz
    cd salt-git/
    makepkg -is

.. note:: yaourt

    If a tool such as Yaourt_ is used, the dependencies will be
    gathered and built automatically.

    The command to install salt using the yaourt tool is:

    .. code-block:: bash

        yaourt salt-git

.. _Yaourt: https://aur.archlinux.org/packages.php?ID=5863

Post-installation tasks
=======================

**systemd**

Activate the Salt Master and/or Minion via ``systemctl`` as follows:

.. code-block:: bash

    systemctl enable salt-master.service
    systemctl enable salt-minion.service

**Start the Master**

Once you've completed all of these steps you're ready to start your Salt
Master. You should be able to start your Salt Master now using the command
seen here:

.. code-block:: bash

    systemctl start salt-master

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
