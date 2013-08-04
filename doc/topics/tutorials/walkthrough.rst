======================
Salt Stack Walkthrough
======================

Welcome!
========

Welcome to Salt Stack! I am excited that you are interested in Salt and
starting down the path to better infrastructure management. I developed
(and am continuing to develop) Salt with the goal of making the best
software available to manage computers of almost any kind. I hope you enjoy
working with Salt and that the software can solve your real world needs!

- Thomas S Hatch
- Salt creator and chief developer
- CTO of Salt Stack, Inc.

.. note::

    This is the first of a series of walkthroughs and serves as the best entry
    point for people new to Salt, after this be sure to read up on pillar and
    more on states:

    :doc:`Starting States </topics/tutorials/starting_states>`

    :doc:`Pillar Walkthrough </topics/tutorials/pillar>`


Getting Started
===============

What is Salt?
-------------

Salt is a different approach to infrastructure management, it is founded on
the idea that high speed communication with large numbers of systems can open
up new capabilities. This approach makes Salt a powerful multitasking system
that can solve many specific problems in an infrastructure. The backbone of
Salt is the remote execution engine, which creates a high speed, secure and
bi-directional communication net for groups of systems. On top of this
communication system Salt provides an extremely fast, flexible and easy to use
configuration management system called ``Salt States``.

This unique approach to management makes for a transparent control system that
is not only amazingly easy to set up and use, but also capable of solving very
complex problems in infrastructures; as will be explored in this walk through.

Salt is being used today by some of the largest infrastructures in the world
and has a proven ability to scale to astounding proportions without
modification. With the proven ability to scale out well beyond many tens of
thousands of servers, Salt has also proven to be an excellent choice for small
deployments as well, lowering compute and management overhead for
infrastructures as small as just a few systems.


Installing Salt
---------------

Salt Stack has been made to be very easy to install and get started. Setting up
Salt should be as easy as installing Salt via distribution packages on Linux or
via the Windows installer. The :doc:`installation documents
</topics/installation/index>` cover specific platform installation in depth.


Starting Salt
-------------

Salt functions on a master/minion topology. A master server acts as a
central control bus for the clients (called minions), and the minions connect
back to the master.


Setting Up the Salt Master
~~~~~~~~~~~~~~~~~~~~~~~~~~

Turning on the Salt Master is easy, just turn it on! The default configuration
is suitable for the vast majority of installations. The Salt master can be
controlled by the local Linux/Unix service manager:

On Systemd based platforms (OpenSuse, Fedora)::

    # systemctl start salt-master

On Upstart based systems (Ubuntu, older Fedora/RHEL)::

    # service salt-master start

On SysV Init systems (Debian, Gentoo etc.)::

    # /etc/init.d/salt-master start

Or the master can be started directly on the command line::

    # salt-master -d

The Salt Master can also be started in the foreground in debug mode, thus
greatly increasing the command output::

    # salt-master -l debug

The Salt Master needs to bind to 2 TCP network ports on the system, these ports
are 4505 and 4506. For more in depth information on firewalling these ports,
the firewall tutorial is available :doc:`here </topics/tutorials/firewall>`.


Setting up a Salt Minion
~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    The Salt Minion can operate with or without a Salt Master. This walkthrough
    assumes that the minion will be connected to the master, for information on
    how to run a master-less minion please see the masterless quickstart guide:

    :doc:`Masterless Minion Quickstart </topics/tutorials/quickstart>`

The Salt Minion only needs to be aware of one piece of information to run, the
network location of the master. By default the minion will look for the DNS
name `salt` for the master, making the easiest approach to set internal DNS to
resolve the name `salt` back to the Salt Master IP. Otherwise the minion
configuration file will need to be edited, edit the configuration option
``master`` to point to the DNS name or the IP of the Salt Master:

.. note::

    The default location of the configuration files is ``/etc/salt``. Most
    platforms adhere to this convention, but platforms such as FreeBSD and
    Microsoft Windows place this file in different locations.

``/etc/salt/minion:``

.. code-block:: yaml

    master: saltmaster.example.com

Now that the master can be found, start the minion in the same way as the
master; with the platform init system, or via the command line directly:

As a daemon::

    # salt-minion -d

In the foreground in debug mode::

    # salt-minion -l debug

Now that the minion is started it will generate cryptographic keys and attempt
to connect to the master. The next step is to venture back to the master server
and accept the new minion's public key.


Using salt-key
~~~~~~~~~~~~~~

Salt authenticates minions using public key encryption and authentication. For
a minion to start accepting commands from the master the minion keys need to be
accepted. The ``salt-key`` command is used to manage all of the keys on the
master. To list the keys that are on the master run a salt-key list command::

    # salt-key -L

The keys that have been rejected, accepted and pending acceptance are listed.
The easiest way to accept the minion key is to accept all pending keys::

    # salt-key -A

.. note::

    Keys should be verified! The secure thing to do before accepting a key is
    to run ``salt-key -p minion-id`` to print the public key for the minion.
    This can then be compared against the minion's public key file, which is
    located (on the minion, of course) at ``/etc/salt/pki/minion/minion.pub``.

    On the master::

        # salt-key -p foo.domain.com
        Accepted Keys:
        foo.domain.com:  -----BEGIN PUBLIC KEY-----
        MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA0JcA0IEp/yqghK5V2VLM
        jbG7FWV6qtw/ubTDBnpDGQgrvSNOtd0QcJsAzAtDcHwrudQgyxTZGVJqPY7gLc7P
        5b4EFWt5E1w3+KZ+XXy4YtW5oOzVN5BvsJ85g7c0TUnmjL7p3MUUXE4049Ue/zgX
        jtbFJ0aa1HB8bnlQdWWOeflYRNEQL8482ZCmXXATFP1l5uJA9Pr6/ltdWtQTsXUA
        bEseUGEpmq83vAkwtZIyJRG2cJh8ZRlJ6whSMg6wr7lFvStHQQzKHt9pRPml3lLK
        ba2X07myAEJq/lpJNXJm5bkKV0+o8hqYQZ1ndh9HblHb2EoDBNbuIlhYft1uv8Tp
        8beaEbq8ZST082sS/NjeL7W1T9JS6w2rw4GlUFuQlbqW8FSl1VDo+Alxu0VAr4GZ
        gZpl2DgVoL59YDEVrlB464goly2c+eY4XkNT+JdwQ9LwMr83/yAAG6EGNpjT3pZg
        Wey7WRnNTIF7H7ISwEzvik1GrhyBkn6K1RX3uAf760ZsQdhxwHmop+krgVcC0S93
        xFjbBFF3+53mNv7BNPPgl0iwgA9/WuPE3aoE0A8Cm+Q6asZjf8P/h7KS67rIBEKV
        zrQtgf3aZBbW38CT4fTzyWAP138yrU7VSGhPMm5KfTLywNsmXeaR5DnZl6GGNdL1
        fZDM+J9FIGb/50Ee77saAlUCAwEAAQ==
        -----END PUBLIC KEY-----

    On the minion::

        # cat /etc/salt/pki/minion/minion.pub
        -----BEGIN PUBLIC KEY-----
        MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA0JcA0IEp/yqghK5V2VLM
        jbG7FWV6qtw/ubTDBnpDGQgrvSNOtd0QcJsAzAtDcHwrudQgyxTZGVJqPY7gLc7P
        5b4EFWt5E1w3+KZ+XXy4YtW5oOzVN5BvsJ85g7c0TUnmjL7p3MUUXE4049Ue/zgX
        jtbFJ0aa1HB8bnlQdWWOeflYRNEQL8482ZCmXXATFP1l5uJA9Pr6/ltdWtQTsXUA
        bEseUGEpmq83vAkwtZIyJRG2cJh8ZRlJ6whSMg6wr7lFvStHQQzKHt9pRPml3lLK
        ba2X07myAEJq/lpJNXJm5bkKV0+o8hqYQZ1ndh9HblHb2EoDBNbuIlhYft1uv8Tp
        8beaEbq8ZST082sS/NjeL7W1T9JS6w2rw4GlUFuQlbqW8FSl1VDo+Alxu0VAr4GZ
        gZpl2DgVoL59YDEVrlB464goly2c+eY4XkNT+JdwQ9LwMr83/yAAG6EGNpjT3pZg
        Wey7WRnNTIF7H7ISwEzvik1GrhyBkn6K1RX3uAf760ZsQdhxwHmop+krgVcC0S93
        xFjbBFF3+53mNv7BNPPgl0iwgA9/WuPE3aoE0A8Cm+Q6asZjf8P/h7KS67rIBEKV
        zrQtgf3aZBbW38CT4fTzyWAP138yrU7VSGhPMm5KfTLywNsmXeaR5DnZl6GGNdL1
        fZDM+J9FIGb/50Ee77saAlUCAwEAAQ==
        -----END PUBLIC KEY-----


Sending the First Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that the minion is connected to the master and authenticated, the master 
can start to command the minion. Salt commands allow for a vast set of
functions to be executed and for specific minions and groups of minions to be
targeted for execution. This makes the ``salt`` command very powerful, but
the command is also very usable, and easy to understand.

The ``salt`` command is comprised of command options, target specification,
the function to execute, and arguments to the function. A simple command to
start with looks like this::

    # salt '*' test.ping

The ``*`` is the target, which specifies all minions, and ``test.ping`` tells
the minion to run the :ref:`test.ping <salt.modules.test.ping>` function. The
result of running this command will be the master instructing all of the
minions to execute :ref:`test.ping <salt.modules.test.ping>` in parallel and
return the result. This is not an actual ICMP ping, but rather a simple
function which returns ``True``. Using :ref:`test.ping
<salt.modules.test.ping>` is a good way of confirming that a minion is
connected.

.. note::

    Each minion registers itself with a unique minion id. This id defaults to
    the minion's hostname, but can be explicitly defined in the minion config as
    well by using the :conf_minion:`id` parameter.


Getting to Know the Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Salt comes with a vast library of functions available for execution, and Salt
functions are self documenting. To see what functions are available on the
minions execute the :ref:`sys.doc <salt.modules.sys.doc>` function::

    # salt '*' sys.doc

This will display a very large list of available functions and documentation on
them, this documentation is also available :doc:`here
</ref/modules/all/index>`.

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
<salt.modules.cmdmod.run_all>`::

    # salt '*' cmd.run 'ls -l /etc'

The ``pkg`` functions automatically map local system package managers to the
same salt functions. This means that ``pkg.install`` will install packages via
yum on Red Hat based systems, apt on Debian systems, etc.::

    # salt '*' pkg.install vim

The :mod:`network.interfaces <salt.modules.network.interfaces>` function will
list all interfaces on a minion, along with their IP addresses, netmasks, MAC
addresses, etc::

    # salt '*' network.interfaces


Grains
~~~~~~

Salt uses a system called :ref:`Grains <../targeting/grains>` to build up
static data about minions. This data includes information about the operating
system that is running, CPU architecture and much more. The grains system is
used throughout Salt to deliver platform data to many components and to users.

Grains can also be statically set, this makes it easy to assign values to
minions for grouping and managing. A common practice is to assign grains to
minions to specify what the role or roles a minion might be. These static
grains can be set in the minion configuration file or via the
:mod:`grains.setval <salt.modules.grains.setval>` function.


Targeting
~~~~~~~~~~

Salt allows for minions to be targeted based on a wide range of criteria.  The
default targeting system uses globular expressions to match minions, hence if
there are minions named ``larry1``, ``larry2``, ``curly1`` and ``curly2``, a
glob of ``larry*`` will match ``larry1`` and ``larry2``, and a glob of ``*1``
will match ``larry1`` and ``curly1``.

Many other targeting systems can be used other than globs, these systems
include:

Regular Expressions
    Target using PCRE compliant regular expressions

Grains
    Target based on grains data:
    :doc:`Targeting with Grains </topics/targeting/grains>`

Pillar
    Target based on pillar data:
    :doc:`Targeting with Pillar </ref/pillar/index>`

IP
    Target based on IP addr/subnet/range

Compound
    Create logic to target based on multiple targets:
    :doc:`Targeting with Compound </topics/targeting/compound>`

Nodegroup
    Target with nodegroups:
    :doc:`Targeting with Nodegroup </topics/targeting/nodegroups>`

The concepts of targets are used on the command line with salt, but also
function in many other areas as well, including the state system and the
systems used for ACLs and user permissions.


Passing in Arguments
~~~~~~~~~~~~~~~~~~~~

Many of the functions available accept arguments, these arguments can be
passed in on the command line::

    # salt '*' pkg.install vim

This example passes the argument ``vim`` to the pkg.install function, since
many functions can accept more complex input then just a string the arguments
are parsed through YAML, allowing for more complex data to be sent on the
command line::

    # salt '*' test.echo 'foo: bar'

In this case Salt translates the string 'foo: bar' into the dictionary
"{'foo': 'bar'}"

.. note::

    Any line that contains a newline will not be parsed by yaml.


Salt States
===========

Now that the basics are covered the time has come to evaluate ``States``.  Salt
``States``, or the ``State System`` is the component of Salt made for
configuration management. The State system is a fully functional configuration
management system which has been designed to be exceptionally powerful while
still being simple to use, fast, lightweight, deterministic and with salty
levels of flexibility.

The state system is already available with a basic salt setup, no additional
configuration is required, states can be set up immediately.

.. note::

    Before diving into the state system, a brief overview of how states are
    constructed will make many of the concepts clearer. Salt states are based
    on data modeling, and build on a low level data structure that is used to
    execute each state function. Then more logical layers are built on top of
    each other. The high layers of the state system which this tutorial will
    cover consists of everything that needs to be known to use states, the two
    high layers covered here are the `sls` layer and the highest layer
    `highstate`.

    Again, knowing that there are many layers of data management, will help with
    understanding states, but they never need to be used. Just as understanding
    how a compiler functions when learning a programming language,
    understanding what is going on under the hood of a configuration management
    system will also prove to be a valuable asset.


The First SLS Formula
---------------------

The state system is built on sls formulas, these formulas are built out in
files on Salt's file server. To make a very basic sls formula open up a file
under /srv/salt named vim.sls and get vim installed:

``/srv/salt/vim.sls:``

.. code-block:: yaml

    vim:
      pkg.installed

Now install vim on the minions by calling the sls directly::

    # salt '*' state.sls vim

This command will invoke the state system and run the named sls which was just
created, ``vim``.

Now, to beef up the vim sls formula, a vimrc can be added:

``/srv/salt/vim.sls:``

.. code-block:: yaml

    vim:
      pkg.installed

    /etc/vimrc:
      file.managed:
        - source: salt://vimrc
        - mode: 644
        - user: root
        - group: root

Now the desired vimrc needs to be copied into the Salt file server to
/srv/salt/vimrc, in Salt everything is a file, so no path redirection needs
to be accounted for. The vimrc file is placed right next to the vim.sls file.
The same command as above can be executed to all the vim sls formulas and now
include managing the file.

.. note::

    Salt does not need to be restarted/reloaded or have the master manipulated
    in any way when changing sls formulas, they are instantly available.


Adding Some Depth
-----------------

Obviously maintaining sls formulas right in the root of the file server will
not scale out to reasonably sized deployments. This is why more depth is
required. Start by making an nginx formula a better way, make an nginx
subdirectory and add an init.sls file:

``/srv/salt/nginx/init.sls:``

.. code-block:: yaml

    nginx:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: nginx

A few things are introduced in this sls formula, first is the service statement
which ensures that the nginx service is running, but the nginx service can't be
started unless the package is installed, hence the ``require``. The ``require``
statement makes sure that the required component is executed before and that it
results in success.

.. note::

    The `require` option belongs to a family of options called `requisites`.
    Requisites are a powerful component of Salt States, for more information
    on how requisites work and what is available see:
    :doc:`Requisites</ref/states/requisites>`
    Also evaluation ordering is available in Salt as well:
    :doc:`Ordering States</ref/states/ordering>`

Now this new sls formula has a special name, ``init.sls``, when an sls formula is
named ``init.sls`` it inherits the name of the directory path that contains it,
so this formula can be referenced via the following command::

    # salt '*' state.sls nginx

Now that subdirectories can be used the vim.sls formula can be cleaned up, but
to make things more flexible (and to illustrate another point of course), move
the vim.sls and vimrc into a new subdirectory called ``edit`` and change the
vim.sls file to reflect the change:

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

The only change in the file is fixing the source path for the vimrc file. Now
the formula is referenced as ``edit.vim`` because it resides in the edit
subdirectory. Now the edit subdirectory can contain formulas for emacs, nano,
joe or any other editor that may need to be deployed.


Next Reading
------------

Two walkthroughs are specifically recommended at this point. First, a deeper
run through States, followed by an explanation of Pillar.

1. :doc:`Starting States </topics/tutorials/starting_states>`

2. :doc:`Pillar Walkthrough </topics/tutorials/pillar>`

An understanding of Pillar is extremely helpful in using States.


Getting Deeper Into States
--------------------------

Two more in-depth States tutorials exist, which delve much more deeply into States
functionality.

1. Thomas' original states tutorial, :doc:`How Do I Use Salt
   States?</topics/tutorials/starting_states>`, covers much more to get off the
   ground with States.

2. The :doc:`States Tutorial</topics/tutorials/states_pt1>` also provides a
   fantastic introduction.

These tutorials include much more in depth information including templating
sls formulas etc.


So Much More!
=============

This concludes the initial Salt walkthrough, but there are many more things to
learn still! These documents will cover important core aspects of Salt:

- :doc:`Pillar</topics/pillar/index>`

- :doc:`Job Management</topics/jobs/index>`

A few more tutorials are also available:

- :doc:`Remote Execution Tutorial</topics/tutorials/modules>`

- :doc:`Standalone Minion</topics/tutorials/standalone_minion>`

This still is only scratching the surface, many components such as the reactor
and event systems, extending Salt, modular components and more are not covered
here. For an overview of all Salt features and documentation, look at the
:doc:`Table of Contents</contents>`.
