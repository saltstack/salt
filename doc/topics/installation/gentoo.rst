======
Gentoo
======

Salt can be easily installed on Gentoo:

.. code-block:: bash

    emerge pyyaml m2crypto pycrypto jinja pyzmq

Then download and install from source:

1.  Download the latest source tarball from the `GitHub downloads`_ directory for
    the Salt project.

2.  Untar the tarball and run the ``setup.py`` as root:

.. code-block:: bash

    tar xf salt-<version>.tar.gz
    cd salt-<version>
    python setup.py install

.. _GitHub downloads: https://github.com/saltstack/salt/downloads
