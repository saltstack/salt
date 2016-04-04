==================
Salt in 10 Minutes
==================

.. note::
    Welcome to SaltStack! I am excited that you are interested in Salt and
    starting down the path to better infrastructure management. I developed
    (and am continuing to develop) Salt with the goal of making the best
    software available to manage computers of almost any kind. I hope you enjoy
    working with Salt and that the software can solve your real world needs!

    - Thomas S Hatch
    - Salt creator and Chief Developer
    - CTO of SaltStack, Inc.


Getting Started
===============

What is Salt?
-------------

Salt is a different approach to infrastructure management, founded on
the idea that high-speed communication with large numbers of systems can open
up new capabilities. This approach makes Salt a powerful multitasking system
that can solve many specific problems in an infrastructure.

The backbone of Salt is the remote execution engine, which creates a high-speed,
secure and bi-directional communication net for groups of systems. On top of this
communication system, Salt provides an extremely fast, flexible, and easy-to-use
configuration management system called ``Salt States``.

Installing Salt
---------------

SaltStack has been made to be very easy to install and get started. The
:doc:`installation documents </topics/installation/index>` contain instructions
for all supported platforms.

Starting Salt
-------------

Salt functions on a master/minion topology. A master server acts as a
central control bus for the clients, which are called ``minions``. The minions
connect back to the master.


Setting Up the Salt Master
~~~~~~~~~~~~~~~~~~~~~~~~~~

Turning on the Salt Master is easy -- just turn it on! The default configuration
is suitable for the vast majority of installations. The Salt Master can be
controlled by the local Linux/Unix service manager:

On Systemd based platforms (newer Debian, OpenSuse, Fedora):

.. code-block:: bash

    systemctl start salt-master

On Upstart based systems (Ubuntu, older Fedora/RHEL):

.. code-block:: bash

    service salt-master start

On SysV Init systems (Gentoo, older Debian etc.):

.. code-block:: bash

    /etc/init.d/salt-master start

Alternatively, the Master can be started directly on the command-line:

.. code-block:: bash

    salt-master -d

The Salt Master can also be started in the foreground in debug mode, thus
greatly increasing the command output:

.. code-block:: bash

    salt-master -l debug

The Salt Master needs to bind to two TCP network ports on the system. These ports
are ``4505`` and ``4506``. For more in depth information on firewalling these ports,
the firewall tutorial is available :doc:`here </topics/tutorials/firewall>`.

.. _master-dns:

Finding the Salt Master
~~~~~~~~~~~~~~~~~~~~~~~
When a minion starts, by default it searches for a system that resolves to the ``salt`` hostname`` on the network.
If found, the minion initiates the handshake and key authentication process with the Salt master.
This means that the easiest configuration approach is to set internal DNS to resolve the name ``salt`` back to the Salt Master IP.

Otherwise, the minion configuration file will need to be edited so that the
configuration option ``master`` points to the DNS name or the IP of the Salt Master:

.. note::

    The default location of the configuration files is ``/etc/salt``. Most
    platforms adhere to this convention, but platforms such as FreeBSD and
    Microsoft Windows place this file in different locations.

``/etc/salt/minion:``

.. code-block:: yaml

    master: saltmaster.example.com

Setting up a Salt Minion
~~~~~~~~~~~~~~~~~~~~~~~~
.. note::

    The Salt Minion can operate with or without a Salt Master. This walk-through
    assumes that the minion will be connected to the master, for information on
    how to run a master-less minion please see the master-less quick-start guide:

    :doc:`Masterless Minion Quickstart </topics/tutorials/quickstart>`

Now that the master can be found, start the minion in the same way as the
master; with the platform init system or via the command line directly:

As a daemon:

.. code-block:: bash

    salt-minion -d

In the foreground in debug mode:

.. code-block:: bash

    salt-minion -l debug

.. _minion-id-generation:

When the minion is started, it will generate an ``id`` value, unless it has
been generated on a previous run and cached in the configuration directory, which
is ``/etc/salt`` by default. This is the name by which the minion will attempt
to authenticate to the master. The following steps are attempted, in order to
try to find a value that is not ``localhost``:

1. The Python function ``socket.getfqdn()`` is run
2. ``/etc/hostname`` is checked (non-Windows only)
3. ``/etc/hosts`` (``%WINDIR%\system32\drivers\etc\hosts`` on Windows hosts) is
   checked for hostnames that map to anything within :strong:`127.0.0.0/8`.

If none of the above are able to produce an id which is not ``localhost``, then
a sorted list of IP addresses on the minion (excluding any within
:strong:`127.0.0.0/8`) is inspected. The first publicly-routable IP address is
used, if there is one. Otherwise, the first privately-routable IP address is
used.

If all else fails, then ``localhost`` is used as a fallback.

.. note:: Overriding the ``id``

    The minion id can be manually specified using the :conf_minion:`id`
    parameter in the minion config file.  If this configuration value is
    specified, it will override all other sources for the ``id``.

Now that the minion is started, it will generate cryptographic keys and attempt
to connect to the master. The next step is to venture back to the master server
and accept the new minion's public key.

.. _using-salt-key:

Using salt-key
~~~~~~~~~~~~~~

Salt authenticates minions using public-key encryption and authentication. For
a minion to start accepting commands from the master, the minion keys need to be
accepted by the master.

The ``salt-key`` command is used to manage all of the keys on the
master. To list the keys that are on the master:

.. code-block:: bash

    salt-key -L

The keys that have been rejected, accepted, and pending acceptance are listed.
The easiest way to accept the minion key is to accept all pending keys:

.. code-block:: bash

    salt-key -A

.. note::

    Keys should be verified! Print the master key fingerprint by running ``salt-key -F master``
    on the Salt master. Copy the ``master.pub`` fingerprint from the Local Keys section,
    and then set this value as the :conf_minion:`master_finger` in the minion configuration
    file. Restart the Salt minion.

    On the master, run ``salt-key -f minion-id`` to print the fingerprint of the
    minion's public key that was received by the master. On the minion, run
    ``salt-call key.finger --local`` to print the fingerprint of the minion key.

    On the master:

    .. code-block:: bash

        # salt-key -f foo.domain.com
        Unaccepted Keys:
        foo.domain.com:  39:f9:e4:8a:aa:74:8d:52:1a:ec:92:03:82:09:c8:f9

    On the minion:

    .. code-block:: bash

        # salt-call key.finger --local
        local:
            39:f9:e4:8a:aa:74:8d:52:1a:ec:92:03:82:09:c8:f9

    If they match, approve the key with ``salt-key -a foo.domain.com``.


Sending the First Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that the minion is connected to the master and authenticated, the master
can start to command the minion.

Salt commands allow for a vast set of functions to be executed and for
specific minions and groups of minions to be targeted for execution.

The ``salt`` command is comprised of command options, target specification,
the function to execute, and arguments to the function.

A simple command to
start with looks like this:

.. code-block:: bash

    salt '*' test.ping

The ``*`` is the target, which specifies all minions.

``test.ping`` tells the minion to run the :py:func:`test.ping
<salt.modules.test.ping>` function.

In the case of ``test.ping``, ``test`` refers to a :doc:`execution module
</ref/modules/index>`.  ``ping`` refers to the :py:func:`ping
<salt.modules.test.ping>` function contained in the aforementioned ``test``
module.

.. note::

    Execution modules are the workhorses of Salt. They do the work on the
    system to perform various tasks, such as manipulating files and restarting
    services.

The result of running this command will be the master instructing all of the
minions to execute :py:func:`test.ping <salt.modules.test.ping>` in parallel
and return the result.

This is not an actual ICMP ping, but rather a simple function which returns ``True``.
Using :py:func:`test.ping <salt.modules.test.ping>` is a good way of confirming that a minion is
connected.

.. note::

    Each minion registers itself with a unique minion ID. This ID defaults to
    the minion's hostname, but can be explicitly defined in the minion config as
    well by using the :conf_minion:`id` parameter.

Of course, there are hundreds of other modules that can be called just as
``test.ping`` can.  For example, the following would return disk usage on all
targeted minions:

.. code-block:: bash

    salt '*' disk.usage


Getting to Know the Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt comes with a vast library of functions available for execution, and Salt
functions are self-documenting. To see what functions are available on the
minions execute the :py:func:`sys.doc <salt.modules.sys.doc>` function:

.. code-block:: bash

    salt '*' sys.doc

This will display a very large list of available functions and documentation on
them.

.. note::
    Module documentation is also available :doc:`on the web </ref/modules/all/index>`.

These functions cover everything from shelling out to package management to
manipulating database servers. They comprise a powerful system management API
which is the backbone to Salt configuration management and many other aspects
of Salt.

.. note::

    Salt comes with many plugin systems. The functions that are available via
    the ``salt`` command are called :doc:`Execution Modules
    </ref/modules/all/index>`.


Helpful Functions to Know
~~~~~~~~~~~~~~~~~~~~~~~~~

The :doc:`cmd </ref/modules/all/salt.modules.cmdmod>` module contains
functions to shell out on minions, such as :mod:`cmd.run
<salt.modules.cmdmod.run>` and :mod:`cmd.run_all
<salt.modules.cmdmod.run_all>`:

.. code-block:: bash

    salt '*' cmd.run 'ls -l /etc'

The ``pkg`` functions automatically map local system package managers to the
same salt functions. This means that ``pkg.install`` will install packages via
``yum`` on Red Hat based systems, ``apt`` on Debian systems, etc.:

.. code-block:: bash

    salt '*' pkg.install vim

.. note::
    Some custom Linux spins and derivatives of other distributions are not properly
    detected by Salt. If the above command returns an error message saying that
    ``pkg.install`` is not available, then you may need to override the pkg
    provider. This process is explained :doc:`here </ref/states/providers>`.

The :mod:`network.interfaces <salt.modules.network.interfaces>` function will
list all interfaces on a minion, along with their IP addresses, netmasks, MAC
addresses, etc:

.. code-block:: bash

    salt '*' network.interfaces


Changing the Output Format
~~~~~~~~~~~~~~~~~~~~~~~~~~

The default output format used for most Salt commands is called the ``nested``
outputter, but there are several other outputters that can be used to change
the way the output is displayed. For instance, the ``pprint`` outputter can be
used to display the return data using Python's ``pprint`` module:

.. code-block:: bash

    root@saltmaster:~# salt myminion grains.item pythonpath --out=pprint
    {'myminion': {'pythonpath': ['/usr/lib64/python2.7',
                                 '/usr/lib/python2.7/plat-linux2',
                                 '/usr/lib64/python2.7/lib-tk',
                                 '/usr/lib/python2.7/lib-tk',
                                 '/usr/lib/python2.7/site-packages',
                                 '/usr/lib/python2.7/site-packages/gst-0.10',
                                 '/usr/lib/python2.7/site-packages/gtk-2.0']}}

The full list of Salt outputters, as well as example output, can be found
:ref:`here <all-salt.output>`.


``salt-call``
~~~~~~~~~~~~~

The examples so far have described running commands from the Master using the
``salt`` command, but when troubleshooting it can be more beneficial to login
to the minion directly and use ``salt-call``.

Doing so allows you to see the minion log messages specific to the command you
are running (which are *not* part of the return data you see when running the
command from the Master using ``salt``), making it unnecessary to tail the
minion log. More information on ``salt-call`` and how to use it can be found
:ref:`here <using-salt-call>`.

Grains
~~~~~~

Salt uses a system called :doc:`Grains <../targeting/grains>` to build up
static data about minions. This data includes information about the operating
system that is running, CPU architecture and much more. The grains system is
used throughout Salt to deliver platform data to many components and to users.

Grains can also be statically set, this makes it easy to assign values to
minions for grouping and managing.

A common practice is to assign grains to minions to specify what the role or
roles a minion might be. These static grains can be set in the minion
configuration file or via the :mod:`grains.setval <salt.modules.grains.setval>`
function.



Targeting
~~~~~~~~~~

Salt allows for minions to be targeted based on a wide range of criteria.  The
default targeting system uses globular expressions to match minions, hence if
there are minions named ``larry1``, ``larry2``, ``curly1``, and ``curly2``, a
glob of ``larry*`` will match ``larry1`` and ``larry2``, and a glob of ``*1``
will match ``larry1`` and ``curly1``.

Many other targeting systems can be used other than globs, these systems
include:

Regular Expressions
    Target using PCRE-compliant regular expressions

Grains
    Target based on grains data:
    :doc:`Targeting with Grains </topics/targeting/grains>`

Pillar
    Target based on pillar data:
    :doc:`Targeting with Pillar </ref/pillar/index>`

IP
    Target based on IP address/subnet/range

Compound
    Create logic to target based on multiple targets:
    :doc:`Targeting with Compound </topics/targeting/compound>`

Nodegroup
    Target with nodegroups:
    :doc:`Targeting with Nodegroup </topics/targeting/nodegroups>`

The concepts of targets are used on the command line with Salt, but also
function in many other areas as well, including the state system and the
systems used for ACLs and user permissions.


Passing in Arguments
~~~~~~~~~~~~~~~~~~~~

Many of the functions available accept arguments which can be passed in on
the command line:

.. code-block:: bash

    salt '*' pkg.install vim

This example passes the argument ``vim`` to the pkg.install function. Since
many functions can accept more complex input than just a string, the arguments
are parsed through YAML, allowing for more complex data to be sent on the
command line:

.. code-block:: bash

    salt '*' test.echo 'foo: bar'

In this case Salt translates the string 'foo: bar' into the dictionary
"{'foo': 'bar'}"

.. note::

    Any line that contains a newline will not be parsed by YAML.


Salt States
===========

Now that the basics are covered the time has come to evaluate ``States``.  Salt
``States``, or the ``State System`` is the component of Salt made for
configuration management.

The state system is already available with a basic Salt setup, no additional
configuration is required. States can be set up immediately.

.. note::

    Before diving into the state system, a brief overview of how states are
    constructed will make many of the concepts clearer. Salt states are based
    on data modeling and build on a low level data structure that is used to
    execute each state function. Then more logical layers are built on top of
    each other.

    The high layers of the state system which this tutorial will
    cover consists of everything that needs to be known to use states, the two
    high layers covered here are the `sls` layer and the highest layer
    `highstate`.

    Understanding the layers of data management in the State System will help with
    understanding states, but they never need to be used. Just as understanding
    how a compiler functions assists when learning a programming language,
    understanding what is going on under the hood of a configuration management
    system will also prove to be a valuable asset.


The First SLS Formula
---------------------

The state system is built on SLS formulas. These formulas are built out in
files on Salt's file server. To make a very basic SLS formula open up a file
under /srv/salt named vim.sls. The following state ensures that vim is installed
on a system to which that state has been applied.

``/srv/salt/vim.sls:``

.. code-block:: yaml

    vim:
      pkg.installed

Now install vim on the minions by calling the SLS directly:

.. code-block:: bash

    salt '*' state.sls vim

This command will invoke the state system and run the ``vim`` SLS.

Now, to beef up the vim SLS formula, a ``vimrc`` can be added:

``/srv/salt/vim.sls:``

.. code-block:: yaml

    vim:
      pkg.installed: []

    /etc/vimrc:
      file.managed:
        - source: salt://vimrc
        - mode: 644
        - user: root
        - group: root

Now the desired ``vimrc`` needs to be copied into the Salt file server to
``/srv/salt/vimrc``. In Salt, everything is a file, so no path redirection needs
to be accounted for. The ``vimrc`` file is placed right next to the ``vim.sls`` file.
The same command as above can be executed to all the vim SLS formulas and now
include managing the file.

.. note::

    Salt does not need to be restarted/reloaded or have the master manipulated
    in any way when changing SLS formulas. They are instantly available.


Adding Some Depth
-----------------

Obviously maintaining SLS formulas right in a single directory at the root of
the file server will not scale out to reasonably sized deployments. This is
why more depth is required. Start by making an nginx formula a better way,
make an nginx subdirectory and add an init.sls file:

``/srv/salt/nginx/init.sls:``

.. code-block:: yaml

    nginx:
      pkg.installed: []
      service.running:
        - require:
          - pkg: nginx

A few concepts are introduced in this SLS formula.

First is the service statement which ensures that the ``nginx`` service is running.

Of course, the nginx service can't be started unless the package is installed --
hence the ``require`` statement which sets up a dependency between the two.

The ``require`` statement makes sure that the required component is executed before
and that it results in success.

.. note::

    The `require` option belongs to a family of options called `requisites`.
    Requisites are a powerful component of Salt States, for more information
    on how requisites work and what is available see:
    :doc:`Requisites</ref/states/requisites>`

    Also evaluation ordering is available in Salt as well:
    :doc:`Ordering States</ref/states/ordering>`

This new sls formula has a special name --  ``init.sls``. When an SLS formula is
named ``init.sls`` it inherits the name of the directory path that contains it.
This formula can be referenced via the following command:

.. code-block:: bash

    salt '*' state.sls nginx

.. note::
    Reminder!

    Just as one could call the ``test.ping`` or ``disk.usage`` execution modules,
    ``state.sls`` is simply another execution module. It simply takes the name of an
    SLS file as an argument.

Now that subdirectories can be used, the ``vim.sls`` formula can be cleaned up.
To make things more flexible, move the ``vim.sls`` and vimrc into a new subdirectory
called ``edit`` and change the ``vim.sls`` file to reflect the change:

``/srv/salt/edit/vim.sls:``

.. code-block:: yaml

    vim:
      pkg.installed

    /etc/vimrc:
      file.managed:
        - source: salt://edit/vimrc
        - mode: 644
        - user: root
        - group: root

Only the source path to the vimrc file has changed. Now the formula is
referenced as ``edit.vim`` because it resides in the edit subdirectory.
Now the edit subdirectory can contain formulas for emacs, nano, joe or any other
editor that may need to be deployed.


Next Reading
------------

Two walk-throughs are specifically recommended at this point. First, a deeper
run through States, followed by an explanation of Pillar.

1. :doc:`Starting States </topics/tutorials/starting_states>`

2. :doc:`Pillar Walkthrough </topics/tutorials/pillar>`

An understanding of Pillar is extremely helpful in using States.


Getting Deeper Into States
--------------------------

Two more in-depth States tutorials exist, which delve much more deeply into States
functionality.

1. :doc:`How Do I Use Salt States? </topics/tutorials/starting_states>`, covers much
   more to get off the ground with States.

2. The :doc:`States Tutorial</topics/tutorials/states_pt1>` also provides a
   fantastic introduction.

These tutorials include much more in-depth information including templating
SLS formulas etc.


So Much More!
=============

This concludes the initial Salt walk-through, but there are many more things still
to learn! These documents will cover important core aspects of Salt:

- :doc:`Pillar</topics/pillar/index>`

- :doc:`Job Management</topics/jobs/index>`

A few more tutorials are also available:

- :doc:`Remote Execution Tutorial</topics/tutorials/modules>`

- :doc:`Standalone Minion</topics/tutorials/standalone_minion>`

This still is only scratching the surface, many components such as the reactor
and event systems, extending Salt, modular components and more are not covered
here. For an overview of all Salt features and documentation, look at the
:doc:`Table of Contents</contents>`.
