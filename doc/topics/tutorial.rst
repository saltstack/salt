========
Tutorial
========

The Salt system setup is amazingly simple, as this is one of the central design
goals of Salt. Setting up Salt only requires that the Salt :term:`master` be
running and the Salt :term:`minions <minion>` point to the master.

.. glossary::

    master
        The Salt master is the central server that all minions connect to. You
        run commands on the minions through the master and minions send data
        back to the master (unless otherwise redirected with a :doc:`returner
        <../ref/returners/index>`). It is started with the
        :command:`salt-master` program.

    minion
        Salt minions are the potentially hundreds or thousands of servers that
        you query and control from the master.

Installing Salt
===============

As of this writing packages for Salt only exist for Arch Linux, but rpms and
debs will be available in the future (contributions welcome).

.. contents:: Instructions by operating system
    :depth: 1
    :local:

Installing on Arch Linux
------------------------

The Arch Linux Salt package is available in the Arch Linux AUR (if you like
Salt vote for it on the Arch Linux AUR):

https://aur.archlinux.org/packages.php?ID=47512

For help using packages in the Arch Linux AUR:

https://wiki.archlinux.org/index.php/AUR

Installing on Debian or Ubuntu
------------------------------

Providing a .deb installer is on our short-list of things to do; until then
this is the best way to install Salt on Debian and Ubuntu systems:

1.  Install the prerequisite packages::

        aptitude install python-dev python-setuptools python-yaml python-crypto python-m2crypto cython libzmq-dev

    .. note:: Installing on Ubuntu Lucid (10.04 LTS)

        The ZeroMQ package is available starting with Maverick but it is not
        yet available in Lucid backports. Fortunately, Chris Lea has made a
        `ZeroMQ PPA`_ available. Install it before installing Salt::

            aptitude install python-software-properties
            add-apt-repository ppa:chris-lea/zeromq
            add-apt-repository ppa:chris-lea/libpgm
            aptitude update
            aptitude install libzmq-dev

2.  Grab the latest Python ZeroMQ bindings::

        easy_install pyzmq

3.  Install Salt:

    .. parsed-literal::

        easy_install -U --install-layout=deb |latest|

    Please take note of the ``--install-layout=deb`` flag. This is important
    for a functioning installation of Salt. If you have an older version of
    ZeroMQ installed (say from an earlier installation of Salt) purge it first:
    ``aptitude -y purge libzmq0``.

.. _`ZeroMQ PPA`: https://launchpad.net/~chris-lea/+archive/zeromq

Installing from the source tarball
----------------------------------

1.  Download the latest source tarball from the GitHub downloads directory for
    the Salt project: https://github.com/thatch45/salt/downloads

2.  Untar the tarball and run the :file:`setup.py` as root:

.. parsed-literal::

    tar xvf salt-|version|.tar.gz
    cd salt-|version|
    python2 setup.py install

Salt dependencies
`````````````````

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

Configuring Salt
================

Salt configuration is very simple. The default configuration for the
:term:`master` will work for most installations and the only requirement for
setting up a :term:`minion` is to set the location of the master in the minion
configuration file. The configuration files will be installed to
:file:`/etc/salt` and are named after the respective components,
:file:`/etc/salt/master` and :file:`/etc/salt/minion`.

To make a minion check into the correct master simply edit the
:conf_minion:`master` variable in the minion configuration file to reference
the master DNS name or IPv4 address.

.. seealso::

    For further information consult the :doc:`configuration guide
    <../ref/configuration/index>`.

Running Salt
============

1.  Start the :term:`master` in the foreground (to daemonize the process, pass
    the :option:`-d flag <salt-master -d>`)::

        salt-master

2.  Start the :term:`minion` in the foreground (to daemonize the process, pass
    the :option:`-d flag <salt-minion -d>`)::

        salt-minion

.. seealso:: :doc:`salt-master manpage <../ref/cli/salt-master>` and
    :doc:`salt-minion manpage <../ref/cli/salt-minion>`

Arch Linux init scripts
-----------------------

.. code-block:: bash

    /etc/rc.d/salt-master start
    /etc/rc.d/salt-minion start

Manage Salt public keys
=======================

Salt manages authentication with RSA public keys. The keys are managed on the
:term:`master` via the :command:`salt-key` command. Once a :term:`minion`
checks into the master the master will save a copy of the minion key. Before
the master can send commands to the minion the key needs to be "accepted".

1.  List the accepted and unaccepted salt keys::

        salt-key -L

2.  Accept a minion key::

        salt-key -a <minion id>

    or accept all unaccepted minion keys::

        salt-key -A

.. seealso:: :doc:`salt-key manpage <../ref/cli/salt-key>`

Order your minions around
=========================

Now that you have a :term:`master` and at least one :term:`minion`
communicating with each other you can perform commands on the minion via the
:command:`salt` command. Salt calls are comprised of three main components::

    salt '<target>' <function> [arguments]

.. seealso:: :doc:`salt manpage <../ref/cli/salt>`

target
------

The target component allows you to filter which minions should run the
following function. The default filter is a glob on the minion id. E.g.::

    salt '*' test.ping
    salt '*.example.org' test.ping

Targets can be based on minion system information using the grains system::

    salt -G 'os:Ubuntu' test.ping

.. seealso:: :doc:`Grains system <../ref/grains>`

Targets can be filtered by regular expression::

    salt -E 'virtmach[0-9]' test.ping

Finally, targets can be explicitly specified in a list::

    salt -L foo,bar,baz,quo test.ping

function
--------

A function is some functionality provided by a module. Salt ships with a large
collection of available functions. List all available functions on your
minions::

    salt '*' sys.doc

Here are some examples:

Show all currently available minions::

    salt '*' test.ping

Run an arbitrary shell command::

    salt '*' cmd.run 'uname -a'

.. seealso:: :doc:`the full list of modules <../ref/modules/index>`

arguments
---------

Space-delimited arguments to the function::

    salt '*' cmd.exec_code python 'import sys; print sys.version'
