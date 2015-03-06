=======
Solaris
=======

Salt was added to the OpenCSW package repository in September of 2012 by Romeo
Theriault <romeot@hawaii.edu> at version 0.10.2 of Salt. It has mainly been
tested on Solaris 10 (sparc), though it is built for and has been tested
minimally on Solaris 10 (x86), Solaris 9 (sparc/x86) and 11 (sparc/x86).
(Please let me know if you're using it on these platforms!) Most of the testing
has also just focused on the minion, though it has verified that the master
starts up successfully on Solaris 10.

Comments and patches for better support on these platforms is very welcome.

As of version 0.10.4, Solaris is well supported under salt, with all of the
following working well:

1.   remote execution
2.   grain detection
3.   service control with SMF
4.   'pkg' states with 'pkgadd' and 'pkgutil' modules
5.   cron modules/states
6.   user and group modules/states
7.   shadow password management modules/states

Salt is dependent on the following additional packages. These will
automatically be installed as dependencies of the ``py_salt`` package:

- py_yaml
- py_pyzmq
- py_jinja2
- py_msgpack_python
- py_m2crypto
- py_crypto
- python

Installation
============

To install Salt from the OpenCSW package repository you first need to install
`pkgutil`_ assuming you don't already have it installed:

On Solaris 10:

.. code-block:: bash

   pkgadd -d http://get.opencsw.org/now

On Solaris 9:

.. code-block:: bash

   wget http://mirror.opencsw.org/opencsw/pkgutil.pkg
   pkgadd -d pkgutil.pkg all

Once pkgutil is installed you'll need to edit it's config file
``/etc/opt/csw/pkgutil.conf`` to point it at the unstable catalog:

.. code-block:: diff

   - #mirror=http://mirror.opencsw.org/opencsw/testing
   + mirror=http://mirror.opencsw.org/opencsw/unstable

OK, time to install salt.

.. code-block:: bash

   # Update the catalog
   root> /opt/csw/bin/pkgutil -U
   # Install salt
   root> /opt/csw/bin/pkgutil -i -y py_salt

Minion Configuration
====================

Now that salt is installed you can find it's configuration files in
``/etc/opt/csw/salt/``.

You'll want to edit the minion config file to set the name of your salt master
server:

.. code-block:: diff

    - #master: salt
    + master: your-salt-server

If you would like to use `pkgutil`_ as the default package provider for your
Solaris minions, you can do so using the :conf_minion:`providers` option in the
minion config file.

You can now start the salt minion like so:

On Solaris 10:

.. code-block:: bash

    svcadm enable salt-minion


On Solaris 9:

.. code-block:: bash

    /etc/init.d/salt-minion start

You should now be able to log onto the salt master and check to see if the
salt-minion key is awaiting acceptance:

.. code-block:: bash

   salt-key -l un

Accept the key:

.. code-block:: bash

    salt-key -a <your-salt-minion>

Run a simple test against the minion:

.. code-block:: bash

    salt '<your-salt-minion>' test.ping

Troubleshooting
===============

Logs are in ``/var/log/salt``

.. _pkgutil: http://www.opencsw.org/manual/for-administrators/getting-started.html