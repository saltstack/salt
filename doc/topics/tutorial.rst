========
Tutorial
========

Setting up Salt
===============

The Salt system setup is amazingly simple, as this is one of the central design
goals of Salt. Setting up Salt only requires that the salt master be running
and the salt minions point to the salt master.

Installing Salt
---------------

As of this writing packages for Salt only exist for Arch Linux, but rpms and
debs will be available in the future (contributions welcome).

Installing from the source tarball
``````````````````````````````````

Download the latest source tarball from the GitHub downloads directory for the
Salt project:

https://github.com/thatch45/salt/downloads

Next, untar the tarball and run the :file:`setup.py` as root:

.. code-block:: bash

    tar xvf salt-<version>.tar.gz
    cd salt-<version>
    python2 setup.py install

Salt dependencies
+++++++++++++++++

This is a basic Python setup, nothing fancy. Salt does require a number of
dependencies though, all of which should be available in your distribution's
packages.

* `Python 2.6`_
* `pyzmq`_ - ZeroMQ Python bindings
* `M2Crypto`_ - Python OpenSSL wrapper
* `YAML`_ - Python YAML bindings
* `PyCrypto`_ - The Python cryptography toolkit

.. _`Python 2.6`: http://python.org/download/
.. _`pyzmq`: https://github.com/zeromq/pyzmq
.. _`M2Crypto`: http://chandlerproject.org/Projects/MeTooCrypto
.. _`YAML`: http://pyyaml.org/
.. _`PyCrypto`: http://www.dlitz.net/software/pycrypto/

Optional Dependencies:

* gcc - dynamic `Cython`_ module compiling

.. _`Cython`: http://cython.org/

Installing from Arch Linux packages
```````````````````````````````````

The Arch Linux Salt package is available in the Arch Linux AUR (if you like
Salt vote for it on the Arch Linux AUR):

https://aur.archlinux.org/packages.php?ID=47512

For help using packages in the Arch Linux AUR:

https://wiki.archlinux.org/index.php/AUR

Simple configuration
--------------------

.. glossary::

    master
        Some stuff

    minion
        Other stuff

The Salt configuration is very simple, the only requirement for setting up a
salt master and minion is to set the location of the master in the minion
configuration file. The configuration files will be installed to ``/etc/salt``
and are named after the respective components:

* :file:`/etc/salt/master` - The salt-master configuration
* :file:`/etc/salt/minion` - The salt minion configuration

To make a minion check into the correct master simply edit the master variable
in the minion configuration file to reference the master dns name or ipv4
address.

.. seealso::

    For further information consult the :doc:`configuration guide
    <../ref/configuration/index>`.

Running Salt
------------

To run Salt you need to ensure that a master and a minion are running and
referencing each other. Starting the master and minion daemons is done with the
respective commands:

To run the master as a daemon:

.. code-block:: bash

    salt-master -d

To run the master in the foreground:

.. code-block:: bash

    salt-master

To run the minion as a daemon:

.. code-block:: bash

    salt-minion -d

To run the minion in the foreground:

.. code-block:: bash

    salt-minion

Init scripts are available for Arch Linux:

.. code-block:: bash

    /etc/rc.d/salt-master start
    /etc/rc.d/salt-minion start

Manage Salt Public Keys
-----------------------

Salt manages authentication with RSA public keys. The keys are managed on the
salt master via the :command:`saltkey` command. Once a salt minion checks into
the salt master the salt master will save a copy of the minion key. Before the
master can send commands to the minion the key needs to be "accepted". This is
done with the :command:`saltkey` command. :command:`saltkey` can also be used
to list all of the minions that have checked into the master.

List the accepted and unaccepted salt keys:

.. code-block:: bash

    saltkey -L

Accept a minion key:

.. code-block:: bash

    saltkey -a <minion id>

Accept all unaccepted minion keys:

.. code-block:: bash

    saltkey -A

Saltkey can also print out the contents of the minion keys so that they can be
verified:

.. code-block:: bash

    saltkey -p <minion id>

Once some of the minions are communicating with the master you can move on to
using the :command:`salt` command to execute commands on the minions.
