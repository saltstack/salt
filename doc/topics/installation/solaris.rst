=======
Solaris
=======

Salt was added to the OpenCSW package repository in September of 2012 by Romeo Theriault <romeot@hawaii.edu> at version 0.10.2 of Salt. It has mainly been tested on Solaris 10 (sparc), though it is built for, and should work fine on Solaris 10 (x86), Solaris 9 (sparc/x86) and 11 (sparc/x86) also. Most of the testing has also just focused on the minion, though it has verified that the master starts up successfully on Solaris 10.

Comments and patches for better support on these platforms is very welcome. Currently at version 0.10.2 of salt, grain detection is weak but patches that very much improve the grain detection will be released in 0.10.3. Work is also underway to include support for services and packages in Solaris.

Salt is dependent on the following additional packages. These will automatically be installed as
dependencies of the ``py_salt`` package. ::

   py_yaml
   py_pyzmq
   py_jinja2
   py_msgpack_python
   py_m2crypto
   py_crypto
   python

Installation
============

To install Salt from the OpenCSW package repository you first need to install `pkgutil`_ assuming you don't already have it installed:

On Solaris 10:

.. code-block:: bash

   pkgadd -d http://get.opencsw.org/now

On Solaris 9:

.. code-block:: bash

   wget http://mirror.opencsw.org/opencsw/pkgutil.pkg
   pkgadd -d pkgutil.pkg all

Once pkgutil is installed you'll need to edit it's config file ``/etc/opt/csw/pkgutil.conf`` to point it at the unstable catalog:

.. code-block:: diff

   - #mirror=http://mirror.opencsw.org/opencsw/testing
   + mirror=http://mirror.opencsw.org/opencsw/unstable

Ok, time to install salt.

.. code-block:: bash

   # Update the catalog
   root> /opt/csw/bin/pkgutil -U
   # Install salt
   root> /opt/csw/bin/pkgutil -i -y py_salt

Minion Configuration
=============

Now that salt is installed you can find it's configuration files in:

``/etc/opt/csw/salt/``

You'll want to edit the minion config file to set the name of your salt master server:

.. code-block:: diff

    - #master: salt
    + master: your-salt-server

You can now start the salt minion like so:

On Solaris 10:

.. code-block:: bash

    svcadm enable salt-minion


On Solaris 9:

.. code-block:: bash

    /etc/init.d/salt-minion start

You should now be able to log onto the salt master and check to see if the salt-minion key is awaiting acceptance:

.. code-block:: bash

   salt-key -l un
 
Accept the key:

.. code-block:: bash

    salt-key -a <your-salt-minion>

Run a simple test against the minion:

.. code-block:: bash

    salt '<your-salt-minion>' test.ping

Troubleshooting
=============

Logs are in ``/var/log/salt``

.. _pkgutil: http://www.opencsw.org/manual/for-administrators/getting-started.html
