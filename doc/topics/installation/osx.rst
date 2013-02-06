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

Using macports, you may need to install zmq and swig this way:

.. code-block:: bash

    sudo port install pyzmq
    sudo port install py27-m2crypto
    sudo port install py27-crypto
    sudo port install py27-msgpack
    sudo port install python-swig

Now if you are using the OSX system python, you'll need to pip install using 'sudo':

.. code-block:: bash

    sudo pip install salt

If you have `python installed via homebrew`_, you shouldn't need sudo:

.. code-block:: bash

    pip install salt

.. _`python installed via homebrew`: https://github.com/mxcl/homebrew/wiki/Homebrew-and-Python

Salt-Master Customizations
--------------------------

If you want to run salt-master on OSX, you need to change the maxfiles limit for the root user:

.. code-block:: bash

    sudo launchctl limit maxfiles 100000

Now you should be able to run the salt-master without errors:

.. code-block:: bash

    sudo salt-master --log-level=all

Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
