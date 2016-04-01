:orphan:

.. _contents:

SaltStack
=========

Salt, a new approach to infrastructure management, is easy enough to get
running in minutes, scalable enough to manage tens of thousands of servers,
and fast enough to communicate with those servers in *seconds*.

Salt delivers a dynamic communication bus for infrastructures that can be used
for orchestration, remote execution, configuration management and much more.

Download
========

Salt source releases are available for download via the following PyPI link:

    https://pypi.python.org/pypi/salt

The installation document, found in the following link,  outlines where to
obtain packages and installation specifics for platforms:

    :doc:`Installation </topics/installation/index>`

The Salt Bootstrap project, found in the following repository, is a single
shell script, which automates the install correctly on  multiple platforms:

    https://github.com/saltstack/salt-bootstrap

Get Started
===============

A new `Get Started Guide <http://docs.saltstack.com/en/getstarted/>`_ walks you
through the basics of getting SaltStack up and running. You'll learn how to:

* Install and configure SaltStack
* Remotely execute commands across all managed systems
* Design, develop, and deploy system configurations

Tutorials
=========

This walkthrough is an additional tutorial to help you get started quickly and gain a
foundational knowledge of Salt:

:doc:`Official Salt Walkthrough </topics/tutorials/walkthrough>`

The following getting started tutorials are also available:

States - Configuration Management with Salt:
    - :doc:`Getting Started with States <topics/tutorials/starting_states>`
    - :doc:`Basic config management <topics/tutorials/states_pt1>`
    - :doc:`Less basic config management <topics/tutorials/states_pt2>`
    - :doc:`Advanced techniques <topics/tutorials/states_pt3>`
    - :doc:`Salt Fileserver Path Inheritance <topics/tutorials/states_pt4>`

Masterless Quickstart:
    :doc:`Salt Quickstart </topics/tutorials/quickstart>`

Running Salt without root access in userland:
    :doc:`Salt Usermode <topics/tutorials/rooted>`

A list of all tutorials can be found here:
    :doc:`All Salt tutorials <topics/tutorials/index>`

Demo Environments
=================

You can download one of the following `Vagrant <http://vagrantup.com>`_
projects to quickly set up a Salt demo environment:

- https://github.com/UtahDave/salt-vagrant-demo
- https://github.com/UtahDave/salt-vagrant-lxc

Example Formulas
================

A Github repo that contains a number of community-maintained formulas is
available at https://github.com/saltstack-formulas. Contributions are welcome!

A Github repo that contains formulas to install a number of Windows
applications is available at https://github.com/saltstack/salt-winrepo-ng. Note
that Salt makes this repo :ref:`available <windows-package-manager>` to your
Windows minions, and contributions are welcome!

Salt in depth
=============

While setting up, and using, Salt is a simple task, its capabilities run much
deeper. These documents provide a greater understanding of how Salt
empowers infrastructure management.

Remote execution
----------------

Running pre-defined or arbitrary commands on remote hosts, also known as
remote execution, is the core function of Salt. The following links explore
modules and returners, which are two key elements of remote execution.

**Modules**
    Salt modules, fundamental to remote execution, provide
    functionality such as installing packages, restarting a service,
    running a remote command, transferring files, and so on.

    :doc:`Full list of modules </ref/modules/all/index>`
        Contains: a list of core modules that ship with Salt.

    :doc:`Writing modules <ref/modules/index>`
        Contains: a guide on how to write Salt modules.

**Returners**
    Salt returners allow saving minion responses in various datastores, or
    to various locations, in addition to displaying the responses at the CLI.
    Returners can be used to extend Salt to communicate with new, or custom,
    interfaces and to support new databases.

    :doc:`Full list of returners </ref/returners/all/index>`
        Contains: list of returner modules used to store minion responses
        in Redis, Mongo, Cassandra, SQL, and others.

    :doc:`Writing returners <ref/returners/index>`
        Contains: instructions for writing returner modules.

Targeting
---------

Use :ref:`targeting <targeting>` to specify which minions should
execute commands and manage server configuration. The following links provide
additional information about targeting and matching minions.

:ref:`Globbing and regex <targeting-glob>`
    Match minions using globbing and regular expressions.

:ref:`Grains <targeting-grains>`
    Match minions using grains, which are bits of static information about the
    minion such as OS, software version, virtualization, CPU, memory, and so on.

:ref:`Pillar <targeting-pillar>`
    Match minions using user-defined variables.

:ref:`Subnet/IP Address <targeting-ipcidr>`
    Match minions by subnet or IP address (currently IPv4 only).

:ref:`Compound matching <targeting-compound>`
    Combine any of the above matchers into a single expression.

:ref:`Node groups <targeting-nodegroups>`
    Statically define groups of minions in the master config file using the
    :ref:`compound <targeting-compound>` matching syntax.

:ref:`Batching execution <targeting-batch>`
    Loop through all matching minions so that only a subset are executing a
    command at one time.

Configuration management
------------------------

Salt contains a robust and flexible configuration management framework, which
is built on the remote execution core. This framework executes on the minions,
allowing effortless, simultaneous configuration of tens of thousands of hosts,
by rendering language specific state files. The following links provide
resources to learn more about state and renderers.

**States**
    Express the state of a host using small, easy to read, easy to
    understand configuration files. *No programming required*.

    :doc:`Full list of states <ref/states/all/index>`
        Contains: list of install packages, create users, transfer files, start
        services, and so on.

    :doc:`Pillar System <topics/pillar/index>`
        Contains: description of Salt's Pillar system.

    :doc:`States Overview<ref/states/index>`
        Contains: an overview of states and some of the core components.

    :doc:`Highstate data structure <ref/states/highstate>`
        Contains: a dry vocabulary and technical representation of the
        configuration format that states represent.

    :doc:`Writing states <ref/states/writing>`
        Contains: a guide on how to write Salt state modules, easily extending
        Salt to directly manage more software.

**Renderers**
    Renderers use state configuration files written in a variety of languages,
    templating engines, or files. Salt's configuration management system is,
    under the hood, language agnostic.

    :doc:`Full list of renderers <ref/renderers/all/index>`
        Contains: a list of renderers.
        YAML is one choice, but many systems are available, from
        alternative templating engines to the PyDSL language for rendering
        sls formulas.

    :doc:`Renderers <ref/renderers/index>`
        Contains: more information about renderers. Salt states are only
        concerned with the ultimate highstate data structure, not how the
        data structure was created.

Miscellaneous topics
--------------------

The following links explore various Salt topics in depth.

:doc:`Salt Cloud <topics/cloud/index>`
    Salt Cloud is a public cloud provisioning tool that integrates Salt with
    many cloud providers.

:doc:`File Server <ref/file_server/index>`
    Salt can easily and quickly transfer files (in fact, that's how Salt
    states work). Even under heavy load, files are chunked and served.

:doc:`Syndic <topics/topology/syndic>`
    Syndic is a tool to allow one master host to manage many masters, which
    in turn manage many minions. Scale Salt to tens of thousands of hosts or
    across many different networks.

:doc:`Peer Communication <ref/peer>`
    Allow minions to communicate among themselves. For example, configure
    one minion by querying live data from all the others.

:doc:`Reactor System <topics/reactor/index>`
    The reactor system allows for Salt to create a self aware environment
    by hooking infrastructure events into actions.

:doc:`Firewall Settings and Salt <topics/tutorials/firewall>`
    This is a tutorial covering how to properly firewall a Salt Master server.

:doc:`Scheduling Executions (like states)<topics/jobs/schedule>`
    The schedule system in Salt allows for executions to be run from the master
    or minion at automatic intervals.

:doc:`Network topology <topics/topology/index>`
    At it's core, Salt is a highly scalable communication layer built on
    top of ZeroMQ, which enables remote execution and configuration
    management. The possibilities are endless and Salt's future looks
    bright.

:doc:`Testing Salt <topics/development/tests/index>`
    This is a  tutorial for writing unit tests and integration tests.

:doc:`Salt Proxy Minions <topics/proxyminion/index>`
    Proxy minions allow for the control of devices and machines which are
    unable to run a salt-minion.

:ref:`Python API interface <python-api>`
    The Python API allows the developer to use Salt locally from scripts and
    programs easily via ``import salt``.

:ref:`External API interfaces <netapi-introduction>`
    Expose a Salt API such as REST, XMPP, WebSockets, or others using netapi
    modules. Run these modules using the ``salt-api`` daemon.
    See the :ref:`full list of netapi modules <all-netapi-modules>`.

:doc:`Automatic Updates and Frozen Binary Deployments <topics/tutorials/esky>`
    Use a frozen install to make deployments easier (even on Windows!). Or
    take advantage of automatic updates to keep minions running the latest
    builds.

:doc:`Windows Software Manager / Package Repository <topics/windows/windows-package-manager>`
    Looking for an easy way to manage software on Windows machines?
    Search no more! Salt has an integrated software package manager for
    Windows machines! Install software hosted on the master, anywhere on the
    network, including any HTTP, HTTPS, or ftp server.

Reference
---------

:doc:`Command-line interface <ref/cli/index>`
    Read the Salt manpages.

:doc:`Full list of master settings <ref/configuration/master>`
    Read through the heavily-commented master configuration file.

:doc:`Full list of minion settings <ref/configuration/minion>`
    Read through the heavily-commented minion configuration file.

:doc:`Full table of contents </contents>`
    Read the table of contents of this document.

FAQ
===

See :doc:`here <faq>` for a list of Frequently Asked Questions.

More information about the project
==================================

:doc:`Release notes </topics/releases/index>`
    Living history of SaltStack.

:doc:`Salt Development </topics/development/index>`
    Information for Hacking on Salt

:doc:`Translate Documentation </topics/development/translating>`
    How to help out translating Salt to your language.

:ref:`Security disclosures <disclosure>`
    The SaltStack security disclosure policy

.. _`salt-contrib`: https://github.com/saltstack/salt-contrib
.. _`salt-states`: https://github.com/saltstack/salt-states
