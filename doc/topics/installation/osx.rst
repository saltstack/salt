.. _macos-installation:

=====
macOS
=====

Installation from the Official SaltStack Repository
===================================================

**Latest stable build from the selected branch**:
|osxdownloadpy3|

The output of ``md5 <salt pkg>`` should match the contents of the
corresponding md5 file.

.. note::
    - `Earlier builds from supported branches
      <https://repo.saltstack.com/osx/>`__

    - `Archived builds from unsupported branches
      <https://archive.repo.saltstack.com/osx/>`__

Installation from Homebrew
==========================

.. code-block:: bash

    brew install saltstack

It should be noted that Homebrew explicitly discourages the `use of sudo`_:

    Homebrew is designed to work without using sudo. You can decide to use it but we strongly recommend not to do so. If you have used sudo and run into a bug then it is likely to be the cause. Please don’t file a bug report unless you can reproduce it after reinstalling Homebrew from scratch without using sudo

.. _use of sudo: https://github.com/Homebrew/homebrew/blob/master/share/doc/homebrew/FAQ.md#sudo

Installation from MacPorts
==========================

Macports isolates its dependencies from the OS, and installs salt in /opt/local by default, with config files under /opt/local/etc/salt. For best results, add /opt/local/bin to your PATH.

.. code-block:: bash

    sudo port install salt

Variants allow selection of python version used to run salt, defaulting to python27, but also supporting python34, python35, and python36. To install salt with Python 3.6, use the python36 variant, for example:

.. code-block:: bash

    sudo port install salt @python36

Startup items (for master, minion, and rest-cherrypy API gateway, respectively) are installed by subport targets. These will register launchd LaunchDaemons as org.macports.salt-minion, for example, to trigger automatic startup of the salt-minion through launchd. LaunchDaemons for salt can be started and stopped without reboot using the macprots load and unload commands.

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
    Salt master on macOS is not tested or supported by SaltStack. See `SaltStack Platform Support <https://saltstack.com/product-support-lifecycle/>`_ for more information.

To run salt-master on macOS, sudo add this configuration option to the /etc/salt/master file:

.. code-block:: bash

    max_open_files: 8192

On versions previous to macOS 10.10 (Yosemite), increase the root user maxfiles limit:

.. code-block:: bash

    sudo launchctl limit maxfiles 4096 8192

.. note::

    On macOS 10.10 (Yosemite) and higher, maxfiles should not be adjusted. The
    default limits are sufficient in all but the most extreme scenarios.
    Overriding these values with the setting below will cause system
    instability!

Now the salt-master should run without errors:

.. code-block:: bash

    sudo salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :ref:`Configuring Salt<configuring-salt>` page.

