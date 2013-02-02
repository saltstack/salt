====
OS X
====

Now go to the :doc:`Configuring Salt</topics/configuration>` page.

Dependency installation
-----------------------

There are many ways to skin the dependency cat. One solution that I found
simple enough was to install two key packages with the fine homebrew package
manager:


.. code-block:: bash

    brew install swig
    brew install zmq

and then install the python dependencies as follows:


.. code-block:: bash

    pip install M2Crypto pyzmq PyYAML pycrypto msgpack-python jinja2 psutil


Post-installation tasks
=======================

Now go to the :doc:`Configuring Salt</topics/configuration>` page.
