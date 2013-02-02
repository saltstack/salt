====
OS X
====

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

Dependency installation
-----------------------

ZeroMQ and swig need to be installed first, these are avilable via homebrew:


.. code-block:: bash

    brew install swig
    brew install zmq

Now pip can install the remaining deps and salt itself:


.. code-block:: bash

    pip install M2Crypto pyzmq PyYAML pycrypto msgpack-python jinja2 psutil salt


Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
