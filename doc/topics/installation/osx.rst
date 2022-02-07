.. _macos-installation:

=====
macOS
=====

Installation from the Official SaltStack Repository
===================================================

**Latest stable build from the selected branch**: |osxdownloadpy3|

The output of ``md5 <salt pkg>`` should match the contents of the corresponding
md5 file.

.. note::

    - `Earlier builds from supported branches
      <https://repo.saltproject.io/osx/>`__

    - `Archived builds from unsupported branches
      <https://archive.repo.saltproject.io/osx/>`__

To install Salt using the package, download and double-click the downloaded
file. Follow the instructions in the installer.

Configuration
-------------

salt-config cli tool
^^^^^^^^^^^^^^^^^^^^

The Salt Package includes the ``salt-config.sh`` script for configuring Salt
after it has been installed. The script is located in the ``/opt/salt/bin``
directory. A symlink to that file is created in ``/usr/local/sbin``. If
``/usr/local/sbin`` is part of the path you can type the following in a bash
shell to get config options.

.. code-block:: bash

    salt-config --help

.. note::

    If ``/usr/local/sbin`` is not in the path, you can either add it to the
    path, or navigate to ``/usr/local/sbin`` or ``/opt/salt/bin`` to run the
    ``salt-config`` script.

There are two configuration options that allow you to set the master and minion
ID. They are as follows:

===============  =====================================
Option           Description
===============  =====================================
-i, --minion-id  The ID to assign this minion
-m, --master     The hostname/IP address of the master
-h, --help       Display this help message
===============  =====================================

To set the master and minion ID after installation, run the following command:

.. code-block:: bash

    sudo salt-config -i mac_minion -m master.apple.com
    sudo salt-config --minion-id mac_minion --master 10.10.1.10

sample configs
^^^^^^^^^^^^^^

The installer places sample config files in the ``/etc/salt`` directory named
``master.dist`` and ``minion.dist``. You can make a copy of one of these files,
remove the ``.dist`` file extension, and edit as you see fit. Restart the minion
or master service to pick up the changes.

Detailed configuration options can be found at:

    - `Configuring the Salt minion
      <https://docs.saltproject.io/en/latest/ref/configuration/minion.html>`__

    - `Configuring the Salt master
      <https://docs.saltproject.io/en/latest/ref/configuration/master.html>`__

Installation from Homebrew
==========================

.. code-block:: bash

    brew install saltstack

It should be noted that Homebrew explicitly discourages the `use of sudo`_:

    Homebrew is designed to work without using sudo. You can decide to use it
    but we strongly recommend not to do so. If you have used sudo and run into a
    bug then it is likely to be the cause. Please don't file a bug report unless
    you can reproduce it after reinstalling Homebrew from scratch without using
    sudo

.. _use of sudo: https://docs.brew.sh/FAQ#why-does-homebrew-say-sudo-is-bad

Installation from MacPorts
==========================

Macports isolates its dependencies from the OS, and installs Salt in
``/opt/local`` by default, with config files under ``/opt/local/etc/salt``. For
best results, add ``/opt/local/bin`` to your PATH.

.. code-block:: bash

    sudo port install salt

Variants allow selection of the python version used to run Salt. Supported
versions are python35, python36, python37, and python38. To install Salt
with Python 3.6, use the python36 variant, for example:

.. code-block:: bash

    sudo port install salt @python36

Startup items (for master, minion, and rest-cherrypy API gateway, respectively)
are installed by subport targets. These will register launchd LaunchDaemons as
org.macports.salt-minion, for example, to trigger automatic startup of the
salt-minion through launchd. LaunchDaemons for Salt can be started and stopped
without reboot using the macprots load and unload commands.

.. code-block:: bash

    sudo port install salt-master salt-minion salt-api
    sudo port load salt-master salt-minion salt-api

Installation from Pip
=====================

When only using the macOS system's pip, install this way:

.. code-block:: bash

    sudo pip install salt

Salt-Master Customizations
==========================

.. note::

    Salt master on macOS is not tested or supported by SaltStack. See
    `SaltStack Platform Support <https://saltstack.com/product-support-lifecycle/>`_
    for more information.

To run salt-master on macOS, add this configuration option to the
``/etc/salt/master`` file:

.. code-block:: bash

    max_open_files: 8192

Now the salt-master should run without errors:

.. code-block:: bash

    sudo salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :ref:`Configuring Salt<configuring-salt>` page.
