.. _contents:

.. |vid| image:: /_static/film_link.png
    :class: math

Get started with Salt
=====================

.. sidebar:: Presentations

    A list of `presentations and interviews on Salt`_ (including the FLOSS
    Weekly interview).

.. _`presentations and interviews on Salt`: http://saltstack.org/presentations/

Salt is a **remote execution** and **configuration management** tool.

Salt is designed to be secure using **AES encryption** and **public-key
authentication**; incredibly scaleable using an advanced **ZeroMQ** topology;
fast and efficient using **msgpack**; and extensible using small and simple
**Python** modules.

Read the :doc:`Salt overview <topics/index>` for a more thorough description.

Step 1: Remote execution
------------------------

.. sidebar:: |vid| Screencasts

    Watch the `remote execution screencast`__.

.. __: http://blip.tv/saltstack/salt-installation-configuration-and-remote-execution-5713423

The quickest way to see Salt in action is to run a command on a :term:`minion`
host from the :term:`master` host. This is widely known as :term:`remote
execution` — executing commands on remote hosts.

1.  `Installation`_
2.  :doc:`Configure the minion <topics/configuration>`
3.  :doc:`Run remote commands <topics/tutorials/modules>`

Step 2: Configuration management
--------------------------------

Now that you have the basics out of the way, learn to use Salt to configure
your servers. This is widely known as :term:`configuration management` —
installing packages, configuring users and services, and much more.

1.  :doc:`Basic config management <topics/tutorials/states_pt1>`
2.  :doc:`Less basic config management <topics/tutorials/states_pt2>`
3.  :doc:`Advanced techniques <topics/tutorials/states_pt3>`

Salt in depth
=============

Setting up and using Salt is a simple task but it's capabilities run much, much
deeper. Gaining a better understanding of how Salt works will allow you to
truly make it work for you.

.. sidebar:: More tutorials!

    * :doc:`Bootstraping Salt on EC2 <topics/tutorials/bootstrap_ec2>`
    * :doc:`Installing Salt on FreeBSD <topics/tutorials/freebsd>`

.. contents:: The components of Salt
    :local:
    :depth: 2

Remote execution
----------------

Remote execution is the core functionality of Salt. Running pre-defined or
arbitrary commands on remote hosts.

**Modules**
    Salt modules are the core of remote execution. They provide
    functionality such as installing a package, restarting a service,
    running a remote command, transferring a file — and the list goes on.

    :doc:`Full list of modules </ref/modules/all/index>`
        The giant list of core modules that ship with Salt
        (And there are even more in the `salt-contrib`_ repository!)

    :doc:`Writing modules <ref/modules/index>`
        A guide on how to write Salt modules

**Targeting**
    Specify which hosts should run commands or manage configuration.

    :doc:`Targeting <ref/targeting/index>`
        Hostnames, lists, regular expressions, or define groups.

    :doc:`Grains <ref/grains>`
        Bits of static information about a minion such as OS, version,
        virtualization, CPU, memory, and much more.

**Returners**
    Salt returners allow saving minion responses in various datastores or
    to various locations in addition to display at the CLI.

    :doc:`Full list of returners </ref/returners/all/index>`
        Store minion responses in Redis, Mongo, Cassandra or more.

    :doc:`Writing returners <ref/returners/index>`
        If we're missing your favorite storage backend, webservice, or you
        need a custom endpoint returners are *tiny* and simple to write.

Configuration management
------------------------

Building on the remote execution core is a robust and flexible config
management framework. Execution happens on the minions allowing
effortless, simultaneous configuration of thousands of hosts.

**States**
    Express the state of a host using small, easy to read, easy to
    understand configuration files. No programming required (unless you
    want to).

    :doc:`Full list of states <ref/states/all/index>`
        Install packages, create users, transfer files, start services, and
        more and more.

    :doc:`Using states <ref/states/index>`
        You've seen the big list of available states, now learn how to call
        them.

    :doc:`Highstate data structure <ref/states/highstate>`
        A dry, vocabulary and technical representation of the configuration
        format that states represent.

**Renderers**
    Write state configuration files in the language, templating engine, or
    file type of your choice. The world doesn't need yet another DSL.

    :doc:`Full list of renderers <ref/renderers/all/index>`
        YAML? JSON? Jinja? Mako? Python? We got you covered. (And if we
        don't, new renderers are *tiny* and easy to write.)

    :doc:`Renderers <ref/renderers/index>`
        Salt states are only concerned with the ultimate highstate data
        structure. How you create that data structure isn't our business.
        Tweak a config option and use whatever you're most comfortable
        with.

Miscellaneous topics
--------------------

Salt is a many splendid thing.

:doc:`File Server <ref/file_server/index>`
    Salt can easily and quickly transfer files (in fact, that's how Salt
    States work). Even under load, files are chunked and served.

:doc:`Syndic <ref/syndic>`
    A seamless master of masters. Scale Salt to thousands of hosts or
    across many different networks.

:doc:`Peer communication <ref/peer>`
    Allow minions to communicate amongst themselves. For example, configure
    one minion by querying live data from all the others. With great power
    comes great responsibility.

:doc:`Network topology <ref/topology>`
    At it's core, Salt is a highly scalable communication layer built on
    top of ZeroMQ that enables remote execution and configuration
    management. The possibilities are endless and Salt's future looks
    bright.

:doc:`Python API interface <ref/python-api>`
    Use Salt programmatically from your own scripts and programs easily and
    simply via ``import salt``.

Reference
---------

:doc:`Command-line interface <ref/cli/index>`
    Read the Salt manpages.

:doc:`Full list of master settings <ref/configuration/master>`
    Read through the heavily-commented master configuration file.

:doc:`Full list of minion settings <ref/configuration/minion>`
    Read through the heavily-commented minion configuration file.

:doc:`Full table of contents </contents>`
    Dense but complete.

More information about the project
----------------------------------

:doc:`Roadmap </topics/roadmap/index>`
    Where we're headed.

:doc:`Release notes </topics/releases/index>`
    Where we've been.

:doc:`Community </topics/community>`
    How you can get involved.

.. _`salt-contrib`: https://github.com/saltstack/salt-contrib
.. _`salt-states`: https://github.com/saltstack/salt-states
