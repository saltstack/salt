====
OS X
====

Dependency Installation
-----------------------

It should be noted that Homebrew explicitly discourages the `use of sudo`_:

    Homebrew is designed to work without using sudo. You can decide to use it but we strongly recommend not to do so. If you have used sudo and run into a bug then it is likely to be the cause. Please don’t file a bug report unless you can reproduce it after reinstalling Homebrew from scratch without using sudo

So when using Homebrew, if you want support from the Homebrew community, install this way:

.. code-block:: bash

    brew install saltstack

.. _use of sudo: https://github.com/Homebrew/homebrew/blob/master/share/doc/homebrew/FAQ.md#sudo



When using MacPorts, install this way:

.. code-block:: bash

    sudo port install salt

When only using the OS X system's pip, install this way:

.. code-block:: bash

    sudo pip install salt

Salt-Master Customizations
--------------------------

To run salt-master on OS X, the root user maxfiles limit must be increased:

.. note::

    On OS X 10.10 (Yosemite) and higher, maxfiles should not be adjusted. The
    default limits are sufficient in all but the most extreme scenarios.
    Overriding these values with the setting below will cause system
    instability!

.. code-block:: bash

    sudo launchctl limit maxfiles 4096 8192

And sudo add this configuration option to the /etc/salt/master file:

.. code-block:: bash

    max_open_files: 8192

Now the salt-master should run without errors:

.. code-block:: bash

    sudo salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</ref/configuration/index>` page.
