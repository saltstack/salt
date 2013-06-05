====
OS X
====

Dependency Installation
-----------------------

ZeroMQ and swig need to be installed first.

Using homebrew:

.. code-block:: bash

    brew install swig
    brew install zmq

Using macports, zmq, swig, and pip may need to be installed this way:

.. code-block:: bash

    sudo port install py-zmq
    sudo port install py27-m2crypto
    sudo port install py27-crypto
    sudo port install py27-msgpack
    sudo port install swig-python
    sudo port install py-pip

For installs using the OSX system python, pip install needs to use 'sudo':

.. code-block:: bash

    sudo pip install salt

For installs using `python installed via homebrew`_, sudo should be unnecessary:

.. code-block:: bash

    pip install salt

.. _`python installed via homebrew`: https://github.com/mxcl/homebrew/wiki/Homebrew-and-Python

Salt-Master Customizations
--------------------------

To run salt-master on OSX, the root user maxfiles limit must be increased:

.. code-block:: bash

    sudo launchctl limit maxfiles 10000

And add this configuration option to the /etc/salt/master file:

.. code-block:: bash

    max_open_files: 10000

Now the salt-master should run without errors:

.. code-block:: bash

    sudo salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
