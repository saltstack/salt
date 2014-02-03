====
OS X
====

Dependency Installation
-----------------------

When installing via Homebrew, dependency resolution is handled for you.

.. code-block:: bash

    brew install saltstack

When using macports, zmq, swig, and pip may need to be installed this way:

.. code-block:: bash

    sudo port install py-zmq
    sudo port install py27-m2crypto
    sudo port install py27-crypto
    sudo port install py27-msgpack
    sudo port install swig-python
    sudo port install py-pip

For installs using the OS X system python, pip install needs to use 'sudo':

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

    sudo /usr/local/share/python/salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
