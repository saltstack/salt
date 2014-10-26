====
OS X
====

Dependency Installation
-----------------------

When using Homebrew, install this way:

.. code-block:: bash

    sudo brew install saltstack

When using MacPorts, install this way:

.. code-block:: bash

    sudo port install salt
    
When only using the OS X system's pip, install this way:

.. code-block:: bash

    sudo pip install salt

Salt-Master Customizations
--------------------------

To run salt-master on OS X, the root user maxfiles limit must be increased:

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
